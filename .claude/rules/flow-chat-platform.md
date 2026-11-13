---
paths:
  - "backend/app/main.py"
  - "backend/app/core/**"
  - "backend/app/db/**"
  - "backend/app/api/**"
  - "backend/app/modules/chatbot/routers/**"
  - "backend/app/modules/chatbot/services/**"
  - "backend/app/modules/chatbot/repositories/**"
  - "backend/app/modules/chatbot/dependencies.py"
  - "backend/sql/**"
---

# Chat-platform (phần dùng chung của chat)

Đọc trước khi sửa: `docs/ai/flows/chat-platform/README.md` và `STATE.md`; đổi cấu hình
hoặc SQL thì đọc thêm `docs/ai/rules/deploy-rules.md`.

- Transaction của request không UPDATE dòng `chat_sessions` của phiên đã có (lease chạy trên
  connection riêng).
- Trace và log chỉ chứa metadata; không ghi nội dung tin nhắn hay token. Ngoại lệ duy nhất:
  audit `crm_query` sau `CRM_QUERY_AUDIT_LOG` (logger riêng, mặc định tắt).
- SQL trong `backend/sql/` phải idempotent và áp tay trước khi deploy code cần nó.
- Test, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md`.
