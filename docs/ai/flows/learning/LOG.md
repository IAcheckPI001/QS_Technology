# Nhật ký luồng learning

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Thiết kế và backlog trước 2026-11-11 (nguyên văn): [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).
Mục kiểm thử 2026-10-19 (104 test `learning_ai` đạt) nằm trong archive của
[website-qa](../website-qa/LOG-archive-2026-11-11.md) vì ghi chung một lần chạy.

## 2026-11-11 · Tách tài liệu luồng learning (D-002) · loại: thay đổi

- Vấn đề: thiết kế nằm trong `architecture.md` (101 dòng), trạng thái và backlog trong
  `current-state.md` (P6, việc 19–24).
- Quyết định/luật: tách thành README, STATE, LOG; phần cũ chép nguyên văn vào archive (duyệt:
  Toma, D-002).
- File: `docs/ai/flows/learning/*`; `architecture.md`, `current-state.md` rút gọn.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 938 passed,
  14 skipped.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
