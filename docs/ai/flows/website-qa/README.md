# Luồng website-qa: tra cứu, hỏi đáp trên website

Thiết kế của luồng. Trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử ở [LOG.md](LOG.md).
Mô tả chi tiết từng bước trước 2026-11-11 (vòng làm rõ, đa ngôn ngữ, bảng trách nhiệm
retrieve): [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## Phạm vi

Khách trên website hỏi qua widget; dịch vụ AI phân tích câu hỏi, tra `doc_chunks` và stream
câu trả lời có trích `[S#]`. Kênh CRM cũng chạy luồng này khi `CRM_CHAT_FLOW=pipeline`
(rollback). `RetrievalPipeline` của luồng được tool `product_docs_ask` của
[crm-agent](../crm-agent/README.md) dùng lại. Phần chung của lượt chat (service key, session,
lease, ghi history, trace) thuộc [chat-platform](../chat-platform/README.md).

## Điểm vào

| Loại | Vị trí | Ghi chú |
|---|---|---|
| Widget | `src/chatbot/Chatbot.jsx` → `src/services/chatbot.service.js` | Chỉ gọi `/api/chat`, `/api/chat/history` cùng origin |
| BFF | `widget-backend/` (Node ≥ 22, :8787) | Giữ service key, cookie `qs_visitor` và `qs_chat_session`; xem [widget-backend/README.md](../../../../widget-backend/README.md) |
| Route | `POST /chat/website` (`chatbot/routers/chat.py`) | Service key kênh `website` |

## Pipeline

```text
widget → widget-backend → POST /chat/website
 → adapter website.py → InboundRequest
 → SecurityStage (normalize, InjectionGuard, ContentPolicy; block → history blocked, SSE request_blocked)
 → ContextLoader (history completed + ConversationState) → [mode ≠ bot] câu cố định agent.*, dừng
 → Prune (CONTEXT_TOKEN_BUDGET)
 → RetrievalPipeline
     ClarificationResumeStage (khớp chắc chắn → vá sub-query, không LLM)
     AnalysisStage → QueryAnalyzer (LLM JSON strict; bỏ qua nếu đã resume)
     ExecutionStage → planner → ExecutionScheduler → handlers (không LLM)
        retrieve: Retriever → embedding → match_doc_chunks (vector + FTS, RRF) → mở rộng chunk cha
 → chỉ chitchat/out_of_scope/handoff: câu cố định (vi, en) | AnswerComposer → stream_chat
 → HandoffProvider (disabled) + update_conversation_state → history completed → SSE done
```

| Vùng | File | Vai trò |
|---|---|---|
| Adapter | `adapters/website.py` | Schema kênh → `InboundRequest` |
| Security | `stages/security/` (`stage`, `injection_guard`, `content_policy`, `detectors`, `policies/`) | Chặn trước context và provider; không log nội dung thô |
| Context | `stages/context_loader.py`, `stages/prune_stage.py` | History completed, `ConversationState`, ngân sách token |
| Làm rõ | `clarification/`, `stages/clarification_resume_stage.py` | Pending, tối đa 2 lần hỏi, `ttl` |
| Phân tích | `stages/analysis_stage.py`, `analysis/analyzer.py`, `analysis/prompt/`, `extraction/registry.py` | Intent, entity, `standalone_query` tiếng Việt, `language` |
| Thực thi | `stages/execution_stage.py`, `orchestration/{planner,scheduler,handlers,collector}.py` | Một task retrieve mỗi sub-query; giữ sub-query đang chờ làm rõ |
| Retrieval | `retrieval/retriever.py`, `repositories/doc_chunk_repository.py`, `backend/sql/doc_chunks.sql` | Hybrid search có lọc, fallback, gán `S#` |
| Trả lời | `stages/answer_composer.py`, `prompts/answer.py`, `prompts/direct_responses.py` | Một lần gọi LLM cho câu trả lời cuối; câu cố định cho chitchat/out_of_scope/handoff |
| Handoff | `providers/handoff.py` | Scaffold: `DisabledHandoffProvider` |

## Contract

- Request, header, SSE (`delta`, `done`, `error`) và mã lỗi: [api_guidelines.md](../../api_guidelines.md)
  mục "`POST /chat/website` và `POST /chat/crm`" và "Response và SSE contract".
- Code phát SSE (`routers/sse.py`) thuộc [chat-platform](../chat-platform/README.md): thêm
  event mới thì đọc cả README đó, cập nhật api_guidelines.md và kiểm widget-backend
  (`widget-backend/src/routes.js`) có chuyển tiếp event lạ hay không.
- Snapshot retrieval của lượt (`GET /chatbot/sessions/{id}/retrieval`): api_guidelines.md mục
  "Support chat history".
- Thiết kế SecurityStage: [security-stage-pipeline.md](../../security-stage-pipeline.md).
- Cột `doc_chunks` do doc-ingest sinh: [p2_chunk_contract.md](../../reports/p2_chunk_contract.md).

## Bất biến của luồng

- Handler orchestration không gọi LLM; mỗi lượt chỉ một lần LLM cho câu trả lời cuối (ngoài
  analysis).
- `standalone_query` luôn tiếng Việt (embedding/FTS chạy trên `embed_text` tiếng Việt); ngôn
  ngữ trả lời = `analysis.language` → ngôn ngữ phiên → locale client → `vi`.
- Model trong câu hỏi phải có trong câu, lịch sử hoặc `last_models` (`guard_extracted_models`);
  không âm thầm đổi model.
- Sub-query cần làm rõ bị giữ, không tra cứu; các ý đã rõ vẫn chạy.
- Context chỉ đọc history `status='completed'`.
- Service key chỉ nằm ở widget-backend; trình duyệt không thấy `session_id`.

## Cấu hình

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `EMBEDDING_MODEL` | rỗng, `gpt-4o-mini`, `text-embedding-3-small` | Thiếu key: không có provider, chat trả `provider_not_configured` |
| `CONTEXT_TOKEN_BUDGET` | 2048 | Ngân sách Prune |
| `RETRIEVAL_VECTOR_CANDIDATE_K`, `RETRIEVAL_FTS_CANDIDATE_K`, `RETRIEVAL_RRF_K` | 20, 20, 60 | Giá trị khởi đầu, chưa tối ưu |
| `RETRIEVAL_FINAL_CHUNK_TOP_K`, `RETRIEVAL_MAX_CONTEXT_PARENTS`, `RETRIEVAL_MIN_SIMILARITY`, `RETRIEVAL_SPEC_BOOST` | 6, 5, 0,25, 0,005 | |
| widget-backend: `CHATBOT_API_KEY`, `ALLOWED_ORIGINS`, `COOKIE_SECURE` | — | Xem `widget-backend/.env.example` |

## Test

```powershell
# từ backend/
.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api
# từ widget-backend/
npm test
```

Test riêng của luồng trong `tests/chatbot/`: `test_security_*`, `test_context_pipeline`,
`test_retrieval*`, `test_analysis_contract`, `test_orchestration_*`, `test_answer_composer`,
`test_clarification`, `test_normalize_input`, `test_product_catalog`, `test_registry_snapshot`.
Chưa có eval cho luồng này.

## Log runtime

- `chat_history`: `status`, `normalized_query`, `conversation_state`, `retrieval_snapshot`
  (`retrieval_status`, task, chunk).
- Span `stage.*`, `retrieval.search`, `embedding`, `db.match_doc_chunks`, `llm.stream_chat`
  trong trace của lượt.

## Ranh giới với luồng khác

- crm-agent chạy `RetrievalPipeline` trên RunState con (thêm `CatalogLookupStage`, không
  compose); đổi pipeline thì chạy cả test agent.
- `doc_chunks` hiện chứa chunk F86 biên soạn tay; chunk mới sẽ do
  [doc-ingest](../doc-ingest/README.md) cung cấp. Migration schema `doc_chunks` là thay đổi
  của luồng này.
- Registry model `extraction/registry.py` dùng chung với crm-agent; bản chép ở
  `doc_ingest/profiles/registry_snapshot.json` được test kiểm khớp.
