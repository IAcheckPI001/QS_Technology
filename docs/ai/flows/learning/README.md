# Luồng learning: học tri thức từ hội thoại (`learning_ai`)

Thiết kế của luồng. Trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử ở [LOG.md](LOG.md).
Bản mô tả đầy đủ trước 2026-11-11: [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## Phạm vi

Biến hội thoại hỗ trợ giữa nhân viên CRM và khách thành `KnowledgeRecord` có cấu trúc, qua
người duyệt, rồi chia chunk và index cho chatbot truy xuất. Hiện chỉ chạy được tới hết bước
privacy (xem STATE).

## Điểm vào

Chỉ mount khi `LEARNING_API_ENABLED=true` (mặc định tắt); **chưa có xác thực**
(`backend/app/api/v1/router.py`).

| Route (`learning_ai/router.py`) | Việc |
|---|---|
| `GET /support-chat/sessions`, `POST /support-chat/sessions` | Liệt kê, tạo session support-chat |
| `GET /support-chat/sessions/{session_id}/messages` | Đọc tin nhắn của session |
| `POST /ai/learning` | Chạy ingestion → prefilter → privacy cho một session, trả `LearnResponse` |

Frontend: `src/pages/Chat.jsx` gọi `prepareLearning` trong `src/services/chatbot.service.js`.

## Pipeline

```text
[0] POST /ai/learning                     có; sau cờ, chưa xác thực
[1] Ingestion → SourceDocument            có (chưa có bảng job, kết quả không lưu)
      prefilter → privacy A..D            có; Ollama bắt buộc, fail-closed
[2] Pass 1 Segmenter (LLM)                chỉ có schema Segment/SegmentationOutput
[3] Pass 2 Extractor (LLM, strict)        có schema + to_strict_schema; chưa có prompt, chưa gọi provider
[4] assemble_draft → DRAFT record         có logic
[5] validate_record                       có logic
[6] detect_rule_conflicts                 có luật cho parameter/spec/wiring; chưa so ngữ nghĩa, chưa tra DB
[7] Review lifecycle + approval_gate      có logic thuần; chưa persistence/API/UI
[8] Outbox → sync_record                  build_chunks + embedding_text + upsert có; Embedder/SearchIndex chỉ là Protocol
[9] Chatbot retrieval theo ChunkFilters   chưa nối
```

| Vùng | File | Vai trò |
|---|---|---|
| Route | `router.py` | Transport; service làm việc thật |
| Nguồn | `repositories/support_chat_repository.py` | Đọc `public.support_chat_test_sessions`, `public.history_support_chat` theo `message_no` (chỉ đọc) |
| Ingestion | `ingestion/source_document.py`, `prefilter.py`, `service.py` | Document có locator `m1..mN`, lọc hội thoại vô giá trị, điều phối nạp → lọc → privacy |
| Privacy | `privacy/` (`pipeline`, `pii_patterns`, `sensitivity_checker`, `redactor`) | A regex → B Ollama → C thay placeholder → D regex lại |
| Schema | `schemas/knowledge_record.py`, `content.py`, `common.py`, `llm_output.py`, `registry.py`, `api.py` | Record 5 loại nội dung, DTO hai pass LLM, `RegistrySnapshot`, contract API |
| Trích xuất | `extraction/assembler.py`, `validators.py` | Ghép DTO thành draft, kiểm hậu-LLM |
| Duyệt | `review/conflict_detector.py`, `lifecycle.py` | Xung đột theo luật, state machine, approval gate |
| Index | `chunking/`, `indexing/indexer.py` | Chunk theo loại tri thức, đồng bộ index idempotent |
| Provider | `chatbot/providers/ollama_model.py` | Ollama (endpoint OpenAI-compatible), dựng trong `main.py` khi bật cờ |

## Contract

`POST /ai/learning` và các route support-chat: [api_guidelines.md](../../api_guidelines.md)
mục "`POST /ai/learning`" và "Support chat history".

## Bất biến của luồng

- Privacy chạy **trước** khi bất kỳ dữ liệu nào rời server. Fail-closed: provider lỗi, output
  sai schema hoặc `reviewed_locators` thiếu message → cả document `privacy_unavailable`, không
  có kết quả một phần.
- Ollama chỉ báo cáo finding; hệ thống quyết định: `pii`, `pricing` bị thay placeholder
  (`[PERSON_1]`, `[PRICE_1]`); `policy`, `customer_specific` giữ text và gắn cờ. Finding không
  phải chuỗi con nguyên văn bị loại (`unverified_findings`). Giá trị gốc của placeholder không
  được lưu.
- Prefilter chỉ skip khi chắc chắn; message có từ khác chào hỏi, chữ số hoặc mã registry thì giữ.
- `source_id` là UUIDv5 của `session_id` + hash nội dung: ổn định khi nội dung không đổi.
- Hệ thống gán ID, provenance, privacy, `source_id` cho record; LLM không gán.
- `approval_gate` không tự chạy `validate_record` hay conflict detection; service điều phối
  (chưa có) phải bảo đảm thứ tự extract → assemble → validate → conflicts → `pending_review`.
- Segment có chủ đề chính là giá dùng `skip_reason="pricing"`; giá chính thức lấy từ tài liệu
  catalog.

## Cấu hình

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `LEARNING_API_ENABLED` | `false` | Mount route; route chưa có xác thực |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | rỗng | Thiếu thì `POST /ai/learning` trả 503 |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_NUM_CTX`, `OLLAMA_WINDOW_TOKENS` | 180, 8192, 2500 | `OLLAMA_NUM_CTX` phải khớp `PARAMETER num_ctx` trong Modelfile; cửa sổ phải nhỏ hơn `num_ctx` |

## Test

```powershell
# từ backend/
.\venv\Scripts\python.exe -m pytest tests\learning_ai
```

8 file test (`test_learning_api`, `test_privacy_pipeline`, `test_pii_patterns`,
`test_source_document`, `test_assembler_validators`, `test_llm_output`, `test_review`,
`test_chunking_indexer`), provider giả. Chưa có eval.

## Log runtime

Chỉ dòng log `learning ingestion … status=` (`ingestion/service.py`); chưa có bảng job, chưa
có trace cho `/ai/learning`.

## Ranh giới với luồng khác

- Dùng `chatbot/providers/ollama_model.py`; không dùng OpenAI.
- `RegistrySnapshot` cần dùng chung với registry của chatbot (`chatbot/extraction/registry.py`),
  nhưng registry đó chưa có key `topics`, `connectors`, `parameters`, `alarm_codes`.
- Bước [9] sẽ đưa tri thức vào retrieval của [website-qa](../website-qa/README.md); chưa nối.
