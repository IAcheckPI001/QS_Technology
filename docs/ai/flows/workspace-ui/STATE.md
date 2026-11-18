# Trạng thái luồng workspace-ui

Cập nhật: 2026-11-18

Ảnh chụp trạng thái hiện tại. **Viết lại** khi có thay đổi, không nối thêm; lịch sử ghi ở
[LOG.md](LOG.md). Giới hạn: 80 dòng.

## Tóm tắt

- Giao diện v1 đã duyệt (mock version 47, Q1–Q27).
- **GĐ 0 xong:** khung app, lớp API, component dùng chung, test.
- **GĐ 1 xong phần giao diện:** đăng nhập (M1), đổi mật khẩu bắt buộc, đặt lại mật khẩu từ link, chặn route, 401/403.
  - Chỉ chạy với dữ liệu giả.
  - Contract B1 là giả định (WU-4), chưa nối backend thật.
- Workspace mới chạy ở `/`, bản cũ ở `/legacy`. Các màn nghiệp vụ còn là trang "đang xây dựng".

## Độ chín từng bước

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| GĐ 0 · nền | có | |
| GĐ 1 · đăng nhập | một phần | Giao diện và luồng đủ 14.3 (trừ Hồ sơ); chạy trên dữ liệu giả; chờ B1 để nối thật và đóng DR-05 |
| GĐ 2 · hội thoại | chưa có | API đọc đã có (`api/conversations.js`); chờ B2/B5 cho lọc, phân trang |
| GĐ 3 · khóa dịch vụ AI | chưa có | Chờ B7 |
| GĐ 4 · tài khoản | chưa có | Chờ B1 |
| GĐ 5 · tài liệu | chưa có | Chờ B6, ảnh trên Storage, sửa T-07 |
| GĐ 6 · hoàn thiện | chưa có | |

## Đang làm

Không có việc dở. Bước kế: GĐ 2 (phần đọc hội thoại trên API có sẵn).

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| WU-1 | Trung bình | `npm run lint` toàn repo đỏ do 141 lỗi có sẵn ở trang cũ không có route (`Blogs`, `NewBlog`, `Session`, `Services`…); code Workspace 0 lỗi |
| WU-2 | Trung bình | `axios` ^1.11 (dùng ở `services/api.service.js` của bản cũ và widget) có nhiều cảnh báo `npm audit`; Workspace không dùng. Nâng phiên bản cần Toma duyệt |
| WU-3 | Thấp | Thành phần riêng màn (`FilterBar`, `DateRangeDropdown`, `OutlineTree`, `ImageViewer`) làm trong giai đoạn của màn |
| WU-4 | Trung bình | Contract B1 (đường dẫn `/workspace/auth/*`, mã lỗi, cookie `ws_csrf`, `must_change_password`) là giả định của frontend, ghi ở README mục Contract; chốt khi làm B1 |
| WU-5 | Thấp | 14.2 nói thông báo đăng nhập sai giống nhau cho mọi lý do, 14.3 lại muốn báo khoá/vô hiệu. Giao diện hiện đủ cả ba; B1 cần chốt khi nào được trả `account_locked`/`account_disabled` (vd. chỉ khi mật khẩu đúng) |
| WU-6 | Thấp | Chưa có lối vào đổi mật khẩu tự nguyện (màn Hồ sơ không có trong mock v1); route `/change-password` đã hỗ trợ |

## Kết quả kiểm gần nhất

| Ngày | Lệnh | Kết quả |
|---|---|---|
| 2026-11-18 | `npm test` | 6 file, 43 test đạt |
| 2026-11-18 | `npx eslint src/workspace src/App.jsx vite.config.js` | 0 lỗi (toàn repo: 141 lỗi có sẵn, WU-1) |
| 2026-11-18 | `npm run build` | Đạt; dữ liệu giả không có trong bundle production |
| 2026-11-18 | Preview 5174 (dữ liệu giả), 320px và 1280×800 | Khoá (giờ mở), bắt đổi mật khẩu chặn mọi trang và quay về `next`, kiểm mật khẩu ở trình duyệt, link đặt lại hỏng/hợp lệ, điền sẵn email sau đặt lại; khớp kích thước mock M1; không tràn ngang |

## Bước tiếp theo

1. GĐ 2: Lịch sử hội thoại, Chi tiết (2 khung tự cuộn), Diễn biến trên API sẵn có; ẩn bộ lọc chưa có API.
2. Backend B1 theo mục 14, dùng contract ở README luồng này; xong thì tắt dữ liệu giả cho đăng nhập và kiểm lại.
3. Dọn lỗi lint có sẵn (WU-1) và nâng axios (WU-2), nếu Toma đồng ý.
