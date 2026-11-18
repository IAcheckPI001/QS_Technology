# Trạng thái luồng workspace-ui

Cập nhật: 2026-11-18

Ảnh chụp trạng thái hiện tại. **Viết lại** khi có thay đổi, không nối thêm; lịch sử ghi ở
[LOG.md](LOG.md). Giới hạn: 80 dòng.

## Tóm tắt

- Giao diện v1 đã duyệt (mock version 47, Q1–Q27; Q28 khung nguồn version 49).
- **GĐ 0 xong:** khung app, lớp API, component dùng chung, test.
- **GĐ 1 xong phần giao diện:** đăng nhập, đổi và đặt lại mật khẩu; chỉ chạy với dữ liệu giả, chờ B1.
- **GĐ 2 xong phần đọc trên B2, B3, B5:** Lịch sử hội thoại có đủ bộ lọc (kênh, trạng thái, model sản
  phẩm, thời gian), 4 ô số liệu, tìm không dấu có tô sáng và "Khớp ở lượt N", phân trang ở máy chủ;
  Chi tiết mở đúng lượt khớp; nguồn câu trả lời theo lượt; chi phí thật. Đã kiểm với backend thật.
- Workspace mới ở `/`, bản cũ ở `/legacy`. Tài liệu, Khóa AI, Tài khoản còn là trang "đang xây dựng".

## Độ chín từng bước

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| GĐ 0 · nền | có | |
| GĐ 1 · đăng nhập | một phần | Giao diện đủ 14.3 (trừ Hồ sơ); chờ B1 để nối thật và đóng DR-05 |
| GĐ 2 · hội thoại | có (chưa xác thực) | B2/B3/B5 đã nối và kiểm với dữ liệu thật; còn chi tiết tải mọi lượt một lần, registry model (B8) |
| GĐ 3 · khóa dịch vụ AI | chưa có | Chờ B7 |
| GĐ 4 · tài khoản | chưa có | Chờ B1 |
| GĐ 5 · tài liệu | chưa có | Chờ B6, ảnh trên Storage, sửa T-07 |
| GĐ 6 · hoàn thiện | chưa có | |

## Đang làm

Không có việc dở. Kiểm với dữ liệu thật: chạy backend từ `backend/` của worktree (`--env-file` của
checkout chính, có `WORKSPACE_CONVERSATION_API_ENABLED=true`), rồi preview `frontend-worktree-live`.

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| WU-1 | Trung bình | `npm run lint` toàn repo đỏ do 141 lỗi có sẵn ở trang cũ không có route; code Workspace 0 lỗi |
| WU-2 | Trung bình | `axios` ^1.11 (bản cũ và widget) có cảnh báo `npm audit`; Workspace không dùng. Nâng phiên bản cần Toma duyệt |
| WU-3 | Thấp | `OutlineTree`, `ImageViewer` làm khi có API của màn (B6); bộ lọc/khoảng ngày đang nằm riêng trong màn hội thoại |
| WU-4 | Trung bình | Contract B1 là giả định của frontend (README mục Contract) |
| WU-5 | Thấp | 14.2 và 14.3 khác nhau về báo khoá/vô hiệu; B1 cần chốt |
| WU-6 | Thấp | Chưa có lối vào đổi mật khẩu tự nguyện (màn Hồ sơ không có trong mock v1) |
| WU-7 | Thấp | Chi tiết hội thoại vẫn tải mọi lượt (`/history` không `limit`); chuyển sang phân trang cần đầu trang từ `/conversations/{id}` |
| WU-8 | Thấp | Bundle JS ~500 kB (Vite cảnh báo); tách code theo route ở GĐ 6, khi bỏ bản cũ |
| WU-9 | Thấp | Điện thoại: màn chi tiết và diễn biến chưa ẩn thanh dưới như mẫu mục 17 |
| WU-11 | Thấp | Độ khớp là điểm fused (dữ liệu thật ~0,03), thanh độ khớp gần như rỗng dù đoạn được dùng; Q23 đã ghi "chưa đổi thang" |
| WU-12 | Thấp | B2/B3/B5 chỉ có trong worktree này cho tới khi merge. Lượt ghi trước B5 không có tên tài liệu/mục trên thẻ đoạn |
| WU-13 | Thấp | Lỗi công cụ CRM đã có câu dễ hiểu và kết luận; mã HTTP cụ thể (vd 404) chỉ có ở màn Diễn biến khi lượt có trace |
| WU-14 | Thấp | Bộ lọc Model sản phẩm: 7 mục khai báo tạm ở `status.js` (Q16 muốn lấy từ registry, B8); lượt cũ lưu `ASTRO_10S`/`ASTRO_10I` nên không khớp mã `10S`/`10i` |

## Kết quả kiểm gần nhất

| Ngày | Lệnh | Kết quả |
|---|---|---|
| 2026-11-18 | playwright-cli, preview 5174 + backend thật, 1440×900 và 375×812 | Kiểm duyệt khoảng cách, cỡ chữ, nút, sự kiện: 9 lỗi đã sửa (LOG); bộ lọc điện thoại dạng chip + sheet theo mock |
| 2026-11-18 | `npm test` | 11 file, 87 test đạt |
| 2026-11-18 | Preview 5174 + backend B2 thật, 1440×900 và 375×812 | 30 ngày: 14 hội thoại / 3 chuyển nhân viên / 222 câu hỏi / 199 đ; tìm không dấu có tô sáng; "Khớp ở lượt 62" mở chi tiết cuộn đúng lượt, khung nguồn lượt 62, quay lại giữ bộ lọc; Tháng trước → 10 hội thoại, thẻ khoảng ngày; điện thoại không tràn ngang |
| 2026-11-18 | `npx eslint src/workspace` | 0 lỗi (toàn repo: 141 lỗi có sẵn, WU-1) |
| 2026-11-18 | `npm run build` | Đạt; không có dữ liệu giả trong bundle production |
| 2026-11-18 | Preview 5174 + backend B5 thật, 1280×800 | Hội thoại CRM 95 lượt: nhãn và khung nguồn đúng từng loại; lượt 95 hiện bảng công cụ (6 lần gọi, 5 lỗi) |

## Bước tiếp theo

1. Toma duyệt và commit B2 (backend + giao diện + SQL đã áp).
2. Nạp credit OpenAI dev để kiểm chi phí của lượt thành công; chốt WU-11 (cách hiện độ khớp).
3. B8 registry model (WU-14), phân trang chi tiết (WU-7); GĐ 3/4/5 khi có B7, B1, B6.
