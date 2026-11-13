# Nhật ký luồng <tên>

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính và trỏ tới nó. Khi file vượt 300 dòng, cắt các mục cũ
sang `LOG-archive-<ngày của mục mới nhất bị cắt>.md` và để lại liên kết ở đầu file.
(Archive tạo khi tách tài liệu theo luồng mang ngày tách, vd. `LOG-archive-2026-11-11.md`.)

Sau khi thêm mục, viết lại [STATE.md](STATE.md).

## YYYY-MM-DD · <tiêu đề ngắn> (<ID liên quan>) · loại: thay đổi | quyết định | sự cố | đánh giá

- Vấn đề: <điều gì sai hoặc thiếu, ở đâu>
- Quyết định/luật: <nội dung> (duyệt: <ai>)
- File: <file đã sửa, test đã thêm>
- Kiểm chứng: <lệnh> → <kết quả, run id>
- Ảnh hưởng contract/API/schema: <có: gì | không>
- Mở tiếp: <ID vấn đề mới hoặc việc còn lại>

Bỏ dòng không áp dụng. Giữ ID sẵn có của luồng (ví dụ I-xx vấn đề, BL-xx backlog, T-xx
luật, D-xx quyết định).
