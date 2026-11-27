# Trạng thái toàn dự án

Cập nhật: 2026-11-26

Bảng tổng, mỗi luồng một dòng. Chi tiết, vấn đề mở và bước tiếp theo nằm ở `STATE.md` của
từng luồng; lịch sử ở `LOG.md`. File này không chứa lịch sử; cập nhật dòng của luồng khi
STATE của luồng đổi trạng thái tổng.

| Luồng | Trạng thái | Chưa kiểm trên hệ thống thật | Chi tiết |
|---|---|---|---|
| chat-platform | Service key, session, lease, history, trace có code và test; API Workspace B2/B3/B5 (bảng tóm tắt `chat_conversations`, tìm không dấu, phân trang, nguồn theo lượt, chi phí thật) đã kiểm với Supabase thật, có trên `feature/deploy_ai_service` (D-011–D-013); GET Support Workspace chưa xác thực; `Idempotency-Key` chưa chống trùng | `/health/db`, lease trên khóa dòng | [STATE](flows/chat-platform/STATE.md) |
| workspace-ui | GĐ 0–2: khung app, đăng nhập (dữ liệu giả, chờ B1), Lịch sử/Chi tiết/Diễn biến hội thoại trên B2/B3/B5 (đã kiểm dữ liệu thật); câu trả lời Markdown + huy hiệu trích dẫn bấm tới nguồn, cả widget (WU-17 đợt 1, 2026-11-25, merge `a1de8e9`); kiểm duyệt bằng playwright-cli; có trên `feature/deploy_ai_service`; GĐ 3–5 chờ B7, B1, B6 | Đăng nhập thật (B1) | [STATE](flows/workspace-ui/STATE.md) |
| website-qa | Chạy trọn luồng; chat tra cứu trên `doc_chunks_v2` từ 2026-11-19 (D-009 bước 6; mọi chunk còn `draft`, production mặc định `RETRIEVAL_APPROVED_ONLY=true` nên chưa có tài liệu). Đang làm R-1 (tối ưu bước phân tích + định tuyến, [kế hoạch](reports/p3_r1_routing_plan.md)): công cụ đo và luật định tuyến `r1`/`r2` đã có code (chỉ eval dùng, production giữ `r0`), **chưa đo được vì OpenAI hết credit (2026-11-14)**; handoff là scaffold; chưa có SSE nguồn/ảnh | Tra cứu v2 trong lượt thật (chờ credit OpenAI); số đo luật định tuyến | [STATE](flows/website-qa/STATE.md) |
| crm-agent | Thử nghiệm; tool CRM (`crm_schema`/`crm_query`) sau `CRM_REPORT_ENABLED` (mặc định tắt); eval gpt-4.1-mini 78/81. Đã dọn 2026-11-16 (D-010). Đợt 0 và Đợt 1 bước 1 (so sánh 1 lần gọi, ép tra nguồn) đã merge, kiểm thật 2026-11-20; câu so sánh theo D-014 tạm (cắt cột đạt C1–C7, chọn bảng chung còn sai). Đợt 1 bước 2 (C1–C3), bước 3 (gói A: `facts`, lịch sử theo lượt, D-015) và sửa LC-2/4/7 đã merge (`0561487`); kiểm thật 7 câu CRM 5/7; trần token lượt môi trường kiểm thử 30000; lỗi mở: nhãn facts (LC-8), nghĩa "hộp tin nhắn chờ" (LC-6); còn mở: nghĩa "khách" của phiếu (r1); chưa phân quyền tool | Eval lại sau Đợt 0/1 (G1); chốt D-014; audit log trên server thật | [STATE](flows/crm-agent/STATE.md) |
| learning | Tới hết bước privacy sau `LEARNING_API_ENABLED`, chưa xác thực; segment/extract, job, index chưa nối | Supabase, Ollama | [STATE](flows/learning/STATE.md) |
| doc-ingest | PDF → chunk nháp → `doc_chunks_v2` (draft). DB 2026-11-26: 983 active, 0 approved = 911 chunk CRM của 10 tài liệu (run `crm-1.2/1.4/1.6`, verdict model 596 ok / 307 fix / 8 pending, chưa người xác nhận) + 72 chunk catalog phương án C. T-15b, T-21, T-20b đã push; S0 trang lai + T-22 staged chờ duyệt. Chưa có cổng "tìm được" (I-61): chunk đạt chưa bảo đảm tra cứu tốt | Nạp theo sổ nguồn (giai đoạn 2); `approved` (I-53) | [STATE](flows/doc-ingest/STATE.md) |

## Kiểm thử toàn repo gần nhất

2026-11-16, sau đợt dọn crm-agent, trên `feature/deploy_ai_service` (`2178910`):
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 1016 passed, 14 skipped.
  Trước dọn, `671fe22`: 1120 passed (số giảm là test của phương án A đã xoá).

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
