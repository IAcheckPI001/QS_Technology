# Reporting Query API — hướng dẫn cho LLM / AI agent

Dùng khi người dùng hỏi số liệu hoặc danh sách ("sale A tháng này phụ trách bao nhiêu KH", "sản phẩm bán tháng 10"). LLM **không viết SQL**. LLM sinh một **JSON truy vấn**, backend kiểm tra và dựng SQL tham số hoá, rồi chạy. Chi tiết cho người đọc: `reporting-api.md`.

- Code: `internal/platform/reporting/`.
- Khác với `/ai/tools` (xem `ai-tools.md`): API này là `/reports/*`, **chỉ cần** `Authorization: Bearer <token của người đang hỏi>`. Không cần `X-API-Key`.
- Quyền và data scope của người hỏi quyết định dữ liệu trả về. Dataset `customers` cần quyền `customer.read`. Mọi bảng khác cần quyền `auth.manage_roles`. Thiếu quyền sẽ nhận 403.

---

## 1. Quy trình gọi (làm đúng thứ tự)

1. `GET /api/v1/reports/datasets` để xem bảng nào được dùng, kèm metrics, dimensions, date_fields.
2. Nếu câu hỏi cần join: `GET /api/v1/reports/tables/{table}` để lấy `columns` và `relations` của bảng. Mỗi `relations[].name` là một cột khoá ngoại, `relations[].table` là bảng đích. Lặp lại với bảng đích cho tới khi tới được cột cần.
3. Dựng JSON, gọi `POST /api/v1/reports/query`.
4. Nếu nhận **400**, đọc `error` (nội dung nói rõ cột nào hoặc quan hệ nào sai), sửa JSON và gọi lại. Tối đa 3 lần.
5. Trả lời người dùng bằng tiếng Việt từ `rows` và `totals`. Không bịa số.

Không đoán tên bảng hay cột. Chỉ dùng tên có trong bước 1 và 2.

## 2. Cấu trúc JSON

```json
{
  "dataset": "<tên bảng gốc>",
  "select": ["cột", "fk.fk.cột"],
  "dimensions": ["cột nhóm"],
  "metrics": ["count"],
  "filters": [{ "field": "cột", "op": "eq", "value": "x" }],
  "date_range": { "field": "created_at", "from": "2026-10-01", "to": "2026-10-31" },
  "order_by": [{ "field": "count", "dir": "desc" }],
  "limit": 100,
  "offset": 0,
  "totals": true
}
```

| Trường | Quy tắc |
|---|---|
| `dataset` | Bắt buộc. Tên bảng gốc |
| `select` | **Liệt kê record.** Không dùng chung với `metrics`/`dimensions` |
| `dimensions` + `metrics` | **Số liệu gộp.** `dimensions` là "chia theo cái gì", `metrics` là "tính gì" |
| Bắt buộc | Phải có ít nhất một trong `select`, `metrics`, `dimensions` (không để mảng rỗng) |
| `filters` | Nối bằng AND, tối đa 20 |
| `date_range` | `from`/`to` dạng `YYYY-MM-DD`, cả hai đầu đều tính. Cột ngày dùng được là `created_at`... xem `date_fields` |
| `order_by` | Chỉ theo trường đã có trong `select`, `metrics` hoặc `dimensions`. `dir` là `asc` hoặc `desc` |
| `limit` | Mặc định 100, tối đa 1000. `offset` để phân trang |
| `totals` | `true` thì trả thêm `totals`: tổng toàn bộ, không bị `limit` cắt. Chỉ có khi có cả `dimensions` và `metrics` |
| Trường lạ | Bị từ chối bằng 400 (không gửi `sort`, `pagination`, `module`, `entity`) |

### Chọn chế độ

| Người dùng hỏi | Dùng |
|---|---|
| "bao nhiêu", "tổng", "trung bình" | `metrics` |
| "theo từng sale / sản phẩm / tháng" | `dimensions` + `metrics` |
| "danh sách", "liệt kê", "xem các phiếu" | `select` |

### `metrics`

| Giá trị | Ý nghĩa |
|---|---|
| `count` | Đếm số dòng |
| `count_distinct:<cột>` | Đếm giá trị khác nhau (vd số khách khác nhau) |
| `count:<cột>` | Đếm dòng có cột không rỗng |
| `sum:<cột>`, `avg:<cột>`, `min:<cột>`, `max:<cột>` | Chỉ cho cột **số** |

### `filters.op`

| `op` | `value` |
|---|---|
| `eq`, `neq`, `contains` | Một chuỗi |
| `in`, `not_in` | Mảng chuỗi (1 đến 100 phần tử) |
| `is_null`, `not_null` | Không có `value` |

**Mọi `value` phải là chuỗi**, kể cả số và UUID. Không có toán tử `>`, `<`, `>=`: dùng `date_range` cho ngày. Không có OR/NOT.

### Cột ngày theo thời gian

Thêm hậu tố vào tên cột ngày để nhóm: `created_at_day`, `created_at_month`, `created_at_year`. Chỉ dùng trong `dimensions` (và `select` khi cột đó có sẵn).

### Đường dẫn join

`fk_col.fk_col.cột`: mỗi đoạn **trước** dấu chấm cuối là tên cột khoá ngoại (giữ nguyên tên trong DB, lấy từ `relations[].name`), đoạn **cuối** là cột thật.

Ví dụ `case_id.product_item_id.customer_id`:
- `case_id`: `support_assignments.case_id` → `support_cases`
- `product_item_id`: `support_cases.product_item_id` → `product_items`
- `customer_id`: cột thật của `product_items`

Dùng được ở `select`, `dimensions`, `metrics`, `filters`, `order_by`, `date_range.field`. Tối đa 4 bước và 8 bảng mỗi query. Luôn là `LEFT JOIN`, và chỉ đi từ bảng con sang bảng cha (không đi ngược cha → con).

## 3. Response

```json
{ "dataset": "customers", "columns": ["assigned_sales", "count"],
  "rows": [{ "assigned_sales": "9cf20ea7-…", "count": 8 }],
  "count": 9, "totals": { "count": 38 } }
```

- Tên cột trả về là tên trường đã gửi, với `.` đổi thành `__` và `:` đổi thành `_`. Ví dụ `case_id.status` trả về `case_id__status`.
- `order_by` vẫn dùng tên **gốc** (`count`, `avg:cột`), không dùng tên đã đổi.
- `count` trong response là số dòng trả về, **không phải** tổng số bản ghi. Muốn tổng thì dùng `totals`.
- Cột `assigned_sales` của dataset `customers` chỉ là UUID. Muốn tên sale, gọi thêm `GET /ai/tools/list_users` (xem `ai-tools.md`) hoặc dùng bảng có join sang `auth_users`.

## 4. Lỗi

| Mã | Ý nghĩa | LLM làm gì |
|---|---|---|
| 400 `invalid report query: ...` | Spec sai | Đọc thông báo, sửa JSON, gọi lại |
| 403 | Người hỏi không có quyền | Nói thẳng với người dùng, không thử lại |
| 401 | Token sai hoặc hết hạn | Báo đăng nhập lại |
| 500 | Lỗi DB hoặc quá 15 giây | Thu hẹp `date_range` hoặc `filters` rồi thử lại một lần |

Các lỗi 400 thường gặp: `unknown dimension`, `unknown metric`, `table "x" has no column "y"`, `"x" has no relation "y"`, `metric "..." needs a numeric column`, `select (list mode) cannot be combined with metrics or dimensions`, `at least one of select, metrics or dimensions is required`.

## 5. Ví dụ: câu hỏi → JSON → SQL

### 5.1 "Sale A tháng 10 đã hỗ trợ bao nhiêu khách?" (join nhiều bước, đếm khác nhau)

```json
{
  "dataset": "support_assignments",
  "metrics": ["count", "count_distinct:case_id.product_item_id.customer_id"],
  "filters": [{ "field": "assigned_to", "op": "eq", "value": "<uuid sale A>" }],
  "date_range": { "field": "created_at", "from": "2026-10-01", "to": "2026-10-31" }
}
```

```sql
SELECT COUNT(*)::bigint AS "count",
       COUNT(DISTINCT j2."customer_id")::bigint AS "count_distinct_case_id__product_item_id__customer_id"
FROM public."support_assignments" t
LEFT JOIN public."support_cases" j1 ON j1."id" = t."case_id"          AND j1."deleted_at" IS NULL
LEFT JOIN public."product_items" j2 ON j2."id" = j1."product_item_id" AND j2."deleted_at" IS NULL
WHERE TRUE AND COALESCE(t."assigned_to"::text, '') = $1
  AND t."created_at" >= $2::timestamp AND t."created_at" < ($3::date + 1)
```

### 5.2 "Top 10 sale có nhiều khách mới nhất tháng 10" (nhóm, sắp xếp, tổng)

```json
{
  "dataset": "customers",
  "dimensions": ["assigned_sales"],
  "metrics": ["count"],
  "filters": [{ "field": "customer_type", "op": "in", "value": ["lead", "student", "official"] }],
  "date_range": { "field": "created_at", "from": "2026-10-01", "to": "2026-10-31" },
  "order_by": [{ "field": "count", "dir": "desc" }],
  "limit": 10,
  "totals": true
}
```

```sql
SELECT COALESCE(c.assigned_sales_id::text, '') AS "assigned_sales", COUNT(*)::bigint AS "count"
FROM customers c LEFT JOIN customer_statuses cs ON cs.id = c.status_id
WHERE TRUE
  AND (c.deleted_at IS NULL AND c.merged_into_id IS NULL AND c.self_of_organization_id IS NULL)
  AND COALESCE(c.customer_type, '') = ANY($1::text[])
  AND c.created_at >= $2::timestamp AND c.created_at < ($3::date + 1)
GROUP BY COALESCE(c.assigned_sales_id::text, '')
ORDER BY "count" DESC LIMIT $4
```

### 5.3 "Liệt kê các phiếu hỗ trợ đã xong của sale A tháng 10–11" (`select`)

```json
{
  "dataset": "support_assignments",
  "select": ["case_id.case_number", "case_id.subject", "case_id.status",
             "case_id.product_item_id.customer_id.full_name", "assigned_to.username", "created_at"],
  "filters": [
    { "field": "case_id.status", "op": "in", "value": ["resolved", "closed"] },
    { "field": "assigned_to", "op": "eq", "value": "<uuid sale A>" }
  ],
  "date_range": { "field": "created_at", "from": "2026-10-01", "to": "2026-11-30" },
  "limit": 1000
}
```

```sql
SELECT j1."case_number" AS "case_id__case_number", j1."subject" AS "case_id__subject",
       j1."status" AS "case_id__status",
       j3."full_name" AS "case_id__product_item_id__customer_id__full_name",
       j4."username" AS "assigned_to__username", COALESCE(t."created_at"::text, '') AS "created_at"
FROM public."support_assignments" t
LEFT JOIN public."support_cases" j1 ON j1."id" = t."case_id"          AND j1."deleted_at" IS NULL
LEFT JOIN public."product_items" j2 ON j2."id" = j1."product_item_id" AND j2."deleted_at" IS NULL
LEFT JOIN public."customers"     j3 ON j3."id" = j2."customer_id"     AND j3."deleted_at" IS NULL
LEFT JOIN public."auth_users"    j4 ON j4."id" = t."assigned_to"
WHERE TRUE AND COALESCE(j1."status"::text,'') = ANY($1::text[]) AND COALESCE(t."assigned_to"::text,'') = $2
  AND t."created_at" >= $3::timestamp AND t."created_at" < ($4::date + 1)
ORDER BY t."created_at" DESC LIMIT $5
```

### 5.4 "Sản phẩm bán được trong tháng 10" (nhóm theo tên sản phẩm qua join)

Hệ thống không có bảng đơn bán hàng. "Bán" được hiểu là thiết bị được giao cho khách (`product_ownerships.created_at`). Nói rõ điều này khi trả lời.

```json
{
  "dataset": "product_ownerships",
  "dimensions": ["product_item_id.product_id.name"],
  "metrics": ["count"],
  "date_range": { "field": "created_at", "from": "2026-10-01", "to": "2026-10-31" },
  "order_by": [{ "field": "count", "dir": "desc" }]
}
```

```sql
SELECT COALESCE(j2."name"::text, '') AS "product_item_id__product_id__name", COUNT(*)::bigint AS "count"
FROM public."product_ownerships" t
LEFT JOIN public."product_items" j1 ON j1."id" = t."product_item_id" AND j1."deleted_at" IS NULL
LEFT JOIN public."products"      j2 ON j2."id" = j1."product_id"     AND j2."deleted_at" IS NULL
WHERE TRUE AND (t.deleted_at IS NULL)
  AND t."created_at" >= $1::timestamp AND t."created_at" < ($2::date + 1)
GROUP BY COALESCE(j2."name"::text, '')
ORDER BY "count" DESC LIMIT $3
```

## 6. Quy tắc cho LLM

1. Không bịa tên bảng, cột, quan hệ. Lấy từ `datasets` và `tables/{table}`.
2. Không gửi `select` cùng `metrics` hoặc `dimensions`.
3. Mọi `value` là chuỗi. UUID, số và ngày đều viết dạng chuỗi.
4. Lọc ngày bằng `date_range`, không bằng `filters`.
5. "Tháng này" thì tự đổi thành ngày cụ thể (`from` là ngày 1, `to` là ngày cuối tháng) dựa trên ngày hiện tại do hệ thống cung cấp.
6. Khi người dùng nói tên (tên sale, tên KH) thay vì UUID: tìm UUID trước (`list_users`, `search_customers` trong `ai-tools.md`), rồi mới truyền vào `filters`.
7. Khi nghĩa của câu hỏi mơ hồ (ví dụ "bán", "hỗ trợ", mốc ngày nào), nêu giả định đã dùng khi trả lời, hoặc hỏi lại người dùng.
8. Kết quả `rows` rỗng không có nghĩa là lỗi. Kiểm tra lại điều kiện lọc và quyền, rồi báo đúng như vậy.
9. Chưa hỗ trợ: OR/NOT, HAVING, INNER/RIGHT JOIN, join ngược cha → con, so sánh cột với cột, subquery, UNION, CTE. Nếu câu hỏi cần những thứ này, hãy tách thành nhiều lần gọi hoặc nói rõ là chưa làm được.

## 7. Code mẫu (Python)

```python
import requests

BASE = "http://localhost:8080/api/v1"

def run_report(token: str, spec: dict, retries: int = 3):
    h = {"Authorization": f"Bearer {token}"}
    for _ in range(retries):
        r = requests.post(f"{BASE}/reports/query", json=spec, headers=h, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 400:
            # đưa r.json()["error"] cho LLM để nó sửa spec rồi gọi lại
            spec = fix_with_llm(spec, r.json()["error"])
            continue
        r.raise_for_status()
    raise RuntimeError("spec still invalid after retries")

def table_info(token: str, table: str):
    h = {"Authorization": f"Bearer {token}"}
    return requests.get(f"{BASE}/reports/tables/{table}", headers=h, timeout=30).json()
```

`fix_with_llm` là hàm của agent: gửi spec cũ và thông báo lỗi cho LLM, nhận spec mới.

## 8. Gợi ý system prompt

> Bạn trả lời số liệu CRM/ERP bằng cách gọi API báo cáo. Không viết SQL. Trước khi dựng JSON, gọi `GET /reports/datasets` và `GET /reports/tables/{table}` để biết tên bảng, cột và quan hệ. Dùng `select` để liệt kê record, `dimensions` + `metrics` để thống kê, không trộn hai chế độ. Mọi `value` trong `filters` là chuỗi. Lọc ngày bằng `date_range`. Nếu API trả 400, đọc `error`, sửa JSON và gọi lại (tối đa 3 lần). Chỉ báo số lấy từ kết quả. Khi câu hỏi mơ hồ, nêu rõ giả định.

## 9. Giới hạn hiện tại

- Mọi bảng tự sinh cần quyền `auth.manage_roles`. Người dùng không có quyền này chỉ hỏi được dataset `customers`.
- Chưa có phân trang kèm tổng số dòng cho `select`.
- Bảng mới tạo chỉ xuất hiện sau khi API khởi động lại.
- Chưa kiểm tra qua HTTP với token thật. Các ví dụ 5.1 (bản không `group by`), 5.2, 5.3, 5.4 dựa trên query đã chạy thử trên DB, riêng 5.1 là biến thể rút gọn của query đã chạy.
