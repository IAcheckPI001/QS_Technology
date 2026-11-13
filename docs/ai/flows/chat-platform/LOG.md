# Nhật ký chat-platform

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-07 (nguyên văn từ `current-state.md` và `architecture.md`, gồm Finding
status, API gateway, service key, lease, tracing): [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

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
