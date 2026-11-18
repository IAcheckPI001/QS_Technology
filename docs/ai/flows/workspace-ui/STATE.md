# Trạng thái luồng workspace-ui

Cập nhật: 2026-11-18

Ảnh chụp trạng thái hiện tại. **Viết lại** khi có thay đổi, không nối thêm; lịch sử ghi ở
[LOG.md](LOG.md). Giới hạn: 80 dòng.

## Tóm tắt

- Giao diện v1 đã duyệt (mock version 47, Q1–Q27).
- **GĐ 0 xong:** khung app, lớp API, component dùng chung, test.
- **GĐ 1 xong phần giao diện:** đăng nhập, đổi và đặt lại mật khẩu; chỉ chạy với dữ liệu giả, chờ B1.
- **GĐ 2 xong phần đọc:** Lịch sử hội thoại, Chi tiết hội thoại, Diễn biến xử lý trên API hiện có.
  - Đã kiểm với backend :8000 thật (13 hội thoại, hội thoại CRM 95 lượt, trace 12/11 và 17/11) và với dữ liệu giả.
  - Bộ lọc kênh/thời gian/model, ô số liệu, số câu hỏi, chi phí VND, tài liệu theo từng lượt chờ B2/B5 (FRONTEND_REQUIREMENTS mục 19).
- Workspace mới ở `/`, bản cũ ở `/legacy`. Tài liệu, Khóa AI, Tài khoản còn là trang "đang xây dựng".

## Độ chín từng bước

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| GĐ 0 · nền | có | |
| GĐ 1 · đăng nhập | một phần | Giao diện đủ 14.3 (trừ Hồ sơ); chờ B1 để nối thật và đóng DR-05 |
| GĐ 2 · hội thoại | một phần | Phần đọc có, đã chạy với dữ liệu thật; chờ B2/B5 |
| GĐ 3 · khóa dịch vụ AI | chưa có | Chờ B7 |
| GĐ 4 · tài khoản | chưa có | Chờ B1 |
| GĐ 5 · tài liệu | chưa có | Chờ B6, ảnh trên Storage, sửa T-07 |
| GĐ 6 · hoàn thiện | chưa có | |

## Đang làm

Không có việc dở. Kiểm với dữ liệu thật: chạy backend :8000, rồi preview với `VITE_WORKSPACE_FIXTURES=auth` (đăng nhập giả, hội thoại thật).

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| WU-1 | Trung bình | `npm run lint` toàn repo đỏ do 141 lỗi có sẵn ở trang cũ không có route; code Workspace 0 lỗi |
| WU-2 | Trung bình | `axios` ^1.11 (bản cũ và widget) có cảnh báo `npm audit`; Workspace không dùng. Nâng phiên bản cần Toma duyệt |
| WU-3 | Thấp | `FilterBar`, `DateRangeDropdown`, `OutlineTree`, `ImageViewer` làm khi có API của màn (B2, B6) |
| WU-4 | Trung bình | Contract B1 là giả định của frontend (README mục Contract) |
| WU-5 | Thấp | 14.2 và 14.3 khác nhau về báo khoá/vô hiệu; B1 cần chốt |
| WU-6 | Thấp | Chưa có lối vào đổi mật khẩu tự nguyện (màn Hồ sơ không có trong mock v1) |
| WU-7 | Trung bình | Đặc tả B2/B5 (mục 19, thêm `cost_vnd`) đã viết, backend chưa làm |
| WU-8 | Thấp | Bundle JS ~500 kB (Vite cảnh báo); tách code theo route ở GĐ 6, khi bỏ bản cũ |
| WU-9 | Thấp | Điện thoại: màn chi tiết và diễn biến chưa ẩn thanh dưới như mẫu mục 17 |
| WU-12 | Thấp | B5 chỉ có trong worktree này: backend phải chạy từ `backend/` của worktree (`--env-file` của checkout chính) cho tới khi merge. Lượt ghi trước B5 không có tên tài liệu/mục trên thẻ đoạn |
| WU-13 | Thấp | Lỗi công cụ CRM đã có câu dễ hiểu và kết luận; mã HTTP cụ thể (vd 404) chỉ có ở màn Diễn biến khi lượt có trace |
| WU-11 | Thấp | Độ khớp là điểm fused (dữ liệu thật ~0,03), thanh độ khớp gần như rỗng dù đoạn được dùng; Q23 đã ghi "chưa đổi thang" |

## Kết quả kiểm gần nhất

| Ngày | Lệnh | Kết quả |
|---|---|---|
| 2026-11-18 | Preview 5174 + backend :8000 thật, 1280×800 | Danh sách 13 hội thoại; chi tiết hội thoại CRM 95 lượt (tải hết tới "Đầu hội thoại"), tài liệu lượt 7; diễn biến 12/11 (5/6 công cụ lỗi) và 17/11 (lỗi Phân tích câu hỏi) |
| 2026-11-18 | Preview 5174 + backend B5 thật (worktree), 1280×800 | Hội thoại CRM 95 lượt: 81 dữ liệu CRM, 8 trả lời thẳng, 3 không tìm thấy, 2 có tài liệu, 1 bị chặn; nhãn và khung nguồn đúng từng loại; lượt 95 hiện bảng công cụ (6 lần gọi, 5 lỗi) |
| 2026-11-18 | `npm test` | 10 file, 70 test đạt |
| 2026-11-18 | Preview 5174 dữ liệu giả dạng B5, 1280×800 và 375×760 | Nhãn nguồn đủ loại, mặc định lượt mới nhất, bấm lượt đổi khung phải, bảng công cụ CRM, không tìm thấy, tra cứu lỗi, sheet trên điện thoại; backend cũ: tự dùng đường cũ (đã thử với :8000 thật) |
| 2026-11-18 | `npx eslint src/workspace …` | 0 lỗi (toàn repo: 141 lỗi có sẵn, WU-1) |
| 2026-11-18 | `npm run build` | Đạt; không có dữ liệu giả trong bundle production |
| 2026-11-18 | Preview 5174 (dữ liệu giả), 375px và 1280×800 | Danh sách: tải thêm 25, lọc trạng thái, tìm, xoá bộ lọc, thẻ trên điện thoại. Chi tiết: 2 khung tự cuộn vừa màn hình, cuộn sẵn tới lượt mới nhất, sheet tài liệu + Esc trên điện thoại. Diễn biến: lỗi, bị chặn, đã ngắt, hoàn tất có lỗi công cụ, không có trace. Không tràn ngang |

## Bước tiếp theo

1. Nạp credit cho tài khoản OpenAI dev (khóa mới hợp lệ nhưng hết credit, 18/11), gửi lại một câu hỏi để kiểm chi phí của lượt thành công; chốt WU-11 (cách hiện độ khớp); commit GĐ 2, B5, B3.
2. Backend B1 → B2 → B5 (mục 14, 19); bật dần bộ lọc, ô số liệu, tài liệu theo lượt.
3. GĐ 3/4/5 khi có B7, B1, B6.
