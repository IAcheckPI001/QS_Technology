"""Kiểm tool truy vấn thô (crm_schema/crm_query) với CRM thật (thủ công, không chạy trong CI).

1. Index tĩnh (`reporting/raw/schema_index.py`, sinh từ SQL dump) khớp `GET /reports/datasets`
   và `GET /reports/tables/{table}` của CRM: bảng/cột có ở một bên mà không có ở bên kia.
   Lệch thì cập nhật dump và chạy lại `scripts/build_crm_schema_index.py`.
2. Query mẫu (ví dụ 5.1–5.4 của ai-reporting-query.md và vài câu hỏi đa dạng) đi qua
   `compile_raw` của tool rồi gửi CRM: chỉ in HTTP status và số dòng, không in dữ liệu.
3. Query chạm bảng/cột bị chặn phải bị từ chối trước khi tới CRM.

Chạy từ thư mục backend (cần CRM_API_BASE_URL trong .env):

    $env:CRM_EVAL_ACCESS_TOKEN = "<token đăng nhập CRM>"
    .\\venv\\Scripts\\python.exe evals\\check_crm_query_tool.py

Exit code 1 nếu index lệch CRM, query mẫu bị CRM từ chối, hoặc query bị chặn lọt qua.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.modules.chatbot.providers.crm_api import REPORT_QUERY_PATH, REPORT_TABLES_PATH  # noqa: E402
from app.modules.chatbot.reporting.raw.compile import RawQueryError, compile_raw  # noqa: E402
from app.modules.chatbot.reporting.raw.policy import (  # noqa: E402
    BLOCKED_TABLES,
    NOT_EXPOSED_TABLES,
    QUERYABLE_TABLES,
    UNRELEASED_TABLES,
)
from app.modules.chatbot.reporting.raw.schema_index import TABLES  # noqa: E402
from app.modules.chatbot.schemas.system.raw_query import RawQuery  # noqa: E402

# Bảng CRM tự ẩn khỏi Reporting API (đã biết): không tính là lệch.
CRM_HIDDEN = {"password_reset_tokens", "push_device_tokens", "schema_migrations", "sessions",
              "sso_tickets", "verification_codes"}
# Cột CRM tự ẩn theo tên (password/token/secret/hash/api_key/otp).
CRM_HIDDEN_COLUMN = ("password", "token", "secret", "hash", "api_key", "otp")

SAMPLES: list[tuple[str, dict[str, Any]]] = [
    ("5.1 sale hỗ trợ bao nhiêu khách", {
        "dataset": "support_assignments",
        "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
        "filters": [{"field": "assigned_to.username", "op": "contains", "value": "a"}],
        "date_range": {"field": "created_at", "preset": "this_year"},
    }),
    ("5.2 top sale theo khách mới", {
        "dataset": "customers", "dimensions": ["assigned_sales", "assigned_sales_id.username"],
        "metrics": ["count"],
        "filters": [{"field": "customer_type", "op": "in", "value": ["lead", "student", "official"]}],
        "date_range": {"field": "created_at", "preset": "last_30_days"},
        "order_by": [{"field": "count", "dir": "desc"}], "limit": 10,
    }),
    ("5.3 phiếu đã xong của sale", {
        "dataset": "support_assignments",
        "select": ["case_id.case_number", "case_id.status", "case_id.product_item_id.customer_id.full_name",
                   "assigned_to.username", "created_at"],
        "filters": [{"field": "case_id.status", "op": "in", "value": ["resolved", "closed"]}],
        "date_range": {"field": "created_at", "preset": "this_year"},
    }),
    ("5.4 sản phẩm bán được", {
        "dataset": "product_ownerships", "dimensions": ["product_item_id.product_id.name"],
        "metrics": ["count"],
        "filters": [{"field": "transferred_from_ownership_id", "op": "is_null", "value": None}],
        "date_range": {"field": "created_at", "preset": "this_year"},
        "order_by": [{"field": "count", "dir": "desc"}],
    }),
    ("tìm khách theo tên", {
        "dataset": "customers", "select": ["code", "full_name", "phone", "assigned_sales_id.username"],
        "filters": [{"field": "full_name", "op": "contains", "value": "hohmeier"}],
    }),
    ("PO theo trạng thái", {
        "dataset": "purchase_orders", "dimensions": ["status"], "metrics": ["count"],
    }),
    ("tồn kho theo vật tư", {
        "dataset": "stock", "dimensions": ["material_id.name"], "metrics": ["sum:qty"], "limit": 10,
    }),
    ("họ tên nhân viên", {
        "dataset": "user_profiles", "select": ["user_id.username", "last_name", "first_name"], "limit": 5,
    }),
    ("user đang hoạt động", {
        "dataset": "auth_users", "metrics": ["count"],
        "filters": [{"field": "is_active", "op": "eq", "value": "true"}],
    }),
    ("phiếu theo tháng tạo", {
        "dataset": "support_cases", "dimensions": ["created_at_month"], "metrics": ["count"],
        "date_range": {"field": "created_at", "preset": "this_year"},
    }),
]
BLOCKED: list[tuple[str, dict[str, Any]]] = [
    ("khoá mở máy", {"dataset": "lock_requests", "select": ["status", "unlock_key"]}),
    ("input sinh khoá qua join", {"dataset": "support_cases", "select": ["product_item_id.device_input"]}),
    ("kết quả kích hoạt", {"dataset": "product_item_activation_requests", "select": ["result"]}),
    ("hash mật khẩu qua join", {"dataset": "customers", "select": ["assigned_sales_id.password_hash"]}),
]


def _raw(fields: dict[str, Any]) -> RawQuery:
    """Query mẫu viết theo contract CRM; `mode` (bắt buộc từ P0) suy từ select."""
    return RawQuery.model_validate({"mode": "list" if fields.get("select") else "aggregate", **fields})


def _rows(response: httpx.Response) -> str:
    rows = response.json().get("rows")
    return f"{len(rows)} dòng" if isinstance(rows, list) else "?"


async def check_index(client: httpx.AsyncClient) -> int:
    problems = 0
    response = await client.get("/api/v1/reports/datasets")
    response.raise_for_status()
    live = {item["name"] for item in response.json()["datasets"]}
    expected = set(TABLES) - CRM_HIDDEN - NOT_EXPOSED_TABLES
    for name in sorted(expected - live):
        problems += 1
        print(f"  THIẾU TRÊN CRM  {name}")
    for name in sorted(live - set(TABLES) - UNRELEASED_TABLES):
        problems += 1
        print(f"  MỚI TRÊN CRM    {name} (chưa có trong index: cập nhật dump)")
    print(f"  bảng module CRM chưa triển khai (không dùng): {', '.join(sorted(UNRELEASED_TABLES & live)) or '-'}")
    for name in sorted(NOT_EXPOSED_TABLES & live):
        print(f"  CRM trả lại bảng {name}: xem lại NOT_EXPOSED_TABLES")
    exposed = sorted(BLOCKED_TABLES & live)
    print(f"  bảng CRM cho dùng nhưng dịch vụ AI chặn: {', '.join(exposed) or '-'}")

    for name in QUERYABLE_TABLES:
        if name not in live:
            continue
        table = await client.get(f"{REPORT_TABLES_PATH}/{name}")
        if table.status_code != 200:
            problems += 1
            print(f"  HTTP {table.status_code}  /tables/{name}")
            continue
        payload = table.json()
        columns = {item["name"] for item in payload.get("columns") or []}
        relations = {item["name"]: item["table"] for item in payload.get("relations") or []}
        index = TABLES[name]
        missing = sorted(
            column for column in set(index.columns) - columns
            if not any(word in column for word in CRM_HIDDEN_COLUMN)
        )
        extra = sorted(columns - set(index.columns))
        relation_diff = sorted(
            f"{column}->{target}" for column, target in relations.items()
            if index.relations.get(column) != target
        )
        if missing or extra or relation_diff:
            problems += 1
            print(f"  LỆCH {name}: thiếu trên CRM {missing}; mới trên CRM {extra}; quan hệ khác {relation_diff}")
    print(f"  {len(QUERYABLE_TABLES)} bảng truy vấn được đã so cột/quan hệ")
    return problems


async def check_samples(client: httpx.AsyncClient, now: datetime) -> int:
    tz = ZoneInfo(settings.crm_report_timezone)
    problems = 0
    for label, fields in SAMPLES:
        compiled = compile_raw(_raw(fields), now=now, tz=tz)
        for body in (compiled.body, compiled.count_body):
            if body is None:
                continue
            response = await client.post(REPORT_QUERY_PATH, json=body)
            kind = "count" if body is compiled.count_body else compiled.mode
            if response.status_code == 200:
                print(f"  OK        {label} [{kind}]: {_rows(response)}")
            elif response.status_code == 403:
                print(f"  FORBIDDEN {label} [{kind}]: token không có quyền")
            else:
                problems += 1
                print(f"  HTTP {response.status_code}  {label} [{kind}]: {response.text[:200]}")
    for label, fields in BLOCKED:
        try:
            compile_raw(_raw(fields), now=now, tz=tz)
        except (RawQueryError, ValueError) as error:
            print(f"  CHẶN      {label}: {error}")
        else:
            problems += 1
            print(f"  LỌT       {label}: query bị chặn vẫn compile được")
    return problems


async def main() -> int:
    token = os.environ.get("CRM_EVAL_ACCESS_TOKEN", "").strip()
    if not settings.crm_api_base_url or not token:
        print("Cần CRM_API_BASE_URL và CRM_EVAL_ACCESS_TOKEN.")
        return 2
    headers = {"Authorization": f"Bearer {token}", "ngrok-skip-browser-warning": "1"}
    async with httpx.AsyncClient(base_url=settings.crm_api_base_url, headers=headers, timeout=30) as client:
        print("[index tĩnh ↔ CRM]")
        problems = await check_index(client)
        print("\n[query mẫu]")
        problems += await check_samples(client, datetime.now(UTC))
    print(f"\n{problems} vấn đề")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
