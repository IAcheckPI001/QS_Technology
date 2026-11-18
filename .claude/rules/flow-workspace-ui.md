---
paths:
  - "src/workspace/**"
  - "src/App.jsx"
---

# Luồng workspace-ui (giao diện QS AI Workspace)

Đọc trước khi sửa: `docs/ai/flows/workspace-ui/README.md` và `STATE.md`; yêu cầu và quyết định
giao diện: `docs/ai/FRONTEND_REQUIREMENTS.md` (mục 13, 14, 18). Giao diện chuẩn: mock version 47.

- Màn hình gọi API qua `src/workspace/api/<tài nguyên>.js`, không `fetch`/`axios` trực tiếp.
- Kiểm quyền bằng `can()`, không kiểm tên vai trò; dữ liệu giả chỉ khi chạy dev.
- Test, từ gốc repo: `npm test`; trước khi báo xong: `npm run lint`, `npm run build`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md` của luồng.
