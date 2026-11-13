# Luồng crm-agent: agent gọi tool trên kênh CRM

Thiết kế của luồng. Trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử ở [LOG.md](LOG.md).
Bản mô tả đầy đủ trước 2026-11-11 (bảng `catalog_match`, chi tiết `crm_report`):
[LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## Phạm vi

Nhân viên CRM hỏi qua `POST /chat/crm`; agent tự chọn tool để tra tài liệu sản phẩm
(`product_docs_ask`) hoặc lấy số liệu/danh sách từ CRM, rồi viết câu trả lời. Luồng **thử
nghiệm**. Phần chung của lượt chat (service key, session, lease, ghi history, trace) thuộc
[chat-platform](../chat-platform/README.md).

## Điểm vào

| Loại | Vị trí | Ghi chú |
|---|---|---|
| Route | `POST /chat/crm` (`chatbot/routers/chat.py`) | Rẽ sang agent trong `ChatbotService` khi kênh CRM và có `agent_runner` |
| Startup | `agent/setup.py` `build_agent_runner` (gọi từ `main.py`) | Chỉ khi `CRM_CHAT_FLOW=agent` và có OpenAI; thiếu capability/schema sai → dừng khởi động (`ToolConfigurationError`) |
| Eval tay | `backend/evals/run_crm_agent_eval.py`, `check_crm_query_tool.py`, `check_crm_report_contract.py` | Cần OpenAI, CRM thật, `CRM_EVAL_ACCESS_TOKEN`; không chạy trong CI |
| Script | `backend/scripts/build_crm_schema_index.py` | Sinh `reporting/raw/schema_index.py` từ `docs/ai/tool_instruction/database-structure.sql` |

## Pipeline

```text
ChatbotService (security → session/lease → context → prune: chat-platform)
 └─ AgentRunner.run (agent/runner.py)
     ├─ chờ slot (AGENT_MAX_CONCURRENT_RUNS), Deadline(AGENT_TURN_TIMEOUT_S)
     ├─ lặp ≤ AGENT_MAX_STEPS: provider.chat_complete_tools(tool_choice="auto")
     │    └─ ToolRegistry.invoke → tool (song song ≤ AGENT_PARALLEL_TOOLS khi read_only + concurrency_safe)
     ├─ bước cuối tool_choice="none" (hết bước, hết lượt tool, hết giờ, trả lời rỗng lần đầu)
     └─ bỏ [S#] không thuộc nguồn của lượt → một SSE delta → history completed
```

| Vùng | File | Vai trò |
|---|---|---|
| Runner | `agent/runner.py`, `deadline.py`, `prompts.py`, `setup.py` | Vòng lặp tool-calling, giới hạn, deadline, prompt chung; `plan()` để trống |
| Tool contract | `tools/base.py`, `registry.py`, `schema.py` | `ToolSpec`, `ToolOutcome`, `ToolRejected`; chuẩn hóa JSON Schema duy nhất ở `to_provider_schema` |
| Tool tài liệu | `tools/product_docs.py`, `stages/catalog_lookup_stage.py`, `extraction/product_catalog.py` | Chạy `RetrievalPipeline` của website-qa trên RunState con + tìm model theo bảng capabilities |
| Truy vấn thô (C) | `tools/crm_schema.py`, `crm_query.py`, `reporting/raw/` (`compile`, `policy`, `values`, `schema`, `schema_index`, `hints`), `schemas/system/raw_query.py` | LLM tự dựng query trên mọi bảng Reporting API |
| Catalog (A) | `tools/crm_report.py`, `crm_records.py`, `reporting/` (`catalog`, `datasets/`, `validate`, `engine`, `report_api`, `records`, `dates`), `schemas/system/report.py`, `records.py` | 4 dataset định nghĩa sẵn |
| CRM client | `providers/crm_api.py` | `CrmListClient` (API danh sách), `CrmReportClient` (`POST /api/v1/reports/query`, `GET /api/v1/reports/tables/{t}`) |
| Provider | `providers/base.py`, `openai.py` | `ToolCallingProvider` + `LLMCapabilities` |

## Tool

| Tool | Bật khi | Việc | Trần mỗi lượt |
|---|---|---|---|
| `product_docs_ask` | luôn | Tra tài liệu: clarification → analysis → `CatalogLookupStage` → execution, không compose. Status `answered`, `matched`, `no_match`, `needs_clarification`, `no_docs`, `handoff`, `out_of_scope`, `failed` | theo spec |
| `crm_schema` | `CRM_REPORT_ENABLED` và `CRM_TOOLS` ∈ {`query`, `both`} | Mô tả bảng và cột của CRM, quan hệ (kèm 1-1, tuỳ chọn), bảng con, nghĩa của `deleted_at`, giá trị hợp lệ, `known_values` (giá trị thật của bảng tra cứu) của 1–4 bảng; cột bị chặn không trả về | 2 |
| `crm_query` | như trên | `RawQuery`: `mode=list` (`select`) hoặc `aggregate` (`dimensions`/`metrics`), `filters` ≤ 20 (AND), `date_range` (preset tương đối, `month`/`year` do code tính, `custom`; giờ Việt Nam), `order_by`, `limit` ≤ 100, `offset` ≤ 1000, `include_inactive` (bỏ filter mặc định). Giá trị filter được kiểm theo kiểu cột (`reporting/raw/values.py`). Filter mặc định theo dataset (`hints.DEFAULT_FILTERS`: `user_roles` chỉ tài khoản còn dùng, `customers` không tính khách spam) được thêm khi LLM không tự lọc cột đó, ghi "(mặc định: …)" trong `applied.filters`. Danh sách chạy thêm query `count` song song để có `total` | 6 lần thử, trong đó 4 lần tới CRM |

Tên bảng (`crm_schema.tables`, `crm_query.dataset`) kiểm trong code theo `QUERYABLE_TABLES`, không
là enum trong JSON schema; tên lạ trả `tool_invalid_args` kèm gợi ý. Trần `crm_query` (2026-11-12):
runner áp 6 lần thử; `run()` từ chối lần gửi CRM thứ 5 bằng `tool_call_limit`; lần bị compile chặn
không tốn lượt CRM. Call bị `tool_call_limit` không trừ trần chung `AGENT_MAX_TOOL_CALLS`.
| `crm_report` | `CRM_REPORT_ENABLED` và `CRM_TOOLS` ∈ {`catalog`, `both`} | Số liệu tổng hợp theo catalog (`ReportQuery`) | theo spec |
| `crm_records` | như trên | Danh sách ≤ 20 dòng theo whitelist cột (`RecordQuery`) | 3 |

Mặc định `CRM_TOOLS=query` (phương án C, D-005). Mô tả `crm_query` cho LLM nằm ở
`CRM_QUERY_DESCRIPTION`; nhóm bảng theo nghiệp vụ ở `reporting/raw/hints.py`.

## Contract

- Route, SSE, mã lỗi stream (`agent_error`): [api_guidelines.md](../../api_guidelines.md)
  mục "`POST /chat/website` và `POST /chat/crm`" và "Response và SSE contract".
- Snapshot và trace của lượt agent (`agent_steps`, `tool_errors`): api_guidelines.md mục
  "Support chat history".
- Mã lỗi trả lại LLM (không lộ ra client):

| Nhóm | Mã |
|---|---|
| Registry, runner | `tool_not_found`, `tool_not_allowed`, `tool_invalid_args`, `tool_timeout`, `tool_failed`, `tool_invalid_output`, `tool_output_too_large`, `tool_budget_exhausted`, `tool_call_limit` |
| Agent (→ SSE `agent_error`) | `agent_context_missing`, `agent_timeout`, `agent_empty_answer` |
| Nghiệp vụ tool | `model_not_evidenced`, `crm_user_missing` |
| CRM (`providers/crm_api.py`) | `crm_auth_failed` (401), `crm_forbidden` (403), `crm_query_invalid` (400 của query do LLM dựng, LLM sửa và gọi lại), `crm_report_contract_error` (400 của catalog: lỗi cấu hình), `crm_unavailable` |

## Bất biến của luồng

- Runner trung lập với tool: luật chung ở `agent/prompts.py`, luật riêng ở `ToolSpec.guide`,
  chỉ ghép guide của tool principal được dùng. Danh sách tool đi qua tham số `tools`.
- Thêm tool: input `extra="forbid"`, output kế thừa `ToolOutput` (tự cắt bằng `to_llm`),
  khai báo `read_only`/`concurrency_safe`/`deduplicate`/`max_calls_per_turn`/`required_scope`,
  đăng ký ở `agent/setup.py`. Tool gọi CRM chỉ qua `providers/crm_api.py`.
- Mỗi `tool_call_id` có đúng một `ToolOutcome`; `CancelledError` không bao giờ bị bắt; tầng
  agent không tạo task chạy ngầm.
- Backend kiểm soát dữ liệu: model trong câu hỏi agent phải có bằng chứng (tin nhắn, history,
  ngữ cảnh model của phiên, `discovered_models`, hoặc nguồn qua `based_on_sources`).
- `crm_query`: query sai kiểu không tới CRM (CRM vẫn chạy và trả 0 dòng). `compile_raw` kiểm giá
  trị filter theo kiểu cột cuối của đường dẫn (schema sống trong cache trước, index tĩnh sau):
  - uuid chỉ nhận UUID, không `contains`;
  - số và bool được chuẩn hoá;
  - giá trị CHECK/ENUM so không phân biệt hoa thường;
  - cột ngày chỉ lọc qua `date_range`, trừ `is_null`/`not_null` và `contains "YYYY-MM"` trên cột ngày thứ hai;
  - `is_null`/`not_null` bỏ qua `value` (kể cả `""`);
  - `order_by` theo cột chưa chọn ở mode list được thêm vào `select`.
- `crm_query`, luật ngày trong `compile_raw` (mọi model, 2026-11-12): năm câu hỏi không nêu (`dates.stated_years`) bị bỏ, dùng kỳ gần nhất; kỳ đặt trong filters (gồm `<cột>_month eq "N"`) chuyển thành `date_range`; filter lặp đúng kỳ của `date_range` bị bỏ; có kỳ thì bỏ filter trong `hints.DROP_WITH_DATE_RANGE` (`support_assignments.is_current`). Đường dẫn dùng tên bảng thay khoá ngoại bị chặn kèm gợi ý khoá ngoại.
- `crm_query`: mọi đường dẫn qua `policy.check_path`; bảng/cột bị chặn
  (`reporting/raw/policy.py`: khóa, token, cấu hình hệ thống, khóa kích hoạt máy) không bao
  giờ tới CRM. CRM kiểm quyền và phạm vi dữ liệu theo token; dịch vụ AI không lọc thêm.
- `crm_access_token` là `SecretStr`, không log, không lưu; không có token thì Bearer là
  `acting_user_id` (bị log và lưu, nên không được là bí mật).
- Dữ liệu nghiệp vụ CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM và có thể nằm
  trong câu trả lời lưu ở `chat_history` (D-005).

## Cấu hình

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `CRM_CHAT_FLOW` | `agent` | `pipeline`: CRM chạy luồng website-qa (rollback) |
| `CRM_REPORT_ENABLED` | `false` | Bật tool CRM; bắt buộc `CRM_API_BASE_URL`, múi giờ IANA |
| `CRM_TOOLS` | `query` | `query` (C), `catalog` (A), `both` |
| `CRM_SCHEMA_CACHE_S` | 600 | Cache schema sống của bảng CRM (dùng chung giữa người dùng) |
| `CRM_QUERY_AUDIT_LOG` | `false` | Audit `crm_query` có giá trị filter và body gửi CRM (có thể là PII) vào logger `app.crm_query.audit`; chỉ bật có thời hạn |
| `CRM_API_TIMEOUT_S`, `CRM_REPORT_MAX_ITEMS`, `CRM_REPORT_TIMEZONE` | 10, 2000, `Asia/Ho_Chi_Minh` | |
| `AGENT_MAX_STEPS`, `AGENT_MAX_TOOL_CALLS` | 6, 8 | |
| `AGENT_MODEL`, `AGENT_REASONING_EFFORT`, `AGENT_MAX_COMPLETION_TOKENS` | rỗng (= `OPENAI_MODEL`), rỗng, 1200 | Model riêng cho vòng lặp agent; model suy luận (`gpt-5…`, `o3…`) gửi `max_completion_tokens` và không gửi `temperature` |
| `AGENT_TURN_TIMEOUT_S`, `AGENT_LLM_TIMEOUT_S`, `AGENT_TOOL_TIMEOUT_S`, `AGENT_FINAL_RESERVE_S` | 60, 20, 20, 10 | Mọi timeout lấy từ deadline chung |
| `AGENT_TOOL_OUTPUT_TOKENS`, `AGENT_PARALLEL_TOOLS`, `AGENT_MAX_CONCURRENT_RUNS`, `AGENT_HISTORY_MESSAGES` | 3000, 3, 8, 6 | |

## Test và eval

Từ thư mục `backend`:

```powershell
.\venv\Scripts\python.exe -m pytest tests\chatbot
```

Test riêng của luồng: `test_agent_*`, `test_crm_*` (gồm `test_crm_query_tool.py`),
`test_report_*`, `test_tool_*`, `test_product_docs_tool.py`, `test_catalog_lookup_tool.py`;
fake ở `agent_fakes.py`, `report_fakes.py`. Eval tay (cần `$env:CRM_EVAL_ACCESS_TOKEN`):

```powershell
.\venv\Scripts\python.exe evals\run_crm_agent_eval.py [case_id ...]
.\venv\Scripts\python.exe evals\check_crm_query_tool.py
.\venv\Scripts\python.exe evals\compare_agent_models.py --models gpt-4.1-mini --runs 3 [--effort low] [--log file] [--json file]
.\venv\Scripts\python.exe evals\check_crm_report_contract.py
```

Chạy lại `check_crm_query_tool.py` mỗi khi cập nhật dump schema CRM; lệch thì chạy lại
`scripts\build_crm_schema_index.py`. Bảng trong `NOT_EXPOSED_TABLES`/`UNRELEASED_TABLES` không
tính là lệch.

## Log runtime

- Dòng log `agent llm step=…`, `agent tool step=…`,
  `crm_query done attempt=… outcome=… dataset=… returned=… ignored=…`.
- Span `agent.run`, `llm.chat_tools`, `tool.<name>` (có `error_detail` đã che giá trị) trong
  trace của lượt; lưu `public.chat_traces` khi `CHAT_TRACE_PERSIST=true`.

### Giám sát query LLM dựng (`crm_query`)

`build_agent_runner()` chỉ đăng ký tool lúc startup. Query được dựng trong từng lượt:
1. `AgentRunner._complete`: LLM trả `arguments_raw`.
2. `ToolRegistry.invoke`: validate thành `RawQuery`.
3. `compile_raw`: bỏ field thừa, đổi preset ngày, chặn đường dẫn.
4. CRM `POST /reports/query`.

Có hai tầng giám sát:

- **Metadata, luôn bật** (span `tool.crm_query`, log thường, không có giá trị):
  - `attempt`: lần gọi thứ mấy trong lượt;
  - `dataset`, `mode`, cột, `filters` (dạng `cột op`), `filter_value_counts`;
  - `date_from`/`date_to` đã đổi ra ngày;
  - `ignored`;
  - `outcome` ∈ `ok`, `empty` (0 dòng), `invalid_args`, `rejected` (bị compile/policy chặn), `crm_invalid` (CRM 400), `crm_error`.

  Root span có `crm_query_attempts`, `crm_query_outcomes`. Muốn tìm lượt phải sửa query hoặc ra rỗng thì lọc `chat_traces` theo hai trường này.

  Span `tool.crm_schema` có `tables`, `cache_hits`.
- **Audit, sau `CRM_QUERY_AUDIT_LOG`** (`reporting/raw/audit.py`): mỗi lần gọi `crm_query` sinh một dòng JSON `QueryAuditRecord` vào logger `app.crm_query.audit`.
  - Các trường: `trace_id`, `request_id`, `tool_call_id`, `attempt`, `phase` (`invalid_args`/`rejected`/`sent`), `outcome`, `arguments` (hoặc `arguments_raw` khi không validate được), `body`/`count_body` gửi CRM, `ignored`, khoảng ngày, lỗi, `returned`/`total`, `latency_ms`.
  - Không ghi `rows`, câu hỏi hay câu trả lời. Câu hỏi tra theo `request_id` trong `chat_history`.
  - Argument không validate được ghi qua hook `ToolSpec.on_invalid_args`.
- `crm_schema` trả cho mỗi bảng (`TableDescription`):
  - `description`: mô tả bảng của CRM, lấy từ `GET /reports/datasets` (cache cùng TTL; lỗi thì bỏ trống, không làm hỏng tool).
  - `columns`: `tên:kiểu[=giá trị hợp lệ] — mô tả của CRM` (bỏ mô tả của `id`, `created_at`, `updated_at`; cắt 160 ký tự).
  - `relations`: `fk->bảng`, thêm `(1-1)` khi CRM báo `one_to_one`, `(có thể trống)` khi khoá ngoại `nullable` (join giữ dòng con, cột của cha trống).
  - `referenced_by`: các bảng con trỏ tới bảng này (theo `referenced_by` của CRM, thiếu thì theo index tĩnh), tối đa 12. Join chỉ đi từ con lên cha, nên ví dụ họ tên nằm ở `user_profiles` thì phải lấy `user_profiles` làm dataset.
  - `deleted_at`: theo `deleted_at_meaning` của CRM. `deleted`: CRM tự loại dòng xoá mềm, kể cả dòng con qua khoá ngoại bắt buộc. `ended` (`product_ownerships`, `product_agents`, `product_user_access`): lúc kết thúc, CRM không lọc.
  - `person_filter`: có khi bảng có cột trỏ tới `auth_users`; giải thích các cột đó là UUID, và cách lọc theo username hoặc theo tên người (tra `user_profiles` trước).
  - `known_values`: đường dẫn cột → giá trị thật hiện có của bảng tra cứu do admin tạo (`hints.LOOKUP_TABLES`: `roles` hệ thống, `customer_statuses`, `customer_status_groups`, `customer_groups`, `business_fields`), dạng `giá_trị = nhãn`, tối đa 60. Có cho chính bảng đó và cho khoá ngoại trỏ tới nó (vd `user_roles`: `role_id.code`). Lấy bằng `POST /reports/query` theo token người dùng, cache cùng TTL; lỗi (vd 403) thì báo "không lấy được danh sách", không cache.
- Định nghĩa nghiệp vụ "nhân viên <vai trò>" (Toma 2026-11-12): người được gán vai trò đó qua `user_roles` (nhân viên sales = vai trò code `sales`; admin có quyền sales nhưng không tính), đếm `count_distinct:user_id`, chỉ tài khoản còn dùng trừ khi hỏi kể cả người đã nghỉ (`include_inactive`).
- Định nghĩa "khách hàng" (Toma 2026-11-12): không tính khách `spam` (filter mặc định), khách `lost` vẫn tính; khách đã xoá và đã gộp do dataset `customers` của CRM tự loại.
- Guide `crm_query` viết cho `AGENT_MODEL=gpt-4.1-mini` (2026-11-12, khoảng 1.35k token): giữ định tuyến bảng, luật CRM model không tự biết (dấu tiếng Việt, ranh giới UTC, xoá mềm, cột ẩn) và cách trả lời; luật đã ép trong code (năm, kỳ trong filters, filter mặc định, `is_current`) không lặp lại trong guide.
- Bảng không dùng (`reporting/raw/policy.py`): `BLOCKED_TABLES` (khoá/bí mật), `NOT_EXPOSED_TABLES` (`sales_users`, `user_types`: CRM không còn trả), `UNRELEASED_TABLES` (8 bảng module CRM chưa triển khai). Quan hệ trỏ tới các bảng này bị ẩn và join bị chặn.
- Thời gian: CRM lưu UTC. `render_value` (`reporting/records.py`) đổi mọi thời điểm trả về sang `CRM_REPORT_TIMEZONE`; chuỗi không kèm múi giờ coi là UTC, chuỗi chỉ có ngày giữ nguyên. `date_range` gửi ngày lịch Việt Nam nhưng CRM cắt theo ngày UTC (ranh giới 07:00 giờ Việt Nam), nhóm `_day/_month/_year` cũng vậy (chấp nhận tạm, LOG 2026-11-12).
- `evals/run_crm_agent_eval.py` luôn bật audit và in từng lần thử. Case có thể đặt `queries_any`, `final_query_outcome_any`, `query_attempts_max` để chấm query, không chỉ chấm câu trả lời. `date_field`, `no_date_range`, `date_from`/`date_to`, `sent_filters` xét body gửi CRM (sau compile); `filters`, `filter_equals` xét argument LLM dựng. Username nhân viên thật nằm ở biến `CRM_EVAL_STAFF_USERNAME` (chỗ giữ `{staff_username}`), không ghi vào repo. `compare_agent_models.py` báo thêm "đạt bỏ giới hạn gọi" (`passed_ignoring_budget`).
- `chat_history.retrieval_snapshot`: `agent_steps`, `answered_without_tools`,
  `invalid_citations`. `RunStats` của runner chỉ ở bộ nhớ.

## Ranh giới với luồng khác

- `product_docs_ask` dùng lại `RetrievalPipeline`, `Retriever` của
  [website-qa](../website-qa/README.md); đổi pipeline đó thì chạy cả test agent.
- Đầu lượt và cuối lượt (security, session, lease, ghi history) thuộc chat-platform.
- Registry model `chatbot/extraction/registry.py` dùng chung với website-qa.
- Tài liệu của repo CRM: `docs/ai/tool_instruction/` (chỉ grep, không đọc nguyên file).
