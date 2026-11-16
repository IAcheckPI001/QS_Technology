# Trạng thái toàn dự án

Cập nhật: 2026-11-16

Bảng tổng, mỗi luồng một dòng. Chi tiết, vấn đề mở và bước tiếp theo nằm ở `STATE.md` của
từng luồng; lịch sử ở `LOG.md`. File này không chứa lịch sử; cập nhật dòng của luồng khi
STATE của luồng đổi trạng thái tổng.

| Luồng | Trạng thái | Chưa kiểm trên hệ thống thật | Chi tiết |
|---|---|---|---|
| chat-platform | Service key, session, lease, history, trace có code và test; GET Support Workspace chưa xác thực; `Idempotency-Key` chưa chống trùng | Supabase (`/health/db`, insert `chat_history`, lease trên khóa dòng) | [STATE](flows/chat-platform/STATE.md) |
| website-qa | Chạy trọn luồng; chat vẫn dùng bảng cũ `doc_chunks`. Đang làm R-1 (tối ưu bước phân tích + định tuyến, [kế hoạch](reports/p3_r1_routing_plan.md)): công cụ đo và luật định tuyến `r1`/`r2` đã có code (chỉ eval dùng, production giữ `r0`), **chưa đo được vì OpenAI hết credit (2026-11-14)**; handoff là scaffold; chưa có SSE nguồn/ảnh | Chat trên bảng mới `doc_chunks_v2`; số đo luật định tuyến | [STATE](flows/website-qa/STATE.md) |
| crm-agent | Thử nghiệm; tool CRM (`crm_schema`/`crm_query`) sau `CRM_REPORT_ENABLED` (mặc định tắt); eval gpt-4.1-mini 78/81. Đã dọn 2026-11-16 (xoá phương án A, D-010; gỡ `print()` in dữ liệu CRM), chưa merge về `feature/deploy_ai_service`; còn mở: `.env.example` lệch, luật username/trả lời khi chạm giới hạn, nghĩa "khách" của phiếu (r1); chưa phân quyền tool | Eval lại sau đợt dọn và sau thay đổi giới hạn gọi tool; `AGENT_MODEL` ở môi trường chạy; audit log trên server thật | [STATE](flows/crm-agent/STATE.md) |
| learning | Tới hết bước privacy sau `LEARNING_API_ENABLED`, chưa xác thực; segment/extract, job, index chưa nối | Supabase, Ollama | [STATE](flows/learning/STATE.md) |
| doc-ingest | PDF → chunk nháp → `doc_chunks_v2` (draft): F54 296, F86 Installation 23, catalog 7 bộ điều khiển 37 chunk (nguồn biên soạn `curated/`, chờ verdict, chưa gắn hình); cổng 2c v4 không đạt (chờ prompt v5); còn soạn servo/board/phụ kiện/công ty | — (tool offline, chạy trên PDF thật) | [STATE](flows/doc-ingest/STATE.md) |

## Kiểm thử toàn repo gần nhất

2026-11-16, sau đợt dọn crm-agent (nhánh `claude/agent-crm-development-29f518`):
- Từ `backend/`: `pytest tests` → 1015 passed, 14 skipped, 1 failed (`test_f86_baseline`: CSV bị
  checkout thành CRLF trong worktree; có sẵn, không do đợt dọn). Trước dọn, `671fe22`: 1120 passed.

Đợt trước, 2026-11-11:
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
