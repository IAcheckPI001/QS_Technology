# Trạng thái luồng workspace-ui

Cập nhật: 2026-11-25

Ảnh chụp trạng thái hiện tại. **Viết lại** khi có thay đổi, không nối thêm; lịch sử ghi ở
[LOG.md](LOG.md). Giới hạn: 80 dòng.

## Tóm tắt

- Giao diện v1 đã duyệt (mock version 47, Q1–Q27; Q28 khung nguồn version 49).
- **GĐ 0 xong:** khung app, lớp API, component dùng chung, test.
- **GĐ 1 xong phần giao diện:** đăng nhập, đổi và đặt lại mật khẩu; chỉ chạy với dữ liệu giả, chờ B1.
- **GĐ 2 xong phần đọc trên B2, B3, B5** (D-011, D-012, D-013): Lịch sử hội thoại có đủ bộ lọc (kênh,
  trạng thái, model sản phẩm, thời gian; điện thoại dạng chip + sheet), 4 ô số liệu, tìm không dấu có tô
  sáng và "Khớp ở lượt N", phân trang ở máy chủ; Chi tiết mở đúng lượt khớp; nguồn câu trả lời theo lượt;
  chi phí thật. Đã kiểm duyệt bằng playwright-cli với dữ liệu thật.
- Đã có trên `feature/deploy_ai_service` (merge `7599b30`, Toma push). Workspace mới ở `/`, bản cũ ở `/legacy`.
  Tài liệu, Khóa AI, Tài khoản còn là trang "đang xây dựng".
- **WU-17 đợt 1 (2026-11-25, chưa commit):** câu trả lời và đoạn nguồn hiện Markdown (`src/components/Markdown.jsx`,
  dùng chung với widget, thêm `remark-gfm`); `[S#]` là huy hiệu tròn, bấm thì cuộn khung nguồn tới đoạn; lượt lỗi nói
  nguyên nhân từ trace. Đợt 2 (backend) và đợt 3 (vẽ mock trước) chưa làm.

## Độ chín từng bước

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| GĐ 0 · nền | có | Sidebar: khối tài khoản sát đáy ở mọi chiều cao |
| GĐ 1 · đăng nhập | một phần | Giao diện đủ 14.3 (trừ Hồ sơ); chờ B1 để nối thật và đóng DR-05 |
| GĐ 2 · hội thoại | có (chưa xác thực) | B2/B3/B5 đã nối, kiểm duyệt xong; Markdown + huy hiệu trích dẫn (WU-17 đợt 1); còn tải mọi lượt một lần (WU-7), registry model (WU-14) |
| GĐ 3 · khóa dịch vụ AI | chưa có | Chờ B7 |
| GĐ 4 · tài khoản | chưa có | Chờ B1 |
| GĐ 5 · tài liệu | chưa có | Chờ B6, ảnh trên Storage, sửa T-07 |
| GĐ 6 · hoàn thiện | chưa có | |

## Đang làm

Không có việc dở. Kiểm với dữ liệu thật: backend ở `backend/` của checkout chính (`.env` có
`WORKSPACE_CONVERSATION_API_ENABLED=true`), frontend `npm run dev` với `VITE_WORKSPACE_FIXTURES=auth`.
Kiểm duyệt giao diện bằng `playwright-cli` (1440×900 và 375×812) trước khi đưa lên nhánh deploy.

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| WU-1 | Trung bình | `npm run lint` toàn repo đỏ do 185 lỗi có sẵn (trang cũ không có route, script skill impeccable, `mock-preview`); code Workspace và widget 0 lỗi |
| WU-2 | Trung bình | `axios` ^1.11 (bản cũ và widget) có cảnh báo `npm audit`; Workspace không dùng. Nâng phiên bản cần Toma duyệt |
| WU-3 | Thấp | `OutlineTree`, `ImageViewer` làm khi có API của màn (B6) |
| WU-4 | Trung bình | Contract B1 là giả định của frontend (README mục Contract) |
| WU-5 | Thấp | 14.2 và 14.3 khác nhau về báo khoá/vô hiệu; B1 cần chốt |
| WU-6 | Thấp | Chưa có lối vào đổi mật khẩu tự nguyện (màn Hồ sơ không có trong mock v1) |
| WU-7 | Thấp | Chi tiết hội thoại vẫn tải mọi lượt (`/history` không `limit`); chuyển sang phân trang cần đầu trang từ `/conversations/{id}` |
| WU-8 | Thấp | Bundle JS ~500 kB (Vite cảnh báo); tách code theo route ở GĐ 6, khi bỏ bản cũ |
| WU-9 | Thấp | Điện thoại: màn chi tiết và diễn biến chưa ẩn thanh dưới như mẫu mục 17 |
| WU-11 | Thấp | Độ khớp là điểm fused (dữ liệu thật ~0,03), thanh gần như rỗng; hướng: lưu `vector_score` (cosine), hiện ×10 (WU-17 đợt 2; thang tuyệt đối hay tương đối chờ Toma) |
| WU-17 | Trung bình | Đề xuất nguồn 2026-11-25 còn: đợt 2 (ảnh theo lượt ký lại khi đọc, `vector_score`, mã lỗi vào lượt, `done.history_id`); đợt 3 (dòng hoạt động AI, cửa sổ PDF, liên kết từ CRM, chờ B1 và đồng bộ CRM). Nhãn dưới lượt lỗi vẫn "Không có nguồn"; chưa kiểm sheet điện thoại |
| WU-12 | Thấp | Lượt ghi trước B5 không có tên tài liệu/mục trên thẻ đoạn |
| WU-13 | Thấp | Lỗi công cụ CRM đã có câu dễ hiểu và kết luận; mã HTTP cụ thể (vd 404) chỉ có ở màn Diễn biến khi lượt có trace |
| WU-14 | Thấp | Bộ lọc Model sản phẩm: 7 mục khai báo tạm ở `status.js` (Q16 muốn lấy từ registry, B8); lượt cũ lưu `ASTRO_10S`/`ASTRO_10I` nên không khớp mã `10S`/`10i` |
| WU-15 | Thấp | Máy tính: ô tìm hẹp lại khi ô Thời gian rộng 200px, chữ gợi ý dài bị cắt cuối |
| WU-16 | Thấp | Nút chat thử (widget cũ, z-index gốc 1200) chỉ được hạ lớp trong Workspace; `/legacy` giữ nguyên |

## Kết quả kiểm gần nhất

| Ngày | Lệnh | Kết quả |
|---|---|---|
| 2026-11-25 | `npm test`; eslint file đã sửa; `npm run build` | 13 file, 95 test đạt; 0 lỗi; đạt |
| 2026-11-25 | Preview 5174 + backend thật | Markdown lượt 40 (F86), bấm ⑨ cuộn tới đoạn S9; lượt lỗi "Kích thước của F54" → `invalid_api_key` ở bước Phân tích |
| 2026-11-18 | playwright-cli, 1366×600 → 1920×1080 và thu gọn | Sidebar: khối tài khoản cách đáy 16px ở mọi cỡ; menu cách 8px; điện thoại chữ gõ 16px, gợi ý 14px |
| 2026-11-18 | playwright-cli, preview 5174 + backend thật, 1440×900 và 375×812 | Kiểm duyệt khoảng cách, cỡ chữ, nút, sự kiện: 9 lỗi đã sửa (LOG); bộ lọc điện thoại dạng chip + sheet theo mock |
| 2026-11-18 | `npm test` (worktree và checkout chính sau merge) | 11 file, 87 test đạt |
| 2026-11-18 | `npx eslint src/workspace` | 0 lỗi (toàn repo: 141 lỗi có sẵn, WU-1) |
| 2026-11-18 | `npm run build` | Đạt; không có dữ liệu giả trong bundle production |
| 2026-11-18 | Preview 5174 + backend B2 thật | 30 ngày: 14 hội thoại / 3 chuyển nhân viên / 222 câu hỏi / 199 đ; "Khớp ở lượt 62" mở chi tiết cuộn đúng lượt; Tháng trước → 10 hội thoại |

## Bước tiếp theo

1. Toma: commit đợt 1; chốt thang điểm (WU-11), ai mở Workspace từ CRM, mock dòng hoạt động AI; rồi làm WU-17 đợt 2.
2. B8 registry model (WU-14), phân trang chi tiết (WU-7).
3. GĐ 3/4/5 khi có B7, B1, B6.
