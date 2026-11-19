# Nhật ký chat-platform

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-07 (nguyên văn từ `current-state.md` và `architecture.md`, gồm Finding
status, API gateway, service key, lease, tracing): [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

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
