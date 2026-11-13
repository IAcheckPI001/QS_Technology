# Trạng thái toàn dự án

Cập nhật: 2026-11-13

Bảng tổng, mỗi luồng một dòng. Chi tiết, vấn đề mở và bước tiếp theo nằm ở `STATE.md` của
từng luồng; lịch sử ở `LOG.md`. File này không chứa lịch sử; cập nhật dòng của luồng khi
STATE của luồng đổi trạng thái tổng.

| Luồng | Trạng thái | Chưa kiểm trên hệ thống thật | Chi tiết |
|---|---|---|---|
| chat-platform | Service key, session, lease, history, trace có code và test; GET Support Workspace chưa xác thực; `Idempotency-Key` chưa chống trùng | Supabase (`/health/db`, insert `chat_history`, lease trên khóa dòng) | [STATE](flows/chat-platform/STATE.md) |
| website-qa | Chạy trọn luồng; retrieval mức test, tham số chưa tối ưu; handoff là scaffold; chưa có SSE nguồn/ảnh | Retrieval trên Supabase thật | [STATE](flows/website-qa/STATE.md) |
| crm-agent | Thử nghiệm; tool CRM sau `CRM_REPORT_ENABLED` (mặc định tắt), mặc định phương án C (`crm_schema`/`crm_query`, chưa commit); chưa phân quyền tool | OpenAI tool calling; eval tay chưa chạy | [STATE](flows/crm-agent/STATE.md) |
| learning | Tới hết bước privacy sau `LEARNING_API_ENABLED`, chưa xác thực; segment/extract, job, index chưa nối | Supabase, Ollama | [STATE](flows/learning/STATE.md) |
| doc-ingest | PDF → chunk nháp; chưa ghi DB; F54 (run `eval-k`, 296 chunk) đạt cổng 2b (tạm, nhãn chưa xác nhận); Bước 3 làm giàu xong 243/243 lá, cổng 2c tự động đạt, 30 mẫu chờ duyệt | — (tool offline, chạy trên PDF thật) | [STATE](flows/doc-ingest/STATE.md) |

## Kiểm thử toàn repo gần nhất

2026-11-11:
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 951 passed, 14 skipped (sau thay đổi giám sát `crm_query`).
- Từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 318 passed.
- `widget-backend` `npm test` → 22 pass.
- Từ root: `npm run build` đạt; `npm run lint` lỗi sẵn có (139 lỗi ở `src/`, 290 ở
  `.claude/worktrees/`).

## Nội dung cũ

Ngày 2026-11-11 các mục cũ của file này (Completion summary, Finding status, Implemented
behavior, Open risks, Next remediation order, Validation record, Architectural impact,
Context/RAG pipeline) được chép nguyên văn vào `LOG-archive-2026-11-11.md` của luồng tương
ứng (doc-ingest: `LOG-archive-2026-11-09.md`). Mỗi file archive ghi rõ đoạn nào lấy từ đâu.
Quyết định liên luồng: [decisions.md](decisions.md).
