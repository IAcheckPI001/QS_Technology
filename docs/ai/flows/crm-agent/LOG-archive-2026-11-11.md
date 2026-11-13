# Lưu trữ luồng crm-agent tới 2026-11-11

Chép nguyên văn ngày 2026-11-11 khi tách tài liệu theo luồng (D-002). Không sửa file này;
trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử mới ở [LOG.md](LOG.md). Phần lấy từ
`current-state.md` giữ nguyên tiếng Anh như bản gốc.

- **Đã lỗi thời:** việc 12d ghi "decision 2026-11-10 with Toma: option A, no raw
  `list_datasets`/`get_table`/`run_query` tools for the LLM". Cùng ngày quyết định này được
  thay bằng phương án C (`crm_schema` + `crm_query`, D-005); xem [LOG.md](LOG.md).
- Mục "Luồng agent" chưa nhắc tới `crm_schema`/`crm_query` vì được viết trước phương án C.


## Từ `architecture.md`: mục "Luồng agent (kênh CRM)"


Trạng thái: **thử nghiệm**. Kênh CRM luôn chạy agent khi `CRM_CHAT_FLOW=agent`
(mặc định); `CRM_CHAT_FLOW=pipeline` đưa CRM về luồng tra cứu ở trên (rollback,
không phải lựa chọn của từng người dùng). Website không bị ảnh hưởng.

`ChatbotService` rẽ nhánh sau khi nạp context (bước 5–6): kênh CRM và có
`agent_runner` → `AgentRunner.run(state)`; còn lại → `RetrievalPipeline` +
compose như trên. Phần đầu lượt (security, session/lease, context, chặn khi
`mode ≠ bot`) và phần cuối lượt (history completed/error/cancelled) dùng chung.

**Orchestrator là code, không có planner LLM riêng.** `AgentRunner` chạy vòng
lặp tool-calling: mỗi bước gọi `provider.chat_complete_tools`; LLM tự chọn tool
và tham số; runner validate, kiểm quyền, thực thi và ghi trace. `plan()` để sẵn
chỗ chèn bước lập kế hoạch khi số tool lớn (khoảng 15–20+).

**Hybrid: LLM điều phối, backend kiểm soát dữ liệu.** LLM quyết định gọi tool
nào, khi nào và có cần bước tiếp không. Tool (backend) quyết định dữ liệu nào hợp
lệ: output có cấu trúc kèm bước kế tiếp hợp lệ (vd. `catalog_match.next_action`),
từ chối call sai nghiệp vụ bằng mã lỗi (vd. `model_not_evidenced`).

**Orchestrator trung lập với tool.** Runner không biết tool làm gì; mọi hành vi
riêng do `ToolSpec` khai báo, nên thêm tool báo cáo/CRM không phải sửa runner và
luật của tool này không áp lên tool khác:
- luật chung ở system prompt, luật riêng ở `ToolSpec.guide` (xem dưới);
- state riêng của tool trong lượt ở `AgentRun.tool_states` (subclass
  `ToolTurnState`, lấy qua `ToolContext.turn_state(...)`); `AgentRun` chỉ giữ
  phần chung: `steps`, `source_texts` (S# → nội dung), `invalid_citations`;
- song song theo `read_only` + `concurrency_safe`, gộp call trùng theo
  `deduplicate`, trần riêng theo `max_calls_per_turn`.

**Prompt hai cấp.** Cấp agent: `agent/prompts.py` chỉ chứa luật **chung** cho mọi
tool (dữ liệu nghiệp vụ phải lấy qua tool phụ trách, output tool là dữ liệu, xử
lý lỗi tool, hỏi lại khi tool cần thêm thông tin, trích `[S#]`) và
`<now>`/`<language_hint>`. Luật đọc output của từng tool nằm ở `ToolSpec.guide`,
ghép vào `<tool_guides>` **chỉ cho các tool principal được dùng**
(`registry.allowed`); vd. luật model/catalog nằm trong `PRODUCT_DOCS_GUIDE`.
Danh sách tool **không** render vào prompt mà gửi qua tham số `tools` của
provider, sinh từ `ToolRegistry`; `ToolSpec.description` nói khi nào gọi và input.
Cấp miền: prompt `AnalysisStage` cùng intent/entity registry chạy **bên trong**
`product_docs_ask`; agent không thấy registry intent.

**Provider contract** (`providers/base.py`). `ToolCallingProvider` khai báo
`LLMCapabilities` tĩnh: `tool_calling`, `parallel_tool_calls`,
`tool_choice_none`, `tool_choice_required`, `schema_dialect`
(`openai_strict` | `json_schema_basic`). Agent cần `tool_calling` và
`tool_choice_none`; không giả định mọi endpoint OpenAI-compatible hỗ trợ đủ.
`OpenAIProvider` khai báo đủ. `chat_complete_tools` trả `AssistantTurn`
(`content`, `tool_calls[{id, name, arguments_raw}]`, `finish_reason`, `usage`);
arguments giữ nguyên chuỗi, registry mới parse. Backend của tool (Tavily, CRM…)
không phải provider.

**ToolRegistry** (`tools/`). `ToolSpec(name, description, input_model,
output_model, run, guide, read_only, concurrency_safe, deduplicate,
max_calls_per_turn, timeout_s, required_scope)`:
- Tên theo `^[a-zA-Z0-9_-]{1,64}$` (không dấu chấm: `product_docs_ask`); input
  model bắt buộc `extra="forbid"`; output kế thừa `ToolOutput`.
- `to_provider_schema` là nơi **duy nhất** chuẩn hóa JSON Schema của Pydantic:
  inline `$defs`/`$ref`, `Optional[T]` → `type: [T, "null"]`,
  `additionalProperties: false` mọi object, strict thì mọi field vào `required`
  và bỏ keyword không hỗ trợ (ràng buộc vẫn do Pydantic kiểm khi validate).
  Dict tự do, schema đệ quy, union object với dialect basic → lỗi lúc startup.
- `allowed(principal)`: hiện mọi tool không đòi scope đều được dùng (chưa có
  role/scope cho nhân viên CRM) — điểm gắn phân quyền sau này.
- `invoke` luôn trả đúng một `ToolOutcome` cho mỗi `tool_call_id`; lỗi là mã gửi
  lại LLM: `tool_invalid_args` (JSON sai, sai schema, field lạ; kèm vị trí lỗi,
  không lặp giá trị), `tool_not_found`, `tool_not_allowed`, `tool_timeout`,
  `tool_failed` (chi tiết chỉ vào log), `tool_invalid_output`,
  `tool_output_too_large`. Tool từ chối vì nghiệp vụ bằng `ToolRejected(code,
  detail)` (`ToolArgumentError` → `tool_invalid_args`); `detail` do tool viết,
  không chứa dữ liệu nhạy cảm. `CancelledError` không bao giờ bị bắt.
- Thêm tool mới: input `extra="forbid"`, output kế thừa `ToolOutput` (tự cắt
  bằng `to_llm` nếu lớn), `description` + `guide`, khai báo `read_only` /
  `concurrency_safe` / `deduplicate` (tool ghi: không gộp call, chưa hỗ trợ xác
  nhận người dùng) / `max_calls_per_turn` / `required_scope`, đăng ký trong
  `agent/setup.py`. State trong lượt dùng subclass `ToolTurnState` riêng.

**Giao thức tool-call trong runner.**
- `tool_choice="auto"` trong vòng lặp; `"none"` cho bước cuối (hết bước, hết
  lượt gọi tool, hết giờ, hoặc lần trả lời rỗng đầu tiên) — vẫn gửi `tools` để
  lịch sử message `tool` hợp lệ.
- Có tool call (kèm hoặc không kèm content): content là suy nghĩ trung gian,
  không gửi người dùng nhưng giữ trong assistant message. Chỉ có content: câu
  trả lời cuối, yield thành **một** `delta` (chưa stream token). Rỗng hai lần:
  `agent_empty_answer`. `finish_reason=length`: câu trả lời vẫn trả kèm log
  cảnh báo; tool call bị cắt thành `tool_invalid_args`.
- Mỗi `tool_call_id` có đúng một message `role=tool`, theo thứ tự call; call
  vượt `AGENT_MAX_TOOL_CALLS` nhận `tool_budget_exhausted`, call bỏ vì hết giờ
  nhận `tool_timeout`, call vượt `max_calls_per_turn` của tool nhận
  `tool_call_limit` (call của tool khác vẫn chạy).
- Call trùng (cùng tên, argument giống nhau sau khi chuẩn hóa thứ tự key và
  khoảng trắng) của tool `deduplicate` (mặc định = `read_only`) không chạy lại:
  dùng output của call thành công ở bước trước hoặc của call cùng response, bước
  ghi `status="deduplicated"`. Call lỗi được thử lại; tool ghi luôn chạy.
- Câu trả lời cuối: `[S#]` không thuộc nguồn đã trả trong lượt bị bỏ khỏi câu
  trả lời và ghi vào `invalid_citations`.
- Output tool được cắt theo **token** (`util/token_counter.py`,
  `AGENT_TOOL_OUTPUT_TOKENS`). `product_docs_ask` cắt theo cấu trúc: luôn giữ
  `status`/`clarification`/`task_results`, thêm nguồn theo rank tới khi hết
  budget, nguồn cuối cắt ở ranh giới câu, ghi `truncated`/`omitted_sources`.

**Deadline chung và cancellation.** `Deadline(AGENT_TURN_TIMEOUT_S)`; mỗi lời
gọi nhận `min(giới hạn riêng, thời gian còn lại − AGENT_FINAL_RESERVE_S)` nên
tổng không vượt timeout của lượt; còn dưới phần dự phòng thì bỏ tool còn lại và
chuyển sang bước cuối; bước cuối hết giờ → `agent_timeout`. Client ngắt: cancel
đi xuyên `stream_reply` → runner → `TaskGroup` của các tool → RunState con →
`QueryAnalyzer`/`Retriever`/`DocChunkRepository`; service ghi `cancelled`,
không ghi `completed`. Tầng agent không tạo task chạy ngầm tách rời.

**Concurrency ba mức.**
1. Tool call trong một response: độc lập theo định nghĩa (LLM chưa thấy kết quả
   của nhau; phụ thuộc thể hiện qua bước sau). Chạy song song bằng `TaskGroup`
   (tối đa `AGENT_PARALLEL_TOOLS`) chỉ khi provider cho phép và mọi tool trong
   batch `read_only` + `concurrency_safe`; ngược lại tuần tự. S# cấp qua
   `SourceAllocator` dùng chung của lượt: không trùng, chunk trùng giữ S#; khi
   song song, thứ tự số theo thứ tự hoàn thành.
2. Nhiều nhân viên: mỗi request có state riêng; provider/retriever không có
   trạng thái. `AGENT_MAX_CONCURRENT_RUNS` giới hạn lượt agent đồng thời mỗi
   tiến trình. Kết nối DB tối đa ≈ số lượt × tool song song × task retrieve: cân
   với `DATABASE_POOL_SIZE`.
3. Cùng một phiên: lease theo phiên (bước 3), 409 `session_busy`.

**`product_docs_ask`.** Chạy `RetrievalPipeline` trên RunState con, có thêm
`CatalogLookupStage` giữa Analysis và Execution (chỉ pipeline của tool, website
không có): `query.origin` = câu hỏi agent viết; history = history phiên + tin
nhắn hiện tại; `pending` bị bỏ; `last_models`/`active_model` của phiên được giữ
để kế thừa model và phát hiện `context_conflict` bằng code. Status: `answered`
(có nguồn), `matched` / `no_match` (tìm model bằng dữ liệu sản phẩm),
`needs_clarification` (candidates gồm `code` + `name`), `no_docs`, `handoff`,
`out_of_scope`, `failed`. Nhóm nguồn ghi `product_models` (model đã lọc khi
retrieve) để agent không gán nguồn của model này cho model khác.

*Tìm model theo tiêu chí (Q1) rồi hỏi tiếp về model đó (Q2).* Sub-query
discovery = `lookup.product_catalog` chưa có model, có `control_interface`,
`excluded_control_interface` hoặc `unmapped_conditions` (analysis schema v3.4,
thêm `interface_match: all|any`). `CatalogLookupStage` lọc bằng
`ProductCatalog` (hiện `RegistryProductCatalog` đọc `REGISTRY["capabilities"]`
— phần cứng **hỗ trợ** gì, khác `coverage` là **có tài liệu** gì; closed world:
mọi model có một dòng) và trả `catalog_match` (`applied`, `unmapped_conditions`,
`models[{code, name, has_technical_docs, documented_interfaces}]`,
`next_action`):

| Kết quả | `next_action` | Retrieval | Model được dùng làm bằng chứng ở Q2 |
|---|---|---|---|
| Điều kiện trong bảng loại hết model | `report_no_match` (status `no_match`) | không | — |
| 1–3 model (`MAX_AUTO_LOOKUP_MODELS`), không có `unmapped_conditions` | `lookup_each` | không | có (`discovered_models`) |
| ≥ 4 model, không có `unmapped_conditions` | `ask_selection` | không | không: lượt sau nhân viên nêu model hoặc "tất cả" (danh sách nằm trong history) |
| Có `unmapped_conditions` | `verify_with_sources` | catalog; lọc theo ứng viên nếu có điều kiện trong bảng, không lọc nếu không có | chỉ model trong nguồn agent trích qua `based_on_sources` |

`no_match` khác `needs_clarification`: dữ liệu xác nhận không có thì báo kết quả,
không hỏi lại. Một interface vừa yêu cầu vừa loại trừ → `unclear_query`.
Trong cùng lần gọi có discovery, sub-query cần model mà model không có trong câu
hỏi của agent (thiếu model, `context_conflict`, so sánh thiếu model, hoặc model
kế thừa từ phiên) được giữ lại với task status `awaiting_models` (không phải câu
hỏi lại nhân viên); agent gọi lại theo `next_action`. Sub-query độc lập có model
riêng (vd. "F86 có bao nhiêu trục? F54 thì sao?") chạy như thường.

*Bằng chứng model.* Model trong câu hỏi của agent phải có trong: tin nhắn hoặc
history của nhân viên, `last_models`/`active_model` của phiên, `discovered_models`
của lượt (`ProductDocsTurnState`), hoặc nguồn trích qua `based_on_sources`
(`models_in_text`, không tính alias mơ hồ). Thiếu → `model_not_evidenced` trước
khi gọi LLM analysis; S# không có trong lượt → `tool_invalid_args`. Guard trong
AnalysisStage vẫn chạy với cùng bằng chứng (`RunState.evidence_models`) để chặn
model LLM analysis tự thêm. `based_on_sources` chỉ kiểm model **có xuất hiện**
trong nguồn, không kiểm nghĩa câu.

- Làm rõ model qua history, không qua `pending`: tool trả
  `needs_clarification` → agent hỏi lại; lượt sau agent gọi lại với mã model
  nhân viên chọn; câu hỏi lại ở lượt trước nằm trong history nên guard giữ được
  model đó.
- `handoff` chỉ là **kết quả nghiệp vụ** (giá, bảo hành… ngoài tài liệu, kèm
  `handoff_reason`); agent không đổi `Mode`, không gọi `HandoffProvider`.
- Lượt agent chỉ cập nhật ngữ cảnh model của `conversation_state`
  (`last_models`/`active_model` từ các lần tra cứu có nguồn, qua
  `product_docs_plans`); không pending, không handoff. Lượt chỉ dùng tool khác
  giữ nguyên ngữ cảnh model.
- Tool có gọi LLM (analysis) vì thuộc tầng agent; quy tắc "handler orchestration
  không gọi LLM" giữ nguyên.

**Persistence.** `retrieval_snapshot` gộp plan của mọi lần gọi tool (task id
`{tool_call_id}:task-retrieve-qN`) và thêm khóa nội bộ `agent_steps` (bước LLM/
tool, trạng thái, latency; không chứa nội dung), `answered_without_tools` (lượt
không gọi tool nào — theo dõi câu trả lời từ trí nhớ) và `invalid_citations`.
`normalized_query` lưu các câu hỏi agent gửi cho `product_docs_ask`. Lỗi agent →
history `error`, SSE `agent_error`.

**`crm_report`** (thử nghiệm, sau cờ `CRM_REPORT_ENABLED`, mặc định tắt). Số liệu
tổng hợp từ CRM theo **semantic catalog**: LLM chỉ chọn tên logic (dataset, metric,
dimension, filter) trong enum; đường dẫn cột, join, filter hệ thống và định nghĩa nghiệp
vụ nằm trong `DatasetSpec`. LLM không gọi API khám phá schema (`/reports/datasets`,
`/reports/tables`), không thấy token, URL hay tên bảng/cột. Bốn dataset:

| Dataset | Nguồn | Quyền CRM | Ghi chú |
|---|---|---|---|
| `tickets` | list_api `GET /api/v1/support/cases` | theo token | Giữ nguồn cũ: cần metric dẫn xuất (thời gian xử lý, tuổi phiếu, `status_group`) mà Reporting API không tính được |
| `customers` | report_api, dataset dựng sẵn `customers` | `customer.read` | Mặc định loại `customer_type` spam/lost (trừ khi lọc/nhóm theo trường này); `assigned_sales` là UUID, `sales_username` = `assigned_sales_id.username`; lọc theo tên/mã/công ty/liên hệ/ghi chú (không nhóm); liệt kê mọi cột nghiệp vụ kể cả liên hệ và ghi chú |
| `support_assignments` | report_api, bảng `support_assignments` | `auth.manage_roles` | Mỗi dòng là một lần giao; khách = thiết bị của phiếu (`case_id.product_item_id.customer_id`); người hiển thị và lọc theo `assigned_to.username` |
| `device_deliveries` | report_api, bảng `product_ownerships` | `auth.manage_roles` | "Bán được" = thiết bị giao cho khách; loại chuyển nhượng (`transferred_from_ownership_id is_null`) |

- LLM chỉ điền `ReportQuery` (`schemas/system/report.py`): `dataset`, `metrics`
  (1–3), `dimensions` (0–2), `filters` (≤8, AND), `date_range` (`preset` hoặc
  `start`/`end` dạng ngày, `end` không bao gồm), `time_grain`, `sort`, `limit`
  (mặc định 10, trần 50). Enum sinh từ catalog (hợp của mọi dataset); LLM không truyền timezone.
- `reporting/validate.py` kiểm tra theo catalog của dataset (operator hợp kiểu,
  giá trị enum, nhãn tiếng Việt, alias model qua `resolve_models`) **trước** khi gọi
  CRM; lỗi → `tool_invalid_args` kèm giá trị hợp lệ để agent tự sửa. Dataset report_api
  chỉ chia kỳ theo các kỳ khai báo (`ReportApiSource.period_dimension`, không có `week`);
  trường string của report_api giữ nguyên hoa/thường (`casefold=False`, SQL so khớp chính xác).
  Trường string có thêm operator `contains` (chuỗi con, không phân biệt hoa thường): list_api
  so khớp `casefold` trong tiến trình; report_api gửi `op: "contains"`, CRM không phân biệt
  hoa thường nhưng **phân biệt dấu** tiếng Việt ("nguyen" ≠ "nguyễn"). Guide của tool yêu cầu
  tìm tên/mã/liên hệ bằng `contains` trên đúng trường đó.
- list_api: `providers/crm_api.py` gọi `GET {CRM_API_BASE_URL}{source_path}?limit=&offset=`,
  lặp tới `total` hoặc `CRM_REPORT_MAX_ITEMS` (`source_truncated`). Item API → record
  (`extra="ignore"`): `subject`, `description` và trường không khai báo bị bỏ ngay khi
  parse. `reporting/engine.py` (hàm thuần): filter hệ thống (`delete_pending = false`) →
  filters + date_range → nhóm theo dimensions (+ kỳ theo `CRM_REPORT_TIMEZONE`) → metric →
  điền kỳ trống bằng 0 và `change.delta`/`delta_pct` → sort (None cuối) → limit.
- report_api: `reporting/report_api.py` (hàm thuần) compile `NormalizedQuery` thành JSON
  của `POST /api/v1/reports/query`: một query cho mỗi nhóm metric cùng filter riêng
  (vd `current_assignment_count` có `is_current = true`), query gốc luôn có `count`
  (`matched_count`); chia kỳ có dimension thêm query `ranking` không chia kỳ để xếp hạng và
  cắt limit theo tổ hợp; `[start, end)` → `from`/`to` bao gồm; mọi value là chuỗi; query có
  dimension gửi `limit` 1000 + `totals`. `CrmReportClient` chạy các query song song
  (`TaskGroup`), rồi `merge_report` ghép theo khóa dimension (nhóm theo UUID, hiển thị
  username/tên), điền kỳ trống và tính delta bằng hàm của engine.
- **CRM phân quyền và giới hạn phạm vi dữ liệu theo token** (`crm_access_token`, trường
  tùy chọn của `/chat/crm`, `SecretStr`, `exclude=True`: không log, không lưu; không có
  token thì Bearer là `acting_user_id`); dịch vụ AI không lọc quyền thêm. 401 →
  `crm_auth_failed`; 403 → `crm_forbidden`; 400 của Reporting API → `crm_report_contract_error`
  (spec do catalog sinh nên đây là lỗi cấu hình, log ERROR, agent không thử lại);
  timeout/5xx/body lạ → `crm_unavailable`.
- `ReportOutput`: `applied` (query đã chuẩn hóa; `system_filters` gồm filter hệ thống và
  filter mặc định đã áp dụng), `rows`, `row_count`, `total_groups`, `matched_count`,
  `fetched_count`/`skipped_count` (list_api; report_api là `null`), `source_truncated`,
  `source` (`list_api` | `report_api`) và `definitions` (cách hiểu cố định của dataset để
  agent nêu đúng một giả định).
- Thêm dataset: khai báo `DatasetSpec` trong `reporting/datasets/` (list_api: record,
  getter, `source_path`; report_api: `ReportApiSource` + `api_path` cho field/metric/cột);
  contract, validate, engine/compile và tool không đổi. Chưa hỗ trợ `having`, OR/NOT, join
  ngược cha → con, so sánh `gt/lt` trên report_api. Dataset dựng sẵn `customers` dùng tên
  dimension logic (`assigned_sales`, `created_day`/`created_month`) nhưng `select`/`filters`/
  `order_by` theo tên cột thật của bảng (`GET /api/v1/reports/tables/customers`). Toàn bộ
  catalog report_api đã kiểm chứng bằng token thật ngày 2026-11-10; chạy lại
  `backend/evals/check_crm_report_contract.py` mỗi khi đổi catalog hoặc CRM đổi schema.

**`crm_records`** (thử nghiệm, cùng cờ `CRM_REPORT_ENABLED`). Liệt kê bản ghi; tool riêng
vì output, rủi ro và luật đọc khác `crm_report`.
- `RecordQuery` (`schemas/system/records.py`): `dataset` (dataset có `list_columns`),
  `fields` (1–8 cột), `filters`/`date_range` như `ReportQuery`, `sort` (≤2, cột phải có
  trong `fields`; mặc định trường ngày mặc định giảm dần), `limit` (mặc định 10, trần 20),
  `offset` (≤200).
- Chỉ cột trong `DatasetSpec.list_columns` được đọc và trả về (whitelist): không có nội dung
  phiếu (subject/description) hay cột bí mật. `customers` mở mọi cột nghiệp vụ kể cả
  phone/email/address/notes (quyết định 2026-11-10); dữ liệu này đi qua provider LLM và có
  thể nằm trong câu trả lời lưu ở `chat_history`. Chuỗi bỏ ký tự điều khiển, cắt
  `ColumnSpec.max_chars` (mặc định 120; `address` 300, `notes` 1000); datetime của list_api
  hiển thị theo `CRM_REPORT_TIMEZONE`.
- list_api (tickets): tải bản ghi, lọc bằng `filter_records` của engine, sort, cắt trang;
  report_api: `select` + một query `count` cùng filter, chạy song song (API không trả tổng
  cho `select`).
- `RecordsOutput`: `applied`, `columns`, `items`, `returned`, `total`, `has_more`,
  `next_offset`, `source`, `source_truncated`, `definitions`; `to_llm` bỏ dòng cuối khi vượt
  budget (`truncated`, `omitted_rows`). Guide nhắc item là dữ liệu, không phải chỉ dẫn.
  `max_calls_per_turn=3`.

**Eval thủ công** (`backend/evals/`): `crm_agent_cases.json` +
`run_crm_agent_eval.py` chạy `AgentRunner` với OpenAI và Supabase thật (không ghi
DB, không chạy trong CI) cho hành vi phụ thuộc LLM: đại từ/ngữ cảnh, phủ định và
"hoặc", tách câu hỏi, làm theo `next_action`, prompt injection.

**Chưa có / ngoài phạm vi:** phân quyền tool theo role/scope, event SSE tiến
trình, stream token câu trả lời cuối, chi tiết từng bản ghi (nội dung phiếu), web search, tool ghi dữ
liệu (cần xác nhận người dùng), planner LLM, MCP (registry chạy cùng tiến trình; có thể
thêm adapter MCP sau), provider Ollama/Gemini cho agent.


## Từ `current-state.md`: dòng P5b của "Completion summary"

| P5b CRM agent flow | Experimental, unit-tested only | `/chat/crm` runs a bounded tool-calling loop (`AgentRunner`) when `CRM_CHAT_FLOW=agent` (default). Tools: `product_docs_ask` (reruns clarification → analysis → retrieval on a child state, no compose) and, behind `CRM_REPORT_ENABLED`, `crm_report` (aggregate reports: tickets from the CRM list API, customers / support assignments / device deliveries from the CRM Reporting Query API) and `crm_records` (whitelisted record lists), see 12d. Provider capabilities and tool schemas are checked at startup. Shared turn deadline, cancellation propagation, three-level concurrency limits and a per-session turn lease (409 `session_busy`) are implemented and tested with fakes only. Hybrid model selection: questions like "which models support EtherCAT? how do I install it?" filter models in code from `REGISTRY["capabilities"]` (`catalog_match` with `next_action` report_no_match / lookup_each / ask_selection / verify_with_sources), and follow-up lookups only accept models backed by evidence (employee message/history, session model context, discovered models, or cited sources via `based_on_sources`). The orchestrator is tool-neutral: shared rules in the system prompt, per-tool rules in `ToolSpec.guide`, per-tool turn state, `deduplicate` and `max_calls_per_turn` per tool. No per-role tool permissions (every CRM employee can use every tool), no SSE progress events, the final answer is one `delta` (no token streaming), no web tools. Not verified against live OpenAI tool calling or Supabase; `chat_sessions.turn_lease_until` must be applied manually. |

## Từ `current-state.md`: việc 12b, 12d, 12a

12b. Product capabilities and model selection (agent flow), known limits:
     - Capabilities live in code (`extraction/registry.py`), closed world: a
       model without an interface is treated as not supporting it. Data comes
       from the product team; changes need a deploy. Move to a database
       repository behind `ProductCatalog` later. Only `control_interface` exists;
       spec values (number of axes, screen size) are not structured yet, so such
       conditions go to `unmapped_conditions` and `verify_with_sources`.
     - `verify_with_sources` relies on top-k chunks: the model list can be
       incomplete, and the 1–3 / ≥4 threshold is only applied through the prompt.
       `based_on_sources` checks that the model appears in the cited source, not
       what the sentence says.
     - "Astro nào hỗ trợ EtherCAT" (family alias as a filter) still asks to
       disambiguate "Astro". No hardware/firmware version entity. Sources carry
       the model filter of their group, not a per-chunk model (`match_doc_chunks`
       does not return `product_models`).
     - LLM-dependent behaviour (negation "không cần" vs "không hỗ trợ", pronouns,
       following `next_action`, prompt injection) is covered by the manual eval
       `backend/evals/run_crm_agent_eval.py`, which has **not been run** yet.
12d. `crm_report` + `crm_records` (experimental, `CRM_REPORT_ENABLED=false` by default).
     Semantic catalog: the LLM picks logical names from enums; join paths, system
     filters and business definitions live in `DatasetSpec` (decision 2026-11-10 with
     Toma: option A, no raw `list_datasets`/`get_table`/`run_query` tools for the LLM).
     Datasets: `tickets` (CRM `GET /api/v1/support/cases`, computed in-process; kept on
     the list API because the Reporting API cannot compute resolution time, ticket age
     or `status_group`), `customers` (CRM curated report dataset, needs `customer.read`),
     `support_assignments` and `device_deliveries` (`product_ownerships`), both raw
     tables that need `auth.manage_roles` on the CRM side. Report datasets compile to
     `POST /api/v1/reports/query` (`reporting/report_api.py`), run in parallel and are
     merged in the AI service (change/delta, empty periods). `crm_records` lists up to
     20 rows per call from a per-dataset column whitelist (no ticket subject/description
     or secrets; `customers` includes contact columns and notes since 2026-11-10), with
     `total` and `next_offset`. Errors: 401
     `crm_auth_failed`, 403 `crm_forbidden` (new; was `crm_auth_failed`), Reporting API
     400 `crm_report_contract_error`, others `crm_unavailable`. Outputs carry
     `definitions` (fixed meaning of "khách của phiếu", "bán được", …).
     Unit tests use fakes (`test_report_api.py`, `test_crm_records_tool.py`); the
     list API path was verified once against the CRM test API (22 tickets). The
     Reporting API catalog was verified over HTTP on 2026-11-10 with
     `check_crm_report_contract.py`: 0 rejected queries for `customers`,
     `support_assignments`, `device_deliveries`. Earlier that day `crm_records` on
     `customers` failed with `crm_report_contract_error` (CRM 400 `unknown select column
     "full_name"`/`"code"`) because the curated `customers` dataset only accepted its
     logical dimensions in `select`; the CRM side then opened raw column names
     (`select`/`filters`/`order_by`, join paths such as `assigned_sales_id.username`,
     schema at `GET /api/v1/reports/tables/customers`). No catalog change was needed.
     Later the same day "có khách nào tên Hohmeier" returned "không có" without any error:
     the catalog had no name filter, so the LLM filtered `source = "Hohmeier"` (seen in
     the stored trace) while CRM has the customer. Fix (decision 2026-11-10 with the
     user: open every `customers` column, contact columns included): string filters gain
     `contains`; `customers` gets text filters (`full_name`, `code`, `company_name`,
     `phone`, `main_phone`, `email`, `main_email`, `address`, `website`, `notes`, not
     groupable), `campaign`, `organization`, `sales_username` (filter + dimension through
     joins), date fields `last_inbound_at`, `assigned_at`, `updated_at`, and 25 list
     columns (contact columns and notes included, `notes` cut at 1000 chars). Customer
     PII now reaches the LLM provider and may be stored in `chat_history` answers. CRM
     `contains` is case-insensitive but accent-sensitive ("nguyen" 7 vs "nguyễn" 47 on the
     test CRM); the tool guide tells the agent to keep the user's spelling and say so on 0
     results. Contract script (now every list column + one `contains` per string field):
     0 rejected queries; the generated "Hohmeier" search returns the customer.
     Assumptions until the CRM team confirms (all written into `definitions` or code
     comments): DB timestamps are Vietnam local time (the API compares calendar dates);
     a case's customer is `support_cases.product_item_id → product_items.customer_id`;
     the curated `customers` dataset names its dimensions `assigned_sales`,
     `created_day`, `created_month` (confirmed by `GET /reports/datasets`); product
     "model" is `products.name`; people are filtered by exact `auth_users.username`
     (no name → UUID lookup API yet; `assigned_sales` is only a UUID). Check with
     `backend/evals/check_crm_report_contract.py` (needs `CRM_EVAL_ACCESS_TOKEN`).
     The CRM bearer is the optional `crm_access_token` of `/chat/crm`
     (kept only in the request principal as `SecretStr`, excluded from dumps,
     logs, `chat_sessions` and snapshots); without it the tools fall back to
     `acting_user_id`, which is logged and stored, so it must not be a secret. The
     widget test route reads the token from `VITE_CRM_TEST_TOKEN`, which is
     bundled into the browser build: test environment only. Ticket status
     `resolved` counts as done (with `closed`). Known limits: tokens are not
     refreshed; `tickets` still re-fetches every ticket the token can see (no cache,
     no filter push-down); `priority`/`category`/`support_mode` are free strings until
     their enums are confirmed; `in_progress` is only updated by CRM when a case page is
     opened; no ticket content/detail, no SLA/overdue, no `having`, OR/NOT or `gt/lt` on
     report datasets, no `week` grain on report datasets; a sales user without
     `auth.manage_roles` only gets `customers` and `tickets` (others return
     `crm_forbidden`). Does the CRM Reporting API block sensitive columns
     (`auth_users.password_hash`, `sessions`…)? Unknown; the AI service never asks for
     them because only catalog paths are sent.
12a. CRM agent flow backlog: per-role tool permissions, SSE progress event,
     token streaming of the final answer, record detail (ticket content), raw report tool
     for admins (option C: whitelisted tables/columns, behind `required_scope`),
     person name → UUID lookup for report filters, write tools with user confirmation, planner step when the tool
     count grows, MCP adapter, Ollama/Gemini capability declarations, live
     verification of OpenAI tool calling and of cancellation reaching asyncpg
     (`pg_stat_activity`).

## Từ `current-state.md`: các mục "Validation record" của luồng agent

- CRM agent flow (`AgentRunner`, `ToolRegistry`, `product_docs_ask`, provider
  capabilities, shared deadline, cancellation, per-session turn lease)
  (2026-10-30): backend pytest **387 passed, 0 failed** (311 existing tests
  unchanged in assertions; `test_chat_routes.py` harness gained a fake lease
  store). `npm run build` passed; `npm run lint` unchanged (139 pre-existing
  errors in `src/`). Live OpenAI tool calling and Supabase: **not verified**.
- Hybrid model selection (capabilities table, `CatalogLookupStage`,
  `catalog_match`, `awaiting_models`, evidence + `based_on_sources`, CRM model
  context, call dedup, citation check, analysis schema v3.4) and tool-neutral
  orchestrator (`ToolSpec.guide`, per-tool turn state, `deduplicate`,
  `max_calls_per_turn`) (2026-10-30): backend pytest **450 passed, 0 failed**.
  Changed assertions in existing tests, all intended: the agent child state now
  sends the session `last_models` to analysis; a model the agent invents is
  rejected with `model_not_evidenced` before analysis (previously
  `needs_clarification` from the guard); an unknown `[S#]` in the final answer is
  removed; the strict tool schema snapshot includes `based_on_sources`; the CRM
  turn now updates `last_models`/`active_model`. `npm run build` passed;
  `npm run lint` unchanged (139 pre-existing errors in `src/`). Live OpenAI and
  Supabase: **not verified**; manual eval not run.
- Trace diagnostics after Toma's case 1 (2026-11-07; `crm_report` with an expired CRM
  token: first call rejected by catalog validation, second call 401). The trace showed
  the flow but not why validation failed, what the LLM asked for, which credential was
  rejected, and `error_spans=5` counted one failure several times. Added: tool span
  `error_detail` (quoted values redacted), `crm_report` query shape +
  `credential_source`, summary `root_error_spans` / `failed_tool_calls`, root
  `tool_errors`, same fields in the `chat_trace` log line. Removed the debug `print`
  of applied report filters in `tools/crm_report.py`. Backend pytest **765 passed,
  14 skipped, 1 failed** (same CRLF-only `test_f86_baseline_csv_unchanged`). Live
  re-run of case 1: pending (Toma).
- CRM Reporting Query API + `crm_records` (2026-11-10, branch `test` from
  `feature/deploy_ai_service`): `CrmReportClient`, `ReportApiSource`/`ColumnSpec` in the
  catalog, `reporting/report_api.py` (compile/merge), `reporting/records.py`, datasets
  `customers`, `support_assignments`, `device_deliveries`, tool `crm_records`, 403 split
  into `crm_forbidden`, `ReportOutput.source`/`definitions` (`fetched_count`/`skipped_count`
  nullable), eval cases r1–r5 + `tools_any`/`datasets_any` in `run_crm_agent_eval.py`
  (`CRM_EVAL_ACCESS_TOKEN`), contract script `evals/check_crm_report_contract.py`.
  Backend pytest **885 passed, 14 skipped, 1 failed** (same CRLF-only
  `test_f86_baseline_csv_unchanged`). Two existing assertions changed on purpose: 403 is
  now `crm_forbidden`, agent setup registers `crm_records`. Frontend untouched;
  `npm run lint`/`build` not run (no `node_modules` in the worktree). Not verified: the
  Reporting API over HTTP, the agent eval cases with live OpenAI.
