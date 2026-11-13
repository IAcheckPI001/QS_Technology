# Chỉ mục xử lý `crm_report` và `crm_records`

Tài liệu này là bản đồ đọc code cho phương án A (catalog) của luồng
`crm-agent`. Nó tập trung vào câu hỏi: file nào khai báo contract, hàm nào
chuẩn hóa query, hàm nào biên dịch/call CRM, và ở bước nào LLM nhận kết quả để
viết câu trả lời.

> **Phạm vi bật tool:** `CRM_REPORT_ENABLED=true` và `CRM_TOOLS=catalog` hoặc
> `both`. Mặc định hiện tại là `CRM_REPORT_ENABLED=false`, `CRM_TOOLS=query`;
> khi đó hai tool này không được đăng ký.

## 1. Sơ đồ tổng quát

```text
POST /chat/crm
  -> ChatbotService / AgentRunner
  -> OpenAIProvider.chat_complete_tools(tool_choice="auto")
  -> LLM trả tool call:
       crm_report(arguments: ReportQuery)
       hoặc crm_records(arguments: RecordQuery)
  -> ToolRegistry.invoke
  -> Pydantic validate input
  -> tool.run (closure trong crm_report.py / crm_records.py)
  -> validate_query / validate_records
  -> nhánh nguồn dữ liệu:
       list_api   -> CrmListClient.fetch_all -> engine/records
       report_api -> compile_report hoặc compile_records
                   -> CrmReportClient.query (POST /api/v1/reports/query)
                   -> merge_report hoặc report_records
  -> ToolOutput được serialize thành message role="tool"
  -> LLM gọi lại với tool_choice="auto" để đọc output
  -> AgentRunner gọi bước cuối tool_choice="none"
  -> LLM trả text cuối -> SSE delta / history
```

Điểm quan trọng: LLM **không tự dựng JSON HTTP của Reporting API**. LLM chỉ
điền tên logic trong `ReportQuery`/`RecordQuery`. Backend lấy đường dẫn bảng,
cột, metric, filter hệ thống và định nghĩa nghiệp vụ từ catalog rồi mới tạo
request gửi CRM.

## 2. Điểm khởi tạo và đăng ký tool

| Bước | File / hàm | Trách nhiệm |
|---|---|---|
| Đọc cờ cấu hình | [`backend/app/core/config.py`](../../../../backend/app/core/config.py) | Cung cấp `crm_report_enabled`, `crm_tools`, URL, timeout, timezone và giới hạn lấy dữ liệu. |
| Tạo client | [`agent/setup.py`](../../../../backend/app/modules/chatbot/agent/setup.py), `build_agent_runner` | Tạo `CrmReportClient` và `CrmListClient`; khi `CRM_TOOLS` là `catalog`/`both` thì gọi hai builder của tool. |
| Đăng ký report | [`tools/crm_report.py`](../../../../backend/app/modules/chatbot/tools/crm_report.py), `build_crm_report_tool` | Tạo `ToolSpec(name="crm_report")`, gắn `ReportQuery`, `ReportOutput`, guide, giới hạn 4 call/lượt. |
| Đăng ký records | [`tools/crm_records.py`](../../../../backend/app/modules/chatbot/tools/crm_records.py), `build_crm_records_tool` | Tạo `ToolSpec(name="crm_records")`, gắn `RecordQuery`, `RecordsOutput`, guide, giới hạn 3 call/lượt. |
| Đăng ký vào registry | [`tools/registry.py`](../../../../backend/app/modules/chatbot/tools/registry.py), `ToolRegistry.__init__`, `register`, `provider_tools` | Kiểm tra contract, chuyển Pydantic schema thành schema provider và tạo danh sách `tools` gửi cho LLM. |

`build_agent_runner` dùng `available_datasets(datasets, report_client)` để
chỉ đưa các dataset `report_api` vào khi có `CrmReportClient`. Catalog được
đăng ký tại [`reporting/datasets/__init__.py`](../../../../backend/app/modules/chatbot/reporting/datasets/__init__.py),
biến `DATASETS`.

## 3. Contract mà LLM được phép tạo

### 3.1 `crm_report`

File [`schemas/system/report.py`](../../../../backend/app/modules/chatbot/schemas/system/report.py):

| Symbol | Vai trò |
|---|---|
| `ReportFilter` | Field, operator và value của filter; filter kết hợp AND. |
| `ReportDateRange` | `field`, preset hoặc `[start, end)`; ngày kết thúc không bao gồm. |
| `ReportSort` | Sắp xếp theo metric/dimension/period. |
| `ReportQuery` | Dataset, 1–3 metrics, tối đa 2 dimensions, filters, date range, time grain, sort, limit. |

Các enum dataset/metric/filter/dimension/date được sinh từ `DATASETS`, nhưng
kiểm tra hợp lệ theo **dataset đã chọn** chỉ xảy ra ở
`reporting.validate.validate_query`.

### 3.2 `crm_records`

File [`schemas/system/records.py`](../../../../backend/app/modules/chatbot/schemas/system/records.py):

| Symbol | Vai trò |
|---|---|
| `RecordSort` | Chỉ sort theo field đã chọn để hiển thị. |
| `RecordQuery` | Dataset, whitelist fields, filters/date range, limit tối đa 20 và offset. |

`RecordQuery` dùng lại `ReportFilter` và `ReportDateRange`; field thực sự được
phép liệt kê được kiểm tra theo `DatasetSpec.list_columns`.

## 4. Catalog dataset và nguồn dữ liệu

File nền tảng là [`reporting/catalog.py`](../../../../backend/app/modules/chatbot/reporting/catalog.py):

| Symbol | Vai trò |
|---|---|
| `FieldSpec` | Tên logic, kiểu, enum, filterable/groupable và đường dẫn API. |
| `MetricSpec` | Phép tính logic; với report API có `api_metric` và filter riêng. |
| `ColumnSpec` | Whitelist field cho `crm_records`; cột không khai báo không được đọc/trả về. |
| `ReportApiSource` | Bảng API, date paths, system/default filters, period dimensions và quyền mô tả. |
| `DatasetSpec` | Gom field, metric, date, source, parser, list columns và definitions. |
| `DatasetSpec.parse` | Parse item từ list API; item sai schema bị bỏ và chỉ đếm `skipped`. |

Dataset đăng ký hiện tại:

| Dataset | File | Nguồn |
|---|---|---|
| `tickets` | [`reporting/datasets/tickets.py`](../../../../backend/app/modules/chatbot/reporting/datasets/tickets.py) | `list_api`; lấy bản ghi rồi engine lọc/nhóm/tính metric. |
| `customers` | [`reporting/datasets/customers.py`](../../../../backend/app/modules/chatbot/reporting/datasets/customers.py) | `report_api`; catalog ánh xạ field/metric sang Reporting API. |
| `support_assignments` | [`reporting/datasets/assignments.py`](../../../../backend/app/modules/chatbot/reporting/datasets/assignments.py) | `report_api`. |
| `device_deliveries` | [`reporting/datasets/deliveries.py`](../../../../backend/app/modules/chatbot/reporting/datasets/deliveries.py) | `report_api`. |

## 5. Luồng `crm_report` chi tiết

### 5.1 Từ tool call đến query chuẩn hóa

Entry point là closure `run` trong
[`tools/crm_report.py`](../../../../backend/app/modules/chatbot/tools/crm_report.py):

1. `crm_credential` lấy token từ `principal.crm_access_token`, hoặc fallback
   sang `acting_user_id`; giá trị token không ghi log.
2. `query_shape` ghi metadata an toàn vào span, không ghi giá trị filter/ngày
   cụ thể.
3. Nếu không có credential, ném `ToolRejected("crm_user_missing")`.
4. `validate_query` trong
   [`reporting/validate.py`](../../../../backend/app/modules/chatbot/reporting/validate.py)
   thực hiện:
   - chọn `DatasetSpec`;
   - kiểm tra metric/dimension;
   - gọi `_condition` và `_scalar` để kiểm operator, kiểu, enum và chuẩn hóa value;
   - gọi `_date_range` để đổi preset hoặc start/end thành khoảng thời gian;
   - kiểm `time_grain`, số kỳ, sort và limit;
   - trả `NormalizedQuery`.
5. Query sai nghiệp vụ được đổi thành `ToolArgumentError`, tức mã
   `tool_invalid_args`; `ToolRegistry` gửi detail cho LLM để sửa call.

### 5.2 Nhánh `list_api` (hiện chủ yếu là `tickets`)

Trong `run`:

1. `CrmListClient.fetch_all` lấy lần lượt các trang từ endpoint
   `DatasetSpec.source_path`.
2. `DatasetSpec.parse` đổi item JSON thành record typed và loại item sai định dạng.
3. `run_report` trong
   [`reporting/engine.py`](../../../../backend/app/modules/chatbot/reporting/engine.py)
   gọi chuỗi xử lý:
   - `filter_records` / `_filter`: filter hệ thống, date range và filter LLM;
   - `_groups`, `_group_rows`: tạo nhóm theo dimensions/time grain;
   - `compute_metric` / `_metrics`: tính count, avg, max, sum hoặc metric dẫn xuất;
   - `period_change`: tính delta/delta_pct giữa các kỳ;
   - sort, điền kỳ trống và giới hạn rows.
4. `_output` tạo `ReportOutput` gồm `applied`, `rows`, `matched_count`,
   `fetched_count`, `skipped_count`, `source_truncated`, `definitions`.

### 5.3 Nhánh `report_api` (customers/assignments/deliveries)

`run` gọi `_run_report_api` trong
[`tools/crm_report.py`](../../../../backend/app/modules/chatbot/tools/crm_report.py):

1. `compile_report` trong
   [`reporting/report_api.py`](../../../../backend/app/modules/chatbot/reporting/report_api.py)
   gọi `base_filters`, `api_date_range`, `_metric_groups`, `_paths` và
   `_period_dimension`.
2. Kết quả là `CompiledReport` với một hoặc nhiều `ApiQuery`:
   - query `values` lấy metric/rows;
   - query `ranking` bổ sung khi cần xếp hạng theo nhóm và chia kỳ;
   - query gốc có `count` để lấy `matched_count`;
   - metric có filter riêng được tách thành nhóm query riêng.
3. `query_all` chạy các body song song bằng `asyncio.TaskGroup`, gọi
   `CrmReportClient.query` cho từng body. Lỗi đầu tiên thành `ToolRejected`;
   các query còn lại bị hủy.
4. `merge_report` ghép `ApiResult` theo khóa dimension/kỳ, tính metric, sort,
   limit, kỳ trống, delta và `total_groups`.
5. `_output` trả `ReportOutput`; với report API,
   `fetched_count` và `skipped_count` là `null`, còn `source="report_api"`.

## 6. Luồng `crm_records` chi tiết

Entry point là closure `run` trong
[`tools/crm_records.py`](../../../../backend/app/modules/chatbot/tools/crm_records.py):

1. Lấy credential bằng `crm_credential` dùng chung với `crm_report`.
2. `validate_records` trong
   [`reporting/records.py`](../../../../backend/app/modules/chatbot/reporting/records.py)
   kiểm dataset có `list_columns`, whitelist fields, filters/date range, sort,
   limit và offset; trả `NormalizedRecords`.
3. Nhánh `list_api` gọi `_from_list_api`:
   - `CrmListClient.fetch_all`;
   - `DatasetSpec.parse`;
   - `list_records` → `filter_records`, getter của `ColumnSpec`, sort, offset/limit;
   - `render`/`render_value` loại control character, đổi timezone và cắt text.
4. Nhánh `report_api` gọi `_from_report_api`:
   - `compile_records` tạo một body `select` và một body `count`;
   - `query_all` gọi cả hai qua `CrmReportClient`;
   - `report_records` lấy field theo `api_column`, tạo items và đọc tổng count;
   - `render` chuẩn hóa dữ liệu hiển thị.
5. `RecordsOutput` trả `items`, `returned`, `total`, `has_more`, `next_offset`,
   `source`, `source_truncated` và `definitions`.

`crm_records` không dùng để thống kê; nó chỉ liệt kê tối đa 20 dòng theo
whitelist. `crm_report` không trả bản ghi thô; nó trả rows đã tổng hợp.

## 7. Các hàm thực hiện HTTP call CRM

File [`providers/crm_api.py`](../../../../backend/app/modules/chatbot/providers/crm_api.py)
đảm nhiệm toàn bộ HTTP access:

| Hàm | HTTP | Được gọi từ | Kết quả |
|---|---|---|---|
| `CrmListClient.fetch_all` | `GET source_path?limit=&offset=` nhiều trang | `crm_report.run`, `crm_records._from_list_api` | `ListPage(items, total, truncated)`. |
| `CrmListClient._page` | Thực hiện từng GET | `fetch_all` | Parse `items`/`total`, kiểm body. |
| `CrmReportClient.query` | `POST /api/v1/reports/query` | `query_all` trong cả hai tool | `ReportPage(rows, totals, truncated)`. |
| `CrmReportClient.get_table` | `GET /api/v1/reports/tables/{table}` | Tool `crm_schema`/`crm_query`, không phải nhánh catalog trực tiếp | `TableSchema(columns, relations)`. |
| `_headers` | Tạo Authorization header | các client | Không ghi token vào log. |
| `_raise_for_access` | Ánh xạ 401/403 | các client | `crm_auth_failed` / `crm_forbidden`. |

Trong `CrmReportClient.query`:

- HTTP 400 với query catalog sinh ra → `crm_report_contract_error`;
- timeout/network/body sai hoặc status khác → `crm_unavailable`;
- 401/403 → lỗi quyền tương ứng;
- response hợp lệ phải có `rows` là list object, `totals` có thể là dict.

## 8. LLM nhận query và kết quả ở bước nào?

### Bước A — LLM sinh query arguments

`AgentRunner._run` trong
[`agent/runner.py`](../../../../backend/app/modules/chatbot/agent/runner.py)
gọi `_complete(..., tool_choice="auto")`. Provider
[`providers/openai.py`](../../../../backend/app/modules/chatbot/providers/openai.py)
`OpenAIProvider.chat_complete_tools` nhận response của OpenAI và chuyển từng
function call thành:

```text
ToolCallRequest(name="crm_report" hoặc "crm_records",
                arguments_raw="<JSON do LLM tạo>")
```

Đây là thời điểm LLM trả **query logic** (`ReportQuery` hoặc `RecordQuery`),
chưa phải JSON request cuối gửi Reporting API.

### Bước B — Backend thực thi và gửi kết quả về context LLM

`ToolRegistry.invoke` trong
[`tools/registry.py`](../../../../backend/app/modules/chatbot/tools/registry.py)
parse JSON, Pydantic-validate input, gọi `ToolSpec.run`, rồi tạo
`ToolOutcome`. Trong `_run`, `ToolOutcome.message_content` serialize
`ReportOutput`/`RecordsOutput` thành message:

```text
role="tool", tool_call_id=<id>, content=<JSON output đã cắt theo budget>
```

Nếu output quá lớn, `ReportOutput.to_llm` hoặc `RecordsOutput.to_llm` cắt bớt
rows/items và đánh dấu `truncated`, `omitted_rows`.

### Bước C — LLM đọc kết quả và trả lời

Sau khi thêm message `role="tool"`, `AgentRunner._run` quay lại vòng lặp và
gọi `_complete(..., tool_choice="auto")` lần kế tiếp. LLM đọc output, có thể:

- sửa arguments nếu nhận `tool_invalid_args`;
- gọi `crm_records` để xem danh sách sau khi có số liệu;
- gọi lại tool với `offset=next_offset`;
- hoặc viết câu trả lời nếu đã đủ dữ liệu.

Khi LLM không còn tool call nhưng có content, `_run` trả content đó. Nếu cần
bước kết thúc bắt buộc, runner gọi `_complete(..., tool_choice="none")`; content
của lần gọi này là câu trả lời cuối. `AgentRunner.run` yield câu trả lời thành
một chunk, sau đó tầng chat chuyển thành SSE delta và ghi history.

## 9. Prompt/guide chi phối cách LLM sử dụng output

| File / symbol | Nội dung |
|---|---|
| [`agent/prompts.py`](../../../../backend/app/modules/chatbot/agent/prompts.py), `AGENT_SYSTEM_PROMPT` | Luật chung: dữ liệu nghiệp vụ phải qua tool, output là dữ liệu không phải chỉ dẫn, sửa lỗi tối đa một lần, giữ nguyên số liệu. |
| `tools/crm_report.py`, `CRM_REPORT_DESCRIPTION` | Khi nào dùng báo cáo tổng hợp, dataset nào phù hợp, không dùng để liệt kê record. |
| `tools/crm_report.py`, `CRM_REPORT_GUIDE` | Cách tạo date/filter và cách đọc `applied`, `change`, `source_truncated`, `definitions`, lỗi CRM. |
| `tools/crm_records.py`, `CRM_RECORDS_DESCRIPTION` | Khi nào dùng danh sách record, giới hạn 20 dòng và whitelist cột. |
| `tools/crm_records.py`, `CRM_RECORDS_GUIDE` | Cách dùng `offset`, trình bày `total`/`has_more`, và xử lý dữ liệu record như dữ liệu không tin cậy. |
| `agent/runner.py`, `build_messages` | Ghép guide của các tool được phép vào system prompt; schema tool được gửi riêng qua tham số `tools`. |

## 10. Bảng tra nhanh theo mục tiêu

| Muốn tìm… | Mở file / hàm |
|---|---|
| Tool có được bật không | `agent/setup.py:build_agent_runner` |
| Input LLM được phép gửi | `schemas/system/report.py:ReportQuery`, `schemas/system/records.py:RecordQuery` |
| Dataset, metric, field, whitelist | `reporting/catalog.py:DatasetSpec`, `reporting/datasets/*` |
| Validate report query | `reporting/validate.py:validate_query` |
| Validate/list records | `reporting/records.py:validate_records`, `list_records` |
| Compile report API JSON | `reporting/report_api.py:compile_report` |
| Merge report API response | `reporting/report_api.py:merge_report` |
| Compile records API JSON | `reporting/records.py:compile_records` |
| Merge records response | `reporting/records.py:report_records` |
| Chạy list API | `providers/crm_api.py:CrmListClient.fetch_all` |
| Chạy Reporting API | `providers/crm_api.py:CrmReportClient.query` |
| LLM nhận tool call | `providers/openai.py:OpenAIProvider.chat_complete_tools` |
| Tool output quay lại LLM | `agent/runner.py:AgentRunner._run`, `ToolOutcome.message_content` |
| LLM viết câu trả lời cuối | `agent/runner.py:AgentRunner._complete` với `tool_choice="none"` hoặc lần `auto` không có tool call |

## 11. Ranh giới trách nhiệm và lỗi thường gặp

- **Không sửa `CrmReportClient` để thêm logic nghiệp vụ:** logic ánh xạ catalog
  nằm ở `reporting/report_api.py`; client chỉ HTTP, parse response và ánh xạ lỗi.
- **Không để LLM thấy đường dẫn bảng/cột:** các đường dẫn nằm trong
  `DatasetSpec`/`ReportApiSource`; LLM chỉ thấy catalog text và tên logic.
- **Không dùng `crm_report` cho danh sách:** dùng `crm_records`, vì hai output và
  giới hạn dữ liệu khác nhau.
- **HTTP 400 của catalog không phải lỗi để LLM tự sửa:** đó là
  `crm_report_contract_error`, dấu hiệu catalog lệch schema CRM.
- **Số 0 hoặc rows rỗng không mặc định là lỗi:** guide yêu cầu LLM nêu đó là
  không có dữ liệu hoặc ngoài phạm vi token.
- **Thay catalog phải kiểm chứng lại API:** chạy
  `backend/evals/check_crm_report_contract.py` với token CRM thật; test unit nằm
  trong `backend/tests/chatbot/` với nhóm `test_report_*`, `test_tool_*`.

