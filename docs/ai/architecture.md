# Kiến trúc và luồng hiện tại

## Phạm vi hệ thống

Project gồm frontend React/Vite tại `src/`, BFF của widget tại `widget-backend/`, dịch vụ AI
FastAPI tại `backend/` và Supabase Cloud làm database. Dịch vụ AI điều phối chatbot; frontend
chỉ gửi request và đọc SSE. Tool nạp tài liệu `doc_ingest` chạy offline, không nằm trong
dịch vụ AI.

```text
widget ─▶ widget-backend ─▶ POST /chat/website ┐
CRM backend ─────────────▶ POST /chat/crm     ┤  chat-platform: service key, session, lease
                                              ▼
                     ChatbotService: SecurityStage → ContextLoader → Prune
                       ├─ website (hoặc CRM khi CRM_CHAT_FLOW=pipeline): RetrievalPipeline
                       │    → AnswerComposer                                   (website-qa)
                       └─ CRM: AgentRunner ⇄ tool: product_docs_ask, crm_schema/crm_query
                            hoặc crm_report/crm_records                          (crm-agent)
                     → chat_history, chat_traces → SSE                         (chat-platform)

support-chat (Supabase) ─▶ POST /ai/learning: ingestion → privacy → (chưa nối) tri thức  (learning)
PDF ─▶ CLI doc_ingest: S0 → Docling → chuẩn hóa → chunk nháp → (chưa nối) doc_chunks     (doc-ingest)
```

## Luồng

Mỗi luồng có `README.md` (thiết kế), `STATE.md` (trạng thái), `LOG.md` (nhật ký) trong
`docs/ai/flows/<luồng>/`. Chỉ mục để chọn luồng theo task: [AGENTS.md](../../AGENTS.md).

| Luồng | Việc | Thiết kế |
|---|---|---|
| chat-platform | Startup, service key theo kênh, session, turn lease, ghi `chat_history`, tracing, health | [README](flows/chat-platform/README.md) |
| website-qa | Tra cứu, hỏi đáp trên website: security, context, làm rõ, analysis, retrieval hybrid, trả lời | [README](flows/website-qa/README.md) |
| crm-agent | Agent gọi tool trên kênh CRM (thử nghiệm): tài liệu sản phẩm, truy vấn CRM | [README](flows/crm-agent/README.md) |
| learning | Học tri thức từ hội thoại hỗ trợ; hiện tới hết bước privacy | [README](flows/learning/README.md) |
| doc-ingest | Tool offline: PDF manual → chunk nháp có người duyệt; chưa ghi DB | [README](flows/doc-ingest/README.md) |

Nội dung chi tiết của file này trước 2026-11-11 được chép nguyên văn vào
`LOG-archive-2026-11-11.md` của từng luồng (doc-ingest: `LOG-archive-2026-11-09.md`).

## Các lớp và trách nhiệm

| Lớp | Trách nhiệm | Không nên làm |
|---|---|---|
| API router | HTTP/SSE transport, dependency wiring, error mapping | Gọi LLM, chứa detector/business rule |
| Schema | Contract version, validation, giới hạn input | Quyết định orchestration |
| `ChatbotService` | Điều phối session và stages, lifecycle history | Chứa provider implementation |
| Stage | Một bước domain có typed state/decision | Tạo HTTP response |
| `AgentRunner` | Vòng lặp tool-calling, giới hạn, deadline, trace | Chứa logic của từng tool, render tool vào prompt |
| `ToolRegistry` / tool | Contract tool, chuẩn hóa schema, kiểm quyền, invoke an toàn | Ghi state cha ngoài `ToolContext`, tạo task chạy ngầm |
| Provider | Adapter cho OpenAI/LLM, khai báo capability | Policy/security/routing |
| Repository | Query/write Supabase | Trả SSE hoặc biết UI |
| Frontend service | POST và parse SSE | Tự quyết định trạng thái backend |

Quy tắc đầy đủ kèm lý do: [rules/team-rules.md](rules/team-rules.md).
