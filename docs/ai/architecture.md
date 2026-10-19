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
  -> ContextLoader
  -> Prune
  -> AnalysisStage -> OpenAIProvider
  -> execution-plan scaffold
  -> response chunks hiện tại
  -> HistoryRepository -> Supabase public.chat_history
  -> SSE về frontend
```

## Startup và dependency

`backend/app/main.py` tạo FastAPI app, đăng ký CORS và include
`backend/app/api/v1/router.py`. Lifespan cấu hình logging, tạo
`OpenAIProvider` khi có `OPENAI_API_KEY`, lưu provider vào `app.state` và đóng
provider khi shutdown.

`backend/app/api/v1/dependencies.py` tạo `AsyncSession`, `HistoryRepository`
và `ChatbotService`. Router không tự khởi tạo provider hoặc repository.

## Luồng `POST /chatbot`

1. Router parse `WebsiteChatIn`; Pydantic kiểm tra schema version, message,
   giới hạn text và client context.
2. Router tạo `request_id`. Dependency lấy provider từ application state.
   Nếu chưa cấu hình provider, trả HTTP 503.
3. Service kiểm tra `session_id`: UUID hợp lệ có history được dùng lại; các
   trường hợp còn lại nhận UUID mới.
4. `SecurityStage` normalize nội dung, chạy `InjectionGuard` và `ContentPolicy`.
   Nếu block, service ghi audit `status='blocked'` bằng session database riêng,
   không chạy context/provider, rồi router phát SSE `error`.
5. `ContextLoader` đọc history `status='completed'`, tạo `RunContext` gồm
   conversation, query và retrieval scope. Website hiện map tới cả
   `crm-technical` và `crm-sale`.
6. `Prune` áp dụng context token budget, giữ query/summary và bỏ các history
   turn cũ trước; lỗi budget/config là domain error, không phải security block.
7. `AnalysisStage` dựng context analysis và gọi `QueryAnalyzer` qua
   `OpenAIProvider`; sau đó tạo execution plan từ analysis.
8. Retrieval/tool execution và provider final-answer stream chưa được nối vào
   flow hoạt động. Service hiện phát các chunk mẫu, sau đó ghi history
   `status='completed'`. Đây là giới hạn quan trọng của trạng thái hiện tại.
9. Router phát event `done` với `request_id` và authoritative `session_id`.
   Frontend lưu session ID trong localStorage cho request sau.
10. Context/domain/provider exception được log server-side và ánh xạ thành SSE
    `context_error` hoặc `provider_error`.

## Persistence và session

- `HistoryRepository` là ranh giới database và ánh xạ
  `public.chat_history`.
- History thành công (completed) được dùng lại cho context; blocked/error không được đưa
  vào context.
- `session_id` do client gửi chỉ là conversation identifier, chưa phải
  ownership boundary. Chưa có history-read endpoint hoặc authorization đầy đủ.
- `message_id` chưa được lưu để idempotency; concurrent request cùng session
  chưa có ordering guarantee.

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

Đang public: `GET /health`, `GET /health/db`, `POST /chatbot`. Module
`learning_ai` chưa được include (xem mục dưới). Retrieval,
tools, history reads, authentication/ownership, idempotency và production
readiness/schema checks là phạm vi chưa hoàn thiện.

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
[0] POST /learning-knowledge          scaffold: trả 501, chưa include
[1] Ingestion -> SourceDocument       CHƯA CÓ (ingestion/ rỗng, chưa có PII redaction)
      (ẩn danh, units locator->role)
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

Giới hạn đã biết của thiết kế hiện tại:

- `chatbot/extraction/registry.py` chưa có các key `topics`, `connectors`,
  `parameters`, `alarm_codes` mà `FIELD_TO_REGISTRY_KEY` cần, nên với registry thật
  `validate_registry` sẽ báo `unknown_code` cho các trường này.
  `learning_ai/extraction/registry.py` đang là file rỗng.
- `assemble_draft` luôn ghi `redaction_applied=True`, dù chưa có bước redaction.
- `approval_gate` không tự chạy `validate_record` / conflict detection; service
  điều phối (chưa có) phải bảo đảm thứ tự đó.

Khi thay đổi flow, cần cập nhật đồng thời schema/API contract, service/stage,
repository/provider boundary, test và tài liệu này. Không mô tả scaffold hoặc
stub như tính năng đã sẵn sàng.
