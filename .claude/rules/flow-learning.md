---
paths:
  - "backend/app/modules/learning_ai/**"
  - "backend/tests/learning_ai/**"
---

# Luồng learning (học từ hội thoại)

Đọc trước khi sửa: `docs/ai/flows/learning/README.md` và `STATE.md`.

- Luồng mới chạy tới hết bước privacy; segmenter, extractor, bảng job và index chưa nối
  vào runtime. Không mô tả như đã hoàn thiện.
- Route chưa có xác thực, chỉ mount khi `LEARNING_API_ENABLED=true` (mặc định tắt).
- Privacy chạy trước khi dữ liệu rời server và fail-closed.
- Bảng `support_chat_test_sessions`, `history_support_chat` chỉ đọc.
- Test, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests\learning_ai`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md` của luồng.
