"""Kiểm tra catalog report_api khớp schema CRM thật (thủ công, không chạy trong CI).

Với mỗi dataset report_api, gửi tới `POST /api/v1/reports/query` các query nhỏ do chính
`reporting/report_api.py` và `reporting/records.py` sinh ra:
- mỗi metric (không dimension), mỗi dimension (metric đầu tiên), mỗi kỳ chia được;
- một query `select` mọi cột danh sách, `limit` 1.
Query nào bị CRM từ chối (400) là đường dẫn cột/tên dimension trong catalog lệch schema
CRM: script in thông báo lỗi của CRM để sửa catalog. Chỉ in số dòng, không in dữ liệu.

Chạy từ thư mục backend (cần CRM_API_BASE_URL trong .env hoặc môi trường):

    $env:CRM_EVAL_ACCESS_TOKEN = "<token đăng nhập CRM>"
    .\\venv\\Scripts\\python.exe evals\\check_crm_report_contract.py [dataset ...]

Token cần quyền customer.read (customers) và auth.manage_roles (các dataset còn lại);
thiếu quyền thì CRM trả 403 và script báo FORBIDDEN, không phải lỗi catalog.
Exit code 1 nếu có query bị từ chối vì spec.
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
from app.modules.chatbot.providers.crm_api import REPORT_QUERY_PATH  # noqa: E402
from app.modules.chatbot.reporting.catalog import DatasetSpec  # noqa: E402
from app.modules.chatbot.reporting.datasets import DATASETS  # noqa: E402
from app.modules.chatbot.reporting.records import compile_records, validate_records  # noqa: E402
from app.modules.chatbot.reporting.report_api import compile_report  # noqa: E402
from app.modules.chatbot.reporting.validate import validate_query  # noqa: E402
from app.modules.chatbot.schemas.system.records import RecordQuery  # noqa: E402
from app.modules.chatbot.schemas.system.report import ReportQuery  # noqa: E402


def _checks(spec: DatasetSpec, now: datetime) -> list[tuple[str, dict[str, Any]]]:
    tz = ZoneInfo(settings.crm_report_timezone)
    date_range = {"field": spec.default_date_field, "preset": "last_30_days"}
    first_metric = next(iter(spec.metrics))
    specs: list[tuple[str, dict[str, Any]]] = []
    specs += [(f"metric {name}", {"metrics": [name], "date_range": date_range}) for name in spec.metrics]
    specs += [
        (f"dimension {name}", {"metrics": [first_metric], "dimensions": [name], "date_range": date_range})
        for name in spec.dimensions()
    ]
    assert spec.report is not None
    for field in spec.date_fields:
        for grain in ("day", "month"):
            if spec.report.period_dimension(field, grain) is not None:
                specs.append((f"period {field} {grain}", {
                    "metrics": [first_metric], "time_grain": grain,
                    "date_range": {"field": field, "preset": "last_30_days"},
                }))
    bodies: list[tuple[str, dict[str, Any]]] = []
    for label, fields in specs:
        query = validate_query(
            ReportQuery.model_validate({"dataset": spec.name, **fields}), DATASETS, now=now, tz=tz,
        )
        bodies += [(f"{label} [{item.role}]", item.body) for item in compile_report(query).queries]
    if spec.list_columns:
        records = validate_records(
            RecordQuery.model_validate({
                "dataset": spec.name, "fields": list(spec.list_columns)[:8], "limit": 1,
            }),
            DATASETS, now=now, tz=tz,
        )
        select, count, _ = compile_records(records)
        bodies += [("select list_columns", select), ("select count", count)]
    return bodies


async def main(selected: list[str]) -> int:
    token = os.environ.get("CRM_EVAL_ACCESS_TOKEN", "").strip()
    if not settings.crm_api_base_url or not token:
        print("Cần CRM_API_BASE_URL và CRM_EVAL_ACCESS_TOKEN.")
        return 2
    now = datetime.now(UTC)
    datasets = [spec for spec in DATASETS.values() if spec.report is not None]
    if selected:
        datasets = [spec for spec in datasets if spec.name in selected]
    rejected = 0
    headers = {"Authorization": f"Bearer {token}", "ngrok-skip-browser-warning": "1"}
    async with httpx.AsyncClient(base_url=settings.crm_api_base_url, headers=headers, timeout=30) as client:
        for spec in datasets:
            print(f"\n[{spec.name}] (CRM dataset {spec.report.table if spec.report else '-'})")
            for label, body in _checks(spec, now):
                response = await client.post(REPORT_QUERY_PATH, json=body)
                if response.status_code == 200:
                    rows = response.json().get("rows")
                    print(f"  OK         {label}: {len(rows) if isinstance(rows, list) else '?'} dòng")
                elif response.status_code == 403:
                    print(f"  FORBIDDEN  {label}: token không có quyền")
                else:
                    rejected += response.status_code == 400
                    try:
                        detail = response.json().get("error")
                    except ValueError:
                        detail = response.text[:200]
                    print(f"  HTTP {response.status_code}   {label}: {detail}")
    print(f"\n{rejected} query bị từ chối vì spec")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
