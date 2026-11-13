# Lưu trữ luồng learning tới 2026-11-11

Chép nguyên văn ngày 2026-11-11 khi tách tài liệu theo luồng (D-002). Không sửa file này;
trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử mới ở [LOG.md](LOG.md). Phần lấy từ
`current-state.md` giữ nguyên tiếng Anh như bản gốc.



## Từ `architecture.md`: mục "Luồng học tri thức (`learning_ai`): thiết kế và trạng thái"


Mục tiêu: biến hội thoại hỗ trợ / tài liệu thành `KnowledgeRecord` có cấu trúc,
được người duyệt, rồi chia chunk và index cho chatbot truy xuất. Module nằm ở
`backend/app/modules/learning_ai/`.

**Trạng thái tổng quát:** phần lõi domain thuần (schema, validate, conflict rule,
lifecycle, chunking, indexer logic) đã có và có unit test tại
`backend/tests/learning_ai/`. `POST /ai/learning` (sau cờ `LEARNING_API_ENABLED`,
chưa có auth) chạy được bước [1]: ingestion → prefilter → privacy.
**Chưa có luồng end-to-end tới tri thức**: chưa có lời gọi LLM segment/extract,
persistence Supabase (job, record), outbox, embedding hay vector index.

```text
[0] POST /ai/learning                 chạy [1]; chỉ include khi LEARNING_API_ENABLED=true, chưa có auth
[1] Ingestion -> SourceDocument       có logic + service, đã nối route [0] (chưa có bảng job)
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

## Từ `current-state.md`: dòng P6 của "Completion summary"

| P6 knowledge learning pipeline (`learning_ai`) | Ingestion + privacy wired behind a flag | Pure domain logic (record schema, post-LLM validation, rule conflicts, review lifecycle, chunking, indexer sync) plus CRM ingestion, prefilter and the Ollama-backed privacy pipeline exist and are unit-tested with fake providers. `POST /ai/learning` runs ingestion + privacy when `LEARNING_API_ENABLED=true` (no authentication yet). LLM segment/extract calls, job persistence, outbox, embedding and vector index are missing. Not verified against live Supabase/Ollama. |

## Từ `current-state.md`: mục "P5 — Knowledge learning pipeline" của "Next remediation order"


Design and per-step status are in `docs/ai/architecture.md`. Remaining work, in order:

Done: CRM ingestion from `public.history_support_chat`, prefilter, privacy
pipeline (regex A/D, Ollama B, redactor C, fail-closed) and `LearningIngestionService`.
`assemble_draft` now takes `redaction_applied` from the caller. The table is
Supabase-managed and must have `created_at timestamptz not null default now()`. The
ORM expects that column, and it has not been verified against the live table.

19. Add the missing registry keys (`topics`, `connectors`, `parameters`,
    `alarm_codes`) and build one `RegistrySnapshot` source shared with query extraction.
20. Build a labeled Vietnamese CRM evaluation set and measure Ollama recall per finding
    type before trusting a model. The `.env.example` default `qwen3:1.7b` is likely too
    small; `qwen2.5:7b-instruct` or newer is recommended as a starting point.
21. Segmenter/Extractor prompts and calls behind the provider layer, driven by a
    learning service, not the router. Segments whose main topic is pricing must use
    `skip_reason="pricing"`; official prices come from catalog documents.
22. Supabase tables for extraction jobs (with `source_content_hash` so unchanged
    conversations are not reprocessed), knowledge records/revisions, outbox and
    chunks/vectors. This needs a schema decision before implementation.
23. Learning service ordering: extract -> assemble -> validate -> conflicts ->
    `pending_review`. Approval must run the gate after validation and conflicts.
24. Review API/UI, semantic conflict comparison, `Embedder`/`SearchIndex`
    implementations, outbox worker, and chatbot retrieval using `ChunkFilters`.

