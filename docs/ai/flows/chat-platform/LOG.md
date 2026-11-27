# Nhật ký chat-platform

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-07 (nguyên văn từ `current-state.md` và `architecture.md`, gồm Finding
status, API gateway, service key, lease, tracing): [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## 2026-11-27 · Dọn code thừa và trùng ở backend (kiểm duyệt toàn backend) · loại: thay đổi, đánh giá

- Vấn đề: kiểm duyệt `backend/` thấy file không ai gọi, import và setting chết, cấu hình và code trùng giữa các tool crm-agent, repository và tính phí ước tính.
- File xóa: `app/chunking/embedding_chunks.py`, `chunking_loader/import_chunk.py` (hỏng, thiếu `import os`), `chatbot/providers/100millionseek.py`, `chatbot/analysis/context_builder.py` (có `NameError`, bản sống là `AnalysisStage.build_context_analysis`), `util/uuid_generate.py`. Mỗi file đã grep: 0 tham chiếu trong `app`, `tests`, `scripts`, `evals`, docs đang dùng.
- File sửa: bỏ setting `EMBEDDING_INPUT_USD_PER_MILLION`, `AGENT_HISTORY_MESSAGES`, `GPT4O_MINI_*_USD_PER_MILLION` (`Settings.extra="ignore"` nên `.env` cũ vẫn chạy); `ChatbotService._usage` ước tính chi phí qua `core/pricing.price_for/cost_usd` (model lạ tính như gpt-4o-mini; với model mặc định kết quả không đổi); `TRUNCATION_MARGIN_TOKENS` về `tools/base.py`; mixin `repositories/session_factory.py` thay 3 bản `_session()`; gỡ 6 import thừa; tách `pytest` sang `requirements-dev.txt`.
- Test thêm: `tests/chatbot/test_normalize_code_parity.py` (30 ca, chặn `normalize_code` của chat và doc-ingest lệch nhau).
- Kiểm chứng: `pytest tests --ignore=tests\doc_ingest` → 863 passed, 7 failed (cùng 7 test fail trước khi sửa: `test_cancelled_turn`, `test_chat_routes`, `test_crm_agent_flow`, 3 trong `test_sources`, `test_documents_api`); `tests\doc_ingest` (venv ingest) → 454 passed; `import app.main` chạy được.
- Ảnh hưởng contract/API/schema: không. Biến môi trường bỏ đi chỉ bị bỏ qua.
- Mở tiếp: chưa làm (cần quyết định thiết kế) — router import repository và gọi thẳng, 5 chỗ khởi tạo client LLM, 3 chỗ gọi CRM bằng httpx, `repositories` import `services.conversation_filters`; còn `stages/default.py` (được `security-stage-pipeline.md` nhắc như scaffold), `backend/eval/`, `load_csv.py`, `spike/`, manifest legacy, scaffold `review/approval.py`, `doc_chunks.sql` v1.

## 2026-11-25 · Lượt lưu độ khớp, tham chiếu ảnh và mã lỗi; ảnh ký lại khi đọc; `done.history_id` (WU-17 đợt 2) · loại: thay đổi, quyết định

- Vấn đề: ảnh nguồn mất sau tải lại (URL ký 15 phút không lưu), độ khớp hiện điểm RRF ~0,03, lượt lỗi chỉ biết nguyên nhân
  khi có trace, client CRM không biết mã lượt để mở Workspace (đề xuất của Toma, workspace-ui LOG 2026-11-25).
- Quyết định: độ khớp = cosine × 10, thang tuyệt đối (Toma duyệt 2026-11-25). Lượt lưu tham chiếu ảnh, không lưu URL.
- Thay đổi (chỉ thêm khoá, không cần SQL: `retrieval_snapshot` là jsonb):
  - `ChunkHit.similarity` = cosine lớn nhất của chunk con (`retriever.py`); snapshot chunk thêm `similarity`, `assets`.
  - Lượt `error`: `snapshot.error = {stage, code, provider_code, http_status}` (`services/turn_errors.py`, chỉ định danh,
    duyệt chuỗi `__cause__`; lượt lỗi chưa có state vẫn có snapshot tối thiểu).
  - `GET /history`: mỗi lượt có `error`, `cited_sources` (dựng từ snapshot, ảnh ký mới, một lần gọi Storage cho cả trang);
    `GET /retrieval`: `chunks[].similarity`, `chunks[].images`, `error`. Ký ở `sources.py` (`attach_history_sources`,
    `attach_chunk_images`), router chỉ gọi; signer qua `dependencies.get_asset_signer` (None khi cờ tắt → không ảnh).
  - SSE `done` thêm `history_id` (= `message_id`); widget-backend giữ nguyên (chỉ gỡ `session_id`).
  - `api_guidelines.md` cập nhật (TR-06). Test: `tests/chatbot/test_sources.py` +4.
- Kiểm chứng: `pytest tests` (DATABASE_URL giả) → 1221 passed, 14 skipped, 1 failed có sẵn (`test_f86_baseline_csv_unchanged`,
  CSV CRLF trong worktree); `widget-backend` `npm test` → 22 pass.
- Ảnh hưởng contract: có, chỉ thêm khoá (`done.history_id`, `/history` `error`/`cited_sources`, `/retrieval` `similarity`/
  `images`/`error`); client cũ không đổi.
- Kiểm thật (2026-11-25, backend chạy từ worktree + Supabase dev, `CHAT_SOURCES_ENABLED=true`): Toma chạy
  `publish-assets --apply` F54 Installation `crm-1.4-a` → 16 ảnh `published` (bucket `doc-assets`). Lượt website
  `bd147866-…` (phiên `ed3e05c2-…`): `done` có `history_id`; `/history` có `cited_sources` (S1, tr. 11); `/retrieval`
  5 đoạn có `similarity` 0,57–0,75 (RRF 0,019–0,034), ảnh ký mới cho đoạn có ảnh (S2: 2, S5: 3, tải được); Workspace
  hiện "7,0/10"… và ảnh. Đoạn trúng chủ yếu từ `f54_operation_v02` (bản thử cũ, bucket `f54-docs`); đoạn của
  `f54-installation-en` (S4) không có ảnh trong DB.
- Chưa kiểm / mở tiếp: chưa thấy ảnh `doc-assets` trong lượt thật (chunk CRM trúng không mang `assets`; kiểm cột `assets`
  của 847 chunk CRM đã nạp); chưa kiểm `error` trên lượt lỗi thật. Lượt ghi trước 2026-11-25 không có similarity/ảnh/mã
  lỗi. Chưa commit.

## 2026-11-21 · SQL `doc_chunks_v2`: cột `audience`, tham số `p_audiences` (D-014) · loại: thay đổi

- Vấn đề: cần chặn chunk nội bộ khỏi kênh website ở lớp dữ liệu (chi tiết và quyết định: website-qa LOG 2026-11-21, D-014).
- Quyết định/luật: cột `audience` (check `public|internal`, mặc định `internal`); bảng đã tồn tại thêm cột với mặc định `public` rồi đổi
  mặc định về `internal` (dòng đã nạp đều là tài liệu công bố); `match_doc_chunks_v2` thêm `p_audiences text[] default array['public']`, lọc ở ba nhánh.
- File: `backend/sql/doc_chunks_v2.sql`, [deploy-rules.md](../../rules/deploy-rules.md) (hàng SQL số 6).
- Kiểm chứng: chỉ test phía Python (fake session, kiểm tham số và chuỗi SQL); **SQL chưa chạy trên Supabase**. Kiểm sau khi áp:
  `select audience, count(*) from doc_chunks_v2 group by 1` phải ra toàn `public` cho dữ liệu hiện có.
- Ảnh hưởng contract/API/schema/cấu hình: đổi chữ ký hàm SQL; áp SQL trước khi deploy, nếu không retrieval lỗi vì thiếu tham số `p_audiences`.
- Chưa làm / mở tiếp: áp SQL; giai đoạn B (bucket private, ký URL, SSE `sources`) sẽ đổi `api_guidelines.md`.

## 2026-11-20 · ContextLoader chỉ đọc 10 lượt gần nhất; `conversation_state` có thêm `facts` (D-015) · loại: thay đổi

- `HistoryRepository.list_for_context(limit)`: `CONTEXT_HISTORY_TURNS` (mặc định 10) lượt `completed` gần nhất, thứ tự
  cũ → mới; trước đây đọc cả phiên. `conversation_state` của lượt agent có khoá `facts` (định danh do tool trả); đọc
  state cũ không có khoá này vẫn đúng, `facts` hỏng bị bỏ riêng. Không cần SQL.
- Chi tiết: [crm-agent LOG](../crm-agent/LOG.md) mục "Gói A"; quyết định D-015.

## 2026-11-20 · B3 đọc usage từ sổ của trace, không mất khi vượt trần span · loại: thay đổi

- B3 cộng usage từ span nên span bị bỏ vì vượt `CHAT_TRACE_MAX_SPANS` không được tính, lời gọi hết
  giờ/bị huỷ không ghi gì. Nay `OpenAIProvider` ghi `Trace.usage` cho mọi lời gọi; `usage_by_model`
  đọc sổ (rỗng thì đọc span như cũ); lời gọi bị ngắt ghi ước tính, đếm ở `usage.estimated_calls`
  (snapshot và `/history`). History ghi `AGENT_MODEL` ở lượt CRM chạy agent.
- Chi tiết, file, kiểm chứng: [crm-agent LOG](../crm-agent/LOG.md) mục 2026-11-20 (Đợt 0).
- Kiểm chứng: `pytest tests` → 1107 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Chưa merge.

## 2026-11-18 · B2: bảng tóm tắt hội thoại, tìm không dấu, phân trang (Q29, Q30) · loại: thay đổi

- Vấn đề: danh sách hội thoại chạy window function trên toàn `chat_history` và đọc JSON mỗi request
  (100.000 lượt: vài giây); tìm kiếm chỉ trên lượt cuối, phân biệt dấu, không escape; số liệu không
  theo bộ lọc (F8); không phân trang.
- Quyết định/luật (Toma duyệt cách kết hợp Q30 và phạm vi tìm Q29):
  - Python tính cờ của lượt (`turn_sources.turn_flags`: `has_tool_errors`, `is_handoff`,
    `product_models`, `ticket_id`) và ghi vào cột mới của `chat_history` ở cả 4 nhánh ghi;
  - trigger `AFTER INSERT` chỉ cộng dồn vào bảng `chat_conversations` (`sql/chat_conversations.sql`),
    `NOWAIT`, bắt mọi lỗi để không làm hỏng việc ghi lượt; `rebuild_chat_conversations()` phát lại qua
    cùng hàm; rủi ro R1–R10 ở FRONTEND_REQUIREMENTS 19.11;
  - `GET /chatbot/conversations` đường B2 (`q`, `status=handoff`, `channel`, `product_model`,
    `from`/`to` giờ Việt Nam, `limit`, `cursor` keyset gắn dấu bộ lọc, `match`); không gửi tham số mới
    thì như cũ (`/legacy`);
  - `/conversations/metrics`, `/conversations/{id}` sau `WORKSPACE_CONVERSATION_API_ENABLED` (TR-16);
  - `/history` thêm `limit`/`cursor`, `asked_at`, `answered_at`, `turn_number`, `has_trace`;
  - bỏ `cost_source` của `/metrics` (spec 19.5 ghi lý do).
- File: `sql/chat_conversations.sql`, `db/models/history.py`, `repositories/{history,conversation}_repository.py`,
  `services/{turn_sources,conversation_filters,conversation_views,chat_service}.py`, `routers/workspace.py`,
  `api/v1/router.py`, `core/config.py`, `scripts/{backfill_history_flags,check_conversation_summary}.py`;
  test `test_conversation_api.py` (mới), `test_turn_sources.py`, `test_history_api.py`.
- Kiểm chứng: Toma áp SQL, chạy điền cờ (222 lượt, 169 lượt lệch được ghi), `rebuild_chat_conversations()`,
  script so lệch → "Khớp" (14 phiên). API thật: tìm không dấu/đảo thứ tự/đ, phân trang 5 dòng duyệt đủ 14
  phiên không trùng, lọc 7 ngày (3 phiên, khớp `/metrics`), lỗi ngày và cursor → 422, `/history?limit=3`
  đánh số 93–95 rồi 90–92. `pytest tests` → 1071 passed, 14 skipped, 1 failed có sẵn (CRLF).
- Ảnh hưởng contract/API/schema: có (api_guidelines mục conversations và history; deploy-rules SQL mục 7,
  biến `WORKSPACE_CONVERSATION_API_ENABLED`).
- Mở tiếp: chưa kiểm `EXPLAIN` (index trigram có được dùng) trên dữ liệu lớn; chưa có job so lệch định kỳ
  (R1); lượt bị ngắt ghi bằng session riêng chưa kiểm khoá dòng thật (R5).

## 2026-11-18 · Kiểm B3 và W2 với lượt thật: khóa OpenAI hết hạn · loại: sự cố

- Vấn đề: Toma gửi một câu hỏi qua widget (phiên `10507a81…`) để kiểm B3; lượt lỗi `analysis_error`.
- Kết quả: span `llm.chat_json` có `http_status=401`, `provider_error_code=expired_secret_key` (W2 chạy
  đúng): **khóa `OPENAI_API_KEY` của backend đã hết hạn**, mọi lượt chat hiện đều lỗi. B3 ghi
  `usage.source=trace`, 1 lần gọi AI, 0 token, 0 USD (OpenAI không tính lời gọi bị từ chối; cách ước
  tính cũ vẫn tính tiền lượt lỗi).
- Chưa kiểm được: chi phí của một lượt thành công (cần khóa mới).
- Mở tiếp: Toma cấp khóa mới trong `.env` của backend, gửi lại một câu hỏi.
- Cập nhật cùng ngày: Toma thay khóa và khởi động lại backend (15:47); lượt `59264f2d…` lỗi 429
  `credit_balance_exhausted`: khóa hợp lệ nhưng tài khoản OpenAI hết credit. B3 vẫn ghi 0 token,
  0 USD. Chi phí lượt thành công vẫn chưa kiểm được (cần nạp credit).

## 2026-11-18 · B3: ghi usage và chi phí thật của lượt · loại: thay đổi

- Vấn đề: `chat_history` lưu token/chi phí ước tính từ chữ câu hỏi + câu trả lời theo giá gpt-4o-mini;
  dữ liệu thật: lượt CRM 12/11 lưu 54 token / 0,000026 USD trong khi trace ghi 31.168 / 259 token qua
  6 lần gọi gpt-4.1-mini (khoảng 0,013 USD, gấp ~500 lần).
- Quyết định/luật (Toma yêu cầu làm B3):
  - `Trace.usage_by_model()` gom `input_tokens`/`cached_input_tokens`/`output_tokens` của span `llm`,
    `embedding` theo model; `services/turn_usage.py` đổi ra chi phí theo `core/pricing.py` (giá từng
    model, phần input cache tính giá cache, khớp tiền tố cho tên có phiên bản; ghi đè `LLM_PRICES_JSON`);
  - ghi vào cột cũ (`input_tokens`/`output_tokens` = token gọi AI, `cost_usd` gồm embedding), chi tiết
    ở `retrieval_snapshot.usage`: **không cần SQL**; không có trace thì giữ ước tính cũ (`source=estimate`);
  - `/history` thêm `usage` (nguồn số liệu) và `cost_vnd`.
- File: `core/pricing.py` (mới), `core/tracing.py`, `core/config.py`, `services/turn_usage.py` (mới),
  `services/chat_service.py`, `services/turn_sources.py`, `schemas/history.py`, `routers/workspace.py`;
  test `test_turn_usage.py` (mới).
- Kiểm chứng: `pytest tests` → 1045 passed, 14 skipped, 1 failed có sẵn (CSV F86, CRLF trong worktree).
- Ảnh hưởng: nghĩa của cột token/chi phí đổi từ lượt mới (bản ghi cũ giữ ước tính, phân biệt qua
  `usage.source`); tổng chi phí của `/chatbot/conversations` trộn cả hai. Biến mới `LLM_PRICES_JSON`
  (deploy-rules). Bảng giá mặc định cần đối chiếu với giá OpenAI hiện hành.
- Mở tiếp: kiểm một lượt mới với backend thật; cân nhắc tính lại bản ghi cũ từ `chat_traces` (sửa
  dữ liệu production, cần duyệt riêng); span vượt `CHAT_TRACE_MAX_SPANS` không được tính.

## 2026-11-18 · B5: nguồn câu trả lời theo lượt cho QS AI Workspace · loại: thay đổi

- Vấn đề: màn Chi tiết hội thoại cần biết từng lượt dùng tài liệu, dữ liệu CRM hay không tra cứu
  (Q28); `/retrieval` chỉ trả lượt mới nhất có chunk, snapshot không lưu nguồn của đoạn, trace
  không phân biệt "hết credit" với "gọi quá nhanh".
- Quyết định/luật (duyệt: Toma, kế hoạch FRONTEND_REQUIREMENTS 19.15, mock version 49):
  - W1: snapshot lưu `chunk_id`, `doc_id`, `section_title`, `section_path`, `source_id`; gộp đoạn
    trùng theo `chunk_id`, giữ điểm cao nhất;
  - hàm thuần `services/turn_sources.py` tóm tắt nguồn (`answer_source`, `tools` từ `agent_steps`);
  - `/retrieval?history_id` (lượt phiên khác → `404 history_not_found`, lượt không snapshot → 200
    rỗng); `/history` thêm `sources`; repository `get_turn`, `latest_retrieval_turn` (logic chọn
    lượt rời router);
  - W2: span `llm`/`embedding`/`http` lỗi ghi `http_status`, `provider_error_code` (đọc chung bằng
    getattr, chỉ nhận mã định danh).
  - Chỉ thêm trường; không gửi `history_id` thì như cũ (bản `/legacy`).
- File: `services/chat_service.py`, `services/turn_sources.py` (mới), `schemas/history.py`,
  `repositories/history_repository.py`, `routers/workspace.py`, `core/tracing.py`; test
  `test_history_api.py`, `test_retrieval_snapshot.py`, `test_tracing.py`, `test_turn_sources.py` (mới).
- Kiểm chứng: từ `backend/` của worktree, `pytest tests` → 1033 passed, 14 skipped, 1 failed
  có sẵn (`test_f86_baseline_csv_unchanged`: CSV bị git đổi LF→CRLF khi checkout worktree; bản ở
  checkout chính đúng hash). Chưa chạy với Supabase thật.
- Ảnh hưởng contract/API/schema: `api_guidelines.md` (history `sources`, retrieval `history_id`,
  mã `history_not_found`, thuộc tính span). Không SQL mới, không dependency mới. GET vẫn chưa xác
  thực (chờ B1).
- Mở tiếp: kiểm với backend thật; B2.

## 2026-11-11 · Tách phần dùng chung của chat thành chat-platform (D-002) · loại: thay đổi

- Vấn đề: session, service key, lease, persistence, tracing và backlog P1–P4 nằm rải trong
  `architecture.md` và `current-state.md`, trộn với nội dung của từng luồng.
- Quyết định/luật: thư mục riêng `flows/chat-platform/` theo cùng mẫu (duyệt: Toma,
  2026-11-11); phần cũ chép nguyên văn vào archive.
- File: `docs/ai/flows/chat-platform/*`; `architecture.md`, `current-state.md` rút gọn;
  `api_guidelines.md` bỏ mục trạng thái.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 938 passed,
  14 skipped; `widget-backend` `npm test` → 22 pass; `npm run build` đạt; `npm run lint`
  429 lỗi sẵn có (139 ở `src/`, 290 ở `.claude/worktrees/`).
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: số đếm test đầy đủ trước đó được ghi lần cuối là 885 passed (2026-11-10, trong
  worktree); 938 là số mới nhất.
