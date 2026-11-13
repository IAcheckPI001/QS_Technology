---
paths:
  - "backend/app/api/**"
  - "backend/app/modules/chatbot/routers/**"
  - "backend/app/modules/chatbot/schemas/**"
  - "backend/app/modules/learning_ai/router.py"
  - "backend/app/modules/learning_ai/schemas/**"
---

# Contract API

Đọc trước khi sửa: `docs/ai/api_guidelines.md`.

- Router chỉ làm transport (TR-01); schema explicit, versionable (TR-04).
- Đổi schema, SSE event, mã lỗi hoặc status code: cập nhật `api_guidelines.md` và test
  trong cùng thay đổi (TR-06).
- Route mới chưa có xác thực phải nằm sau cờ cấu hình mặc định tắt (TR-16) và được ghi
  vào `docs/ai/rules/deploy-rules.md`.
