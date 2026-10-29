# Kiến trúc và luồng hiện tại

## Phạm vi hệ thống

Project gồm frontend React/Vite tại `src/`, backend FastAPI tại `backend/`,
và Supabase Cloud làm database. Backend là nơi điều phối chatbot; frontend
chỉ tạo request, đọc SSE và lưu `session_id`.

```text
Frontend
  -> FastAPI route/dependency
  -> ChatbotService
  -> SecurityStage
  -> ContextLoader (history + ConversationState)
  -> [mode ≠ bot] câu cố định agent.*, dừng
  -> Prune
  -> ClarificationResumeStage (deterministic, không LLM)
  -> AnalysisStage -> OpenAIProvider (bỏ qua nếu đã resume)
  -> ExecutionStage -> ExecutionScheduler -> handlers (retrieve -> Retriever -> match_doc_chunks)
  -> câu cố định (chitchat/out_of_scope/handoff-only) | AnswerComposer -> OpenAIProvider.stream_chat
  -> HandoffProvider (disabled) + update_conversation_state
  -> HistoryRepository -> Supabase public.chat_history
  -> SSE về frontend
```

## Startup và dependency

`backend/app/main.py` cấu hình logging, tạo FastAPI app, đăng ký CORS, include
`backend/app/api/v1/router.py` và bọc ngoài cùng bằng `RequestContextMiddleware`
(request ID, access log có `outcome`). Lifespan tạo `OpenAIProvider` khi có
`OPENAI_API_KEY`, lưu provider vào `app.state` và đóng provider khi shutdown.

Module chatbot (`backend/app/modules/chatbot/`):

```text
routers/      chat.py (POST /chat/*), workspace.py (GET /chatbot/*), sse.py (SSE + map lỗi)
dependencies.py  service/repository, RequestContext, auth theo kênh, Idempotency-Key
services/     chat_service.py (ChatbotService), session_access.py, service_auth.py
adapters/     website.py, crm.py: schema kênh -> InboundRequest
repositories/ history_repository.py, chat_session_repository.py, doc_chunk_repository.py
```

Router không tự khởi tạo provider hoặc repository.

## Ba thành phần khi chạy

```text
Trình duyệt (widget src/chatbot)
  └─ cookie HttpOnly qs_visitor, qs_chat_session ─▶ widget-backend/ (Node, :8787)
       └─ Bearer qsk_… (key kênh website) + {session_id, message} ─▶ backend/ dịch vụ AI (:8000) POST /chat/website
CRM backend ─ Bearer qsk_… (key kênh crm) + {user_id, session_id, message} ─▶ dịch vụ AI POST /chat/crm
```

- **Dịch vụ AI** (`backend/`): chỉ xác thực service key và xử lý chat; không
  biết khách website.
- **widget-backend** (`widget-backend/`): giữ `CHATBOT_API_KEY`, cấp
  `visitor_id` ẩn danh, giữ `session_id` trong cookie HttpOnly (đọc từ header
  `X-Session-ID`), chuyển tiếp SSE và gỡ `session_id` khỏi event `done`.
- **Widget** (`src/`): chỉ gọi `/api/chat` và `/api/chat/history` cùng origin
  (Vite proxy `/api` khi dev). Support Workspace vẫn gọi thẳng GET
  `/chatbot/...` của dịch vụ AI (chưa xác thực).

## Luồng `POST /chat/website` (và `POST /chat/crm`)

1. Middleware chốt `request_id`. Dependency dựng `RequestContext` (channel do
   endpoint quyết định), xác thực service key qua `ServiceAuthService` (key phải
   được cấp cho kênh của endpoint) và đọc `Idempotency-Key`. Với CRM, router gắn `user_id` của body vào principal bằng
   `PrincipalContext.acting_for()`.
2. Router parse schema kênh (`WebsiteChatIn`/`CRMChatIn`); Pydantic kiểm tra
   schema version, `session_id` UUID, giới hạn text và client context. Nếu chưa
   cấu hình provider, trả HTTP 503.
3. `SessionAccessService` tạo session mới thuộc principal (`chat_sessions`)
   hoặc chỉ dùng lại session cùng chủ, cùng kênh, chưa revoked/expired; còn lại
   trả 404 `session_not_found`. Server sinh `message_id`; adapter dựng
   `InboundRequest` nội bộ (strict), service nhận kèm `PrincipalContext` và
   `RequestContext` trong `RunState`.
4. `SecurityStage` normalize nội dung, chạy `InjectionGuard` và `ContentPolicy`.
   Nếu block, service ghi audit `status='blocked'` bằng session database riêng,
   không chạy context/provider, rồi router phát SSE `error`.
5. `ContextLoader` đọc history `status='completed'`, tạo `RunContext` gồm
   conversation, query và retrieval scope. Website hiện map tới cả
   `crm-technical` và `crm-sale`. `ConversationState` (pending clarification,
   `clarify_attempts`, `last_models`, `mode`, `ticket_id`) được đọc từ cột
   `conversation_state` của row completed gần nhất; dữ liệu sai schema thì dùng
   state mặc định. Nếu `mode ≠ bot` (đã chuyển nhân viên), service trả câu cố
   định `agent.awaiting`/`agent.active`, ghi history và **không** chạy
   analysis/LLM.
6. `Prune` áp dụng context token budget, giữ query/summary và bỏ các history
   turn cũ trước; lỗi budget/config là domain error, không phải security block.
7. `ConversationState` mang `last_models` (cộng dồn, cũ → mới, tối đa 4) và
   `active_model` (model duy nhất của lượt gần nhất; `None` sau lượt có ≥ 2 model;
   giữ nguyên sau lượt không nhắc model). Câu thiếu model kế thừa
   `active_model` trước, rồi mới xét `last_models`. `<state>` gửi LLM gồm cả hai
   để hiểu "nó" (active) và "các model trên" (last_models).
   Vòng làm rõ (`clarification/`):
   - `ClarificationResumeStage` chạy trước analysis. Nếu có pending và câu trả
     lời ngắn khớp chắc chắn (alias model, số thứ tự, "đúng/vâng" khi chỉ có
     một gợi ý, hoặc một mã giống model như "A10"), nó vá raw sub-query đang
     bị giữ (`patch_pending`) và dựng lại analysis bằng `resolve` +
     `plan_turn`, **không gọi LLM**.
   - Nếu không khớp, `AnalysisStage` gọi `QueryAnalyzer` với `<pending>` trong
     context. Output strict có thêm `pending_answer`; khi có giá trị, các ý bị
     giữ đã vá được ghép trước các sub-query mới.
   - Sau `clarify_attempts >= 2` lần hỏi mà vẫn chưa rõ, các ý bị giữ chuyển
     sang `no_docs` (`clarification_exhausted`) và pending bị xóa.
   - Câu trả lời là câu hỏi mới: pending giữ lại với `ttl` giảm dần (mặc định 2).
   - Câu trả lời không trích được gì (LLM trả `sub_queries=[]`, không có
     `pending_answer`, vd. "ok" khi có nhiều gợi ý): giữ lại các ý đang chờ và
     hỏi lại, tính một lần thử.
   - Câu cần đúng một model mà chưa có model (`resolve_sub_query`, có
     `last_models`): `model_dependency=general` → retrieve không lọc model,
     `answer_mode=general`, hỏi model ở cuối (không chặn); `last_models` có 1
     model → kế thừa (warning `inherited_model:X`); ≥ 2 model →
     `context_conflict` với candidates = `last_models`; không có →
     `missing_product_model` với candidates = model có tài liệu cho domain đích.
     Câu trả lời chung kết thúc bằng câu hỏi model tạo pending **không chặn**
     (`blocking=false`): trả lời mã/alias/số thứ tự sẽ tra cứu lại theo model đó;
     "ok/đúng" không kích hoạt (xử lý như chitchat).
     Model nêu ở lượt hiện tại luôn được ưu tiên. Cờ `general` của LLM chỉ được
     nhận khi intent có `allow_general` (mặc định có; `guide.installation` và
     `troubleshoot.error` thì không) và `standalone_query` không nhắc mã cụ thể
     (`MODEL_SPECIFIC_PATTERN`: CN1, X40, #4130, AL12, E05).
   - `guard_extracted_models` loại model LLM trả về mà mã/alias không có trong
     câu hỏi, lịch sử hay `last_models` (warning `model_not_in_text:X`), để không
     âm thầm đổi F84 thành F86.
   - Lỗi analysis/execution/compose được ghi history `error` và trả SSE
     `analysis_error`.
8. `ExecutionStage` tạo execution plan từ analysis và chạy plan qua
   `ExecutionScheduler` với các handler deterministic trong
   `orchestration/handlers.py`. Các handler này không gọi LLM:
   - `chitchat` và `out_of_scope` trả về `completed`.
   - `no_docs` trả về `completed`, kèm `unsupported_models`.
   - `handoff` trả về `handed_off`, kèm `handoff_reason`.
   - Planner **giữ** (`held_sub_query_ids`) các sub-query có clarification
     chặn hoặc có chung mention với clarification của lượt (vd. "F84 khác gì
     F54" khi F84 đang chờ làm rõ). Chúng thành task `clarify` `blocked`
     (`reason=task_blocked`) và không được tra cứu; các ý đã rõ vẫn
     chạy ngay.
   - `retrieve` (mức kiểm thử): planner tạo **một task cho mỗi sub-query**
     (`task-retrieve-{id}`), không gom theo `analysis.batches`, để các intent
     khác nhau không dùng chung scopes hợp nhất; scheduler chạy song song.
     Khi `Retriever` được inject (`main.py` → `app.state.chatbot_retriever`),
     `handle_retrieve` dựng `RetrievalRequest` cho từng target/fallback target
     và gọi `Retriever.search`. Không có retriever thì task `failed` với
     `handler_not_configured`; lỗi embedding/DB thì `failed` với
     `retrieval_error`; không có chunk liên quan thì `completed` kèm
     `metadata.no_hits`.

   Ranh giới trách nhiệm của tầng retrieve (filtered hybrid retrieval):

   | Thành phần | Trách nhiệm |
   |---|---|
   | `handle_retrieve` (`orchestration/handlers.py`) | Task → `RetrievalRequest`, trạng thái và lỗi task |
   | `Retriever.search` (`retrieval/retriever.py`) | Embedding câu hỏi, lặp targets, fallback khi không có chunk vượt `RETRIEVAL_MIN_SIMILARITY`, tách từng model khi `comparison`, gộp/dedupe, cắt `RETRIEVAL_FINAL_CHUNK_TOP_K`, mở rộng sang chunk cha (tối đa `RETRIEVAL_MAX_CONTEXT_PARENTS`), dựng `RetrievalTrace` |
   | `DocChunkRepository` | Session riêng cho mỗi lời gọi (task chạy song song), gọi SQL function |
   | `match_doc_chunks` (`backend/sql/doc_chunks.sql`) | Lọc `is_active`, `domain`, `scopes &&`, `product_models &&`, `control_interface` (rỗng = áp dụng chung); vector top-k + FTS (`embed_text`, OR) top-k; RRF; `spec_attributes` chỉ cộng điểm |
   | `ExecutionStage.assign_source_ids` | Gán `S#` theo thứ tự task sau khi mọi task xong; chunk trùng giữa sub-query dùng chung `S#`; đánh `selected` cho candidate và ghi trace vào `RunState` |
   | `AnswerComposer` | Block `<sources>` theo từng sub-query; prompt yêu cầu trích `[S#]` |

9. Lượt chỉ gồm `chitchat`/`out_of_scope`, hoặc chỉ gồm `handoff`, trả câu cố
   định từ `prompts/direct_responses.py` (theo `handoff_reason`) và không gọi
   `AnswerComposer`, **nếu** ngôn ngữ trả lời có bản soạn sẵn (vi, en). Ngôn ngữ
   khác đi qua `AnswerComposer`.

   Đa ngôn ngữ: analysis trả `language` (ISO 639-1) và `standalone_query` luôn
   bằng tiếng Việt (embedding/FTS chạy trên `embed_text` tiếng Việt). Ngôn ngữ
   trả lời = `analysis.language` → `ConversationState.language` (lượt resume
   không gọi LLM) → locale client → `vi`; được gán vào `query.language`, gửi cho
   `AnswerComposer` qua `<language>` và lưu vào `ConversationState.language`.
   Câu trả lời trước analysis (bị chặn, `agent.*`) dùng ngôn ngữ của phiên →
   locale → `guess_reply_language` (heuristic dấu/từ tiếng Việt, mặc định `en`).
   `chat_history.normalized_query` lưu các `standalone_query`.
   Các lượt khác: `AnswerComposer` gom kết quả bằng `collect_results`, dựng messages gồm
   system prompt, history, `<query>`, `<task_results>` và `<clarification>`
   (nếu có), rồi stream câu trả lời qua `provider.stream_chat`. Mỗi lượt chỉ
   gọi LLM một lần cho câu trả lời cuối. Nếu có task retrieve, messages có thêm
   `<sources>` (nội dung chunk cắt theo `source_char_limit`). Sau khi stream xong,
   service ghi history `status='completed'`. Sources/assets chưa được gửi về
   frontend qua SSE và `retrieved_chunk_ids` chưa được ghi.
   Sau khi trả lời, nếu có task `handed_off` thì gọi `HandoffProvider`. Hiện chỉ
   có `DisabledHandoffProvider` (không ticket, giữ `mode=bot`); chưa nối API
   bên ngoài, chưa chuyển tiếp tin nhắn cho nhân viên và chưa có cơ chế trả về
   `mode=bot`. `update_conversation_state` tính state mới và lưu vào cột
   `conversation_state` của row `completed`.
10. Router phát event `done` với `request_id` và authoritative `session_id`.
    Frontend lưu session ID trong localStorage cho request sau.
11. Context/domain/provider exception được log server-side và ánh xạ thành SSE
    `context_error` hoặc `provider_error`.

## Persistence và session

- `HistoryRepository` là ranh giới database và ánh xạ
  `public.chat_history`.
- History thành công (completed) được dùng lại cho context; blocked/error/cancelled
  không được đưa vào context. `blocked` và `cancelled` (client ngắt kết nối giữa
  lượt) được ghi bằng `create_audit` với session DB riêng, commit ngay.
- `conversation_state` đọc từ lượt completed gần nhất qua
  `load_conversation_state`: bỏ field không còn trong schema, rồi bỏ từng field
  không hợp lệ (giữ `mode`, `ticket_id`… nếu đọc được) thay vì reset toàn bộ;
  log WARNING kèm `session_id` và tên field bị bỏ.
- `retrieval_snapshot` ghi thêm `retrieval_status` và `retrieval_tasks` để truy vết
  lỗi tra cứu (khách không nhận mã lỗi cho trường hợp này).
- `ChatSessionRepository` ánh xạ `public.chat_sessions` (chủ sở hữu session).
  `POST /chat/*` chỉ dùng lại session cùng principal và kênh. Các GET
  `/chatbot/sessions/{session_id}/...` và `/chatbot/conversations` (Support
  Workspace) **chưa** kiểm ownership.
- `message_id` do server sinh là `chat_history.id`; `Idempotency-Key` được lưu
  vào `chat_history.idempotency_key` nhưng chưa chống xử lý trùng. Concurrent
  request cùng session chưa có ordering guarantee.

## Các lớp và trách nhiệm

| Lớp | Trách nhiệm | Không nên làm |
|---|---|---|
| API router | HTTP/SSE transport, dependency wiring, error mapping | Gọi LLM, chứa detector/business rule |
| Schema | Contract version, validation, giới hạn input | Quyết định orchestration |
| `ChatbotService` | Điều phối session và stages, lifecycle history | Chứa provider implementation |
| Stage | Một bước domain có typed state/decision | Tạo HTTP response |
| Provider | Adapter cho OpenAI/LLM | Policy/security/routing |
| Repository | Query/write Supabase | Trả SSE hoặc biết UI |
| Frontend service | POST và parse SSE | Tự quyết định trạng thái backend |

## API surface hiện tại

Đang public: `GET /health`, `GET /health/db`, `POST /chat/website` và
`POST /chat/crm` (service key server-to-server, đúng kênh)
và các GET `/chatbot/...` của Support Workspace. Module `learning_ai` cung cấp
`POST /ai/learning` và các endpoint support-chat khi `LEARNING_API_ENABLED=true`
(xem mục dưới). Quyền nhân viên CRM theo `user_id`, ownership cho các GET history, chống xử lý trùng
theo `Idempotency-Key` và production readiness/schema checks là phạm vi chưa
hoàn thiện.

## Luồng học tri thức (`learning_ai`): thiết kế và trạng thái

Mục tiêu: biến hội thoại hỗ trợ / tài liệu thành `KnowledgeRecord` có cấu trúc,
được người duyệt, rồi chia chunk và index cho chatbot truy xuất. Module nằm ở
`backend/app/modules/learning_ai/`.

**Trạng thái tổng quát:** phần lõi domain thuần (schema, validate, conflict rule,
lifecycle, chunking, indexer logic) đã có và có unit test tại
`backend/tests/learning_ai/`. **Chưa có entrypoint nào chạy luồng end-to-end.**
Chưa có API thật, ingestion, lời gọi LLM, persistence Supabase, outbox, embedding
hay vector index.

```text
[0] POST /ai/learning                 chạy [1]; chỉ include khi LEARNING_API_ENABLED=true, chưa có auth
[1] Ingestion -> SourceDocument       có logic + service (chưa có bảng job, chưa nối route)
      prefilter -> privacy A..D       Ollama bắt buộc, fail-closed (xem mục Privacy bên dưới)
[2] Pass 1 Segmenter (LLM)            chỉ có schema Segment/SegmentationOutput
[3] Pass 2 Extractor (LLM, strict)    có schema + to_strict_schema (inject enum registry);
                                      chưa có prompt/provider call
[4] assemble_draft -> DRAFT record    có logic (hệ thống gán ID/provenance/privacy/source_id)
[5] validate_record                   có logic: locator bịa, basis<->role, mã registry,
                                      classification<->content, registry drift
[6] detect_rule_conflicts             rule cho parameter/spec/wiring có;
                                      so sánh ngữ nghĩa + tra candidate từ DB chưa có
[7] Review lifecycle + approval_gate  có logic thuần; chưa có persistence/API/UI review
[8] Outbox -> sync_record             build_chunks + embedding_text + upsert idempotent có;
                                      Embedder/SearchIndex chỉ là Protocol, chưa có outbox
[9] Chatbot retrieval theo ChunkFilters  chưa nối
```

| File | Vai trò |
|---|---|
| `schemas/knowledge_record.py`, `content.py`, `common.py` | Record chuẩn, content theo 5 loại (wiring, procedure, parameter_config, troubleshooting, spec_fact), Claim có basis + evidence |
| `schemas/llm_output.py` | DTO đầu ra LLM 2 pass và chuyển Pydantic sang JSON Schema strict |
| `schemas/registry.py` | `RegistrySnapshot` dùng chung với query extraction |
| `extraction/assembler.py`, `validators.py` | Ghép DTO thành draft, kiểm tra deterministic hậu-LLM |
| `review/conflict_detector.py`, `lifecycle.py` | Xung đột theo luật, state machine, approval gate, revision bất biến |
| `chunking/*`, `indexing/indexer.py` | Chunk theo loại tri thức, embedding text, đồng bộ index idempotent |
| `repositories/support_chat_repository.py` | Đọc session và message từ `public.support_chat_test_sessions` / `public.history_support_chat` theo `message_no` |
| `ingestion/source_document.py`, `prefilter.py`, `service.py` | Dựng document có locator, lọc hội thoại vô giá trị, điều phối nạp → lọc → privacy |
| `privacy/*` | Regex PII/giá, chia cửa sổ, kiểm tra bằng Ollama, thay placeholder |

### Nguồn và ingestion

Nguồn là hội thoại CRM giữa nhân viên thật và khách trong
`public.history_support_chat` (`id`, `session_id`, `message_no`, `sender_role`,
`message_text`, `created_at`) tham chiếu `public.support_chat_test_sessions`.
Bảng do Supabase quản lý; ứng dụng đọc qua repository. Mỗi row là một message;
locator `m1..mN` liên tục theo `message_no`, message rỗng bị bỏ. `source_id` là UUIDv5 của
`session_id` + hash nội dung, nên ổn định khi nội dung không đổi.

Prefilter chạy trước mọi lời gọi model và chỉ skip khi chắc chắn: thiếu tin nhắn
khách, thiếu tin nhắn nhân viên, mọi message chỉ gồm từ chào hỏi/cảm ơn/xác nhận/đại
từ, hoặc nội dung có nghĩa dưới 40 ký tự. Một message có bất kỳ từ khác, chữ số hoặc mã
registry thì không bị coi là chào hỏi ("xin chào, tôi cần giới thiệu về F86" được giữ).

`LearningIngestionService.prepare(session_id)` trả `IngestionResult` với status
`ready | skipped | privacy_unavailable`. Kết quả chưa được lưu lại vì chưa có bảng job.

### Privacy (bắt buộc trước khi dữ liệu rời server)

```text
A  regex       email, SĐT, IPv4, CCCD/CMND/MST/STK (chỉ khi có từ khoá), giá
B  Ollama      theo cửa sổ: PII phi cấu trúc + pricing / policy / customer_specific
C  redactor    kiểm span có thật, thay placeholder; thực thể PII thay ở MỌI message
D  regex lại   trên kết quả cuối, che nốt nếu còn sót
```

- Ollama nhận text đã che ở tầng A. Model chỉ báo cáo
  `{reviewed_locators, findings[{locator, category, type, text}]}`; hệ thống quyết
  định hành động: `pii` và `pricing` bị thay placeholder (`[PERSON_1]`, `[PRICE_1]`),
  `policy` và `customer_specific` giữ text, gắn cờ trong `flags_by_locator`.
- Fail-closed: provider lỗi, output sai schema, hoặc `reviewed_locators` thiếu message
  mục tiêu → cả document `privacy_unavailable`, không có kết quả một phần.
- Finding có `text` không phải chuỗi con nguyên văn, hoặc locator ngoài cửa sổ, bị loại
  và đếm vào `unverified_findings`.
- Hội thoại dài: gom message nguyên vẹn tới `OLLAMA_WINDOW_TOKENS` (tiktoken × 1,5), kèm
  2 message trước làm ngữ cảnh, và gửi danh sách thực thể đã tìm thấy sang cửa sổ sau.
  Endpoint OpenAI-compatible của Ollama không đặt được `num_ctx` theo request: phải
  đặt `PARAMETER num_ctx` trong Modelfile và khai báo `OLLAMA_NUM_CTX` khớp. Provider
  coi prompt chạm 95% `num_ctx` là đã bị cắt. Kiểm tra `reviewed_locators` là chốt
  chặn cuối khi giá trị cấu hình lệch với Modelfile.
- Regex giá phân biệt đơn vị tiền rõ nghĩa (đ, đồng, vnđ, usd, $), đơn vị số lượng
  (ngàn, nghìn, triệu, tỷ, củ — bỏ qua khi theo sau là danh từ kỹ thuật như "xung",
  "vòng"), đơn vị mơ hồ (k, tr) và tiếng lóng (lít, xị — cần từ khoá giá).
- Thay thế toàn document không phân biệt hoa/thường, ưu tiên không lọt hơn chính xác.
  Giá trị gốc của placeholder không được lưu.

Giới hạn đã biết của thiết kế hiện tại:

- `chatbot/extraction/registry.py` chưa có các key `topics`, `connectors`,
  `parameters`, `alarm_codes` mà `FIELD_TO_REGISTRY_KEY` cần, nên với registry thật
  `validate_registry` sẽ báo `unknown_code` cho các trường này.
  `learning_ai/extraction/registry.py` đang là file rỗng.
- `approval_gate` không tự chạy `validate_record` / conflict detection; service
  điều phối (chưa có) phải bảo đảm thứ tự đó.

Khi thay đổi flow, cần cập nhật đồng thời schema/API contract, service/stage,
repository/provider boundary, test và tài liệu này. Không mô tả scaffold hoặc
stub như tính năng đã sẵn sàng.
