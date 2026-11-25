# Nhật ký luồng workspace-ui

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính và trỏ tới nó. Khi file vượt 300 dòng, cắt các mục cũ
sang `LOG-archive-<ngày của mục mới nhất bị cắt>.md` và để lại liên kết ở đầu file.

Sau khi thêm mục, viết lại [STATE.md](STATE.md).

## 2026-11-25 · Câu trả lời hiện Markdown, huy hiệu trích dẫn tròn bấm tới đoạn nguồn, lượt lỗi nói nguyên nhân (WU-17 đợt 1) · loại: thay đổi, quyết định

- Vấn đề (đề xuất của Toma 2026-11-25): chi tiết hội thoại hiện câu trả lời như chữ thô (`### Cách sử dụng bộ điều
  khiển F86`); `[S1]` là chữ, không dẫn tới đoạn nguồn; lượt lỗi ("Kích thước của F54") chỉ ghi "Lượt này không có nguồn";
  widget không hiện bảng vì `react-markdown` thiếu GFM dù prompt (`prompts/answer.py`) yêu cầu bảng.
- Quyết định (Toma duyệt 2026-11-25, chọn "Làm đợt 1"): chia 3 đợt. Đợt 1 chỉ frontend (mục này). Đợt 2 backend nhỏ: ảnh
  lưu theo lượt và ký lại khi đọc, `vector_score` cho thang 1–10 (WU-11), mã lỗi ghi vào lượt, `history_id` trong `done`.
  Đợt 3 vẽ mock trước: dòng hoạt động AI (event `status`), cửa sổ PDF (chờ đồng bộ CRM), liên kết từ chat CRM (chờ B1).
  Thêm dependency `remark-gfm` ^4.0.1 (TR-08, duyệt cùng đợt 1).
- Thay đổi:
  - `src/components/Markdown.jsx` (+ `.module.css`, `markdownCitations.js`) dùng chung widget và Workspace: GFM (bảng
    cuộn ngang trong khung, danh sách, trích dẫn, code), không render HTML thô, link chỉ http(s)/mailto mở tab mới, ảnh
    markdown chỉ hiện chữ; `[S#]` → huy hiệu tròn xám (bỏ qua trong code).
  - Chi tiết hội thoại: câu trả lời và nội dung đoạn hiện Markdown (thu gọn 3 dòng bằng `max-height` + mờ dần); bấm huy
    hiệu → chọn lượt đó, khung "Nguồn câu trả lời" mở và cuộn tới đoạn có `source_id` (viền nổi); di chuột hiện "tài liệu ·
    tr. N" khi đoạn đã tải; dòng nguồn của đoạn thêm trang (`page_label` bỏ chữ "page").
  - Lượt lỗi: khung nguồn đọc trace của lượt (`describeTrace`, cùng câu với màn Diễn biến) → "Lượt này thất bại ở bước …"
    + lời giải thích nhà cung cấp + mã lỗi; lượt `has_trace=false` hoặc không có trace thì nói rõ không rõ nguyên nhân.
  - File: `features/conversations/{ConversationDetailPage,SourcePanel,RetrievalDocs}.jsx`, `sources.js`, `detail.module.css`,
    `strings.vi.js`; test `src/components/Markdown.test.jsx`, `conversations.test.jsx` (+3 ca). Widget: mục website-qa cùng ngày.
- Kiểm chứng: `npm test` → 13 file, 95 test đạt; `npx eslint` các file đã sửa → 0; `npm run build` đạt. Preview 5174 +
  backend thật: hội thoại "Okay, vậy F86…" lượt 40 hiện tiêu đề/danh sách, bấm ⑨ cuộn tới đoạn #4 (S9) đã mở; "Kích thước
  của F54" hiện "thất bại ở bước Phân tích câu hỏi · khóa API OpenAI không hợp lệ · `invalid_api_key`".
- Ảnh hưởng contract/API: không (chỉ đọc `/retrieval`, `/trace`, `has_trace` sẵn có).
- Chưa kiểm / mở tiếp: nhãn dưới lượt lỗi vẫn ghi "Không có nguồn" (bấm mới thấy nguyên nhân); gợi ý huy hiệu ở Workspace
  là `title` của trình duyệt, chỉ có tên tài liệu với lượt đang xem; chưa kiểm điện thoại (sheet); `npm run lint` toàn repo
  185 lỗi có sẵn ở trang cũ, script skill impeccable, `mock-preview` (WU-1). Chưa commit.

## 2026-11-18 · Sidebar: khối tài khoản sát đáy; cỡ chữ gợi ý trên điện thoại; merge và push · loại: thay đổi

- Vấn đề: Toma tự chỉnh CSS ở checkout chính (`.account { margin-top: 312px }`, khoảng cách menu 8px,
  `.control::placeholder { font-size: 14px }`) và yêu cầu làm lại cho linh động. Nguyên nhân gốc: `.nav { flex: 1 }`
  đặt trên `<ul>`, còn con trực tiếp của sidebar là `<nav>` không giãn, nên khối tài khoản nằm ngay dưới menu;
  312px cố định thì màn thấp đẩy khối ra ngoài, màn cao không sát đáy.
- Quyết định/luật (Toma duyệt):
  - `<nav>` của sidebar có class `navArea` (`flex: 1; min-height: 0`): khối tài khoản luôn sát đáy, menu tự cuộn
    khi thiếu chỗ; không dùng khoảng cách cố định. Giữ khoảng cách menu 8px theo Toma;
  - chữ gợi ý 14px chỉ trong media ≤ 720px (chữ gõ 16px để iOS không tự phóng to); máy tính vốn 14px;
  - hai bản sửa tay ở checkout chính được gỡ sau khi commit bản thay thế.
- File: `layout/AppShell.jsx`, `layout/AppShell.module.css`, `components/ui.module.css` (commit `91ca132`).
- Kiểm chứng: playwright-cli ở 1366×600, 1280×720, 1440×900, 1920×1080 và khi thu gọn: khối tài khoản cách đáy
  16px, luôn thấy; điện thoại: chữ gõ 16px, gợi ý 14px, gợi ý vừa ô. `npm test` → 87 đạt; eslint `src/workspace` → 0.
- Nhánh: `0169885` (9 sửa lỗi kiểm duyệt) và `91ca132` merge vào `feature/deploy_ai_service` thành `7599b30`
  (sau commit `0da64e9` của Toma: skill impeccable, cấu hình Playwright, `vite.config.js` bỏ theo dõi `data/`,
  `.claude/`); test trên checkout chính 87 đạt; Toma tự push.
- Quy trình (Toma 2026-11-18): kiểm duyệt giao diện bằng `playwright-cli` (đo khoảng cách, cỡ chữ, vùng bấm, thao tác
  sự kiện trên dữ liệu thật, 1440×900 và 375×812) trước khi đưa thay đổi giao diện lên nhánh deploy.

## 2026-11-18 · Kiểm duyệt giao diện B2 bằng playwright-cli, sửa 9 lỗi · loại: thay đổi

- Vấn đề (Toma yêu cầu kiểm khoảng cách, cỡ chữ, nút, sự kiện bằng playwright-cli trên nhánh
  `feature/deploy_ai_service`, dữ liệu thật, 1440×900 và 375×812):
  1. lọc khoảng tuỳ chọn: ô Thời gian và "Sửa" xuống dòng thứ hai, chữ bị cắt ("31/10/202");
  2. điện thoại: 5 ô lọc xếp chồng chiếm hết màn đầu (mock dùng ô tìm + chip + sheet);
  3. điện thoại: bảng chọn ngày tràn ngang, bị thanh dưới che nút Áp dụng;
  4. đang lọc "Chuyển nhân viên" mà chọn kênh CRM: URL vẫn giữ `status=handoff`, đổi lại Website thì bộ lọc ẩn bật lại;
  5. bấm ra ngoài không đóng bảng chọn khoảng (mock có lớp nền);
  6. nút chat thử che thẻ cuối trên điện thoại và đè lên sheet/hộp thoại (widget cũ z-index 1200);
  7. con số ô "Chi phí AI" thấp hơn 3 ô kia 5px (nhãn "Ước tính" làm hàng nhãn cao hơn);
  8. nút nhỏ: × của thẻ khoảng 22px, nút chọn nhanh 31px, link quay lại 19px;
  9. điện thoại: chỉ dòng tiêu đề của thẻ hội thoại bấm được.
- Quyết định/luật (Toma: sửa tất cả): theo mock v47 (Conversations, MobileConversations):
  - tách `ConversationFilters.jsx` (máy tính: hàng ô lọc, bảng chọn khoảng có lớp nền; thẻ khoảng có "Sửa" và ×;
    điện thoại: ô tìm, chip "Bộ lọc · n" / khoảng / bộ lọc đang dùng có ×, sheet chỉnh nháp với "Đặt lại" và
    "Xem n hội thoại" đếm theo nháp sau 300 ms) và `filterModel.js` (bộ lọc URL → tham số API);
  - đổi kênh sang CRM xoá `status=handoff` trên URL; ô Thời gian 200px, nhãn "Tuỳ chọn: 01/10 – 31/10";
  - hàng nhãn ô số liệu cao cố định 22px; nút chọn nhanh 32px, × và "Sửa" 28px, link quay lại 32px;
  - điện thoại: cả thẻ hội thoại là link (`::after`), đáy trang chừa 96px cho nút chat thử;
  - widget chat cũ trong Workspace hạ z-index xuống 50 (dưới cửa sổ nổi 60, trên nội dung ≤ 30); không sửa widget vì `/legacy` dùng chung.
- Đính chính báo cáo kiểm duyệt: ô nhập trên điện thoại đã 44px / chữ 16px từ trước (`ui.module.css`), không phải lỗi.
- File: `ConversationsPage.jsx`, `ConversationFilters.jsx` (mới), `filterModel.js` (mới), `conversations.module.css`,
  `detail.module.css`, `trace.module.css`, `layout/AppShell.module.css`, `strings.vi.js`; test `conversations.test.jsx` (+3).
- Kiểm chứng: `npm test` → 87 đạt; `npx eslint src/workspace` → 0 lỗi; build đạt. playwright-cli trên preview 5174 +
  backend thật: ô lọc một hàng, chữ ô Thời gian không cắt; × 28px, "Sửa" 28px, nút chọn nhanh 32px; 4 con số cùng y = 311;
  bấm ngoài đóng bảng, URL giữ nguyên; handoff → CRM cho `?channel=crm`; điện thoại: chip "Bộ lọc", "30 ngày qua", sheet
  "Xem 9 hội thoại" (Website, tháng 10), áp dụng → chip "Bộ lọc · 1", "01/10 – 31/10", "Website"; nút áp dụng 44px nằm
  trong màn; nút chat không che thẻ cuối và nằm dưới sheet; bấm vùng meta của thẻ mở chi tiết; link quay lại 32px.

## 2026-11-18 · B2 trên giao diện: bộ lọc, ô số liệu, tìm không dấu có tô sáng, mở đúng lượt khớp (WU-7) · loại: thay đổi

- Vấn đề: trước B2 chỉ có ô tìm (lượt cuối) và lọc trạng thái; "Tải thêm" cắt trang ở trình duyệt.
- Quyết định/luật (theo mock v47, Q12, Q14, Q16, Q19, Q26, Q29):
  - `api/conversations.js`: gửi bộ lọc, `limit` 25, `cursor` lên máy chủ; `metrics()` trả null khi route
    chưa bật (404) → ẩn 4 ô số liệu và "/ y";
  - bộ lọc Kênh, Trạng thái (thêm "Chuyển nhân viên", khoá khi chọn kênh CRM), Model sản phẩm (7 mục, tạm
    khai báo ở `status.js` tới khi có registry B8), Thời gian (Hôm nay / 7 ngày qua mặc định / 30 ngày /
    Tháng này / Tuỳ chọn có bảng chọn, nút nhanh, kiểm ngày, thẻ "Từ … đến … · n ngày" có ×), tất cả trên URL;
  - 4 ô số liệu (không token), cột Số câu hỏi và Chi phí AI (VND);
  - tô từ khớp không dấu (`utils/search.js`, `components/Highlight.jsx`, cùng quy tắc máy chủ); khớp ở lượt
    khác lượt cuối thì thêm dòng "Khớp ở lượt N: …";
  - link chi tiết thêm `?turn=&q=`: chi tiết mở rộng phần lượt đang hiện tới lượt khớp, cuộn tới, viền nét
    đứt, tô từ khoá; khung nguồn chọn sẵn lượt đó.
- Sửa lỗi có sẵn: `state.from` bị đặt trong `to` của `Link` nên nút quay lại từ chi tiết mất bộ lọc.
- File: `ConversationsPage.jsx`, `ConversationDetailPage.jsx`, `timeRange.js`, `status.js`,
  `conversations.module.css`, `detail.module.css`, `api/conversations.js`, `api/fixtures/conversations.js`
  (giả lập B2), `utils/search.js`, `components/Highlight.jsx`, `strings.vi.js`; test `conversations.test.jsx`,
  `api/conversations.test.js`, `utils/search.test.js`.
- Kiểm chứng: `npm test` → 11 file, 84 test đạt; `npx eslint src/workspace` → 0 lỗi; `npm run build` đạt.
  Preview 5174 với backend B2 thật: 14 hội thoại / 3 chuyển nhân viên / 222 câu hỏi (30 ngày); "truc dieu
  khien" tô "điều khiển", "trục"; "khach hang" → "Khớp ở lượt 62", mở chi tiết cuộn đúng lượt 62, khung nguồn
  lượt 62, quay lại giữ bộ lọc; Tháng trước → 10 hội thoại; 375px không tràn ngang. Sửa trong lúc kiểm: cuộn
  tới lượt khớp bị StrictMode chạy effect lần hai đẩy xuống cuối.
- Mở tiếp: chi tiết vẫn tải mọi lượt một lần (chưa dùng `/history?limit`, cần `/conversations/{id}` cho đầu
  trang); danh sách model của bộ lọc chờ B8; dữ liệu cũ lưu `ASTRO_10S` nên lọc "Astro 10S" (`10S`) không ra.

## 2026-11-18 · Lỗi công cụ CRM bằng lời dễ hiểu, kết luận có lấy được số liệu không · loại: thay đổi

- Vấn đề (Toma): bảng công cụ chỉ hiện mã (`tool_invalid_args`) hoặc nhãn ngắn ("Truy vấn CRM không hợp lệ"), người không chuyên kỹ thuật không biết lỗi là gì và câu trả lời có bị ảnh hưởng không; nhãn `crm_query_invalid` còn sai nghĩa với `crm_schema` (thực ra là CRM không có bảng).
- Quyết định/luật (Toma: sửa thẳng trên giao diện, không qua mock):
  - bảng nghĩa mã lỗi công cụ `S.trace.toolError` (câu giải thích + ai xử lý), tra theo `<tool>:<mã>` rồi `<mã>`; mã lạ → "Công cụ báo lỗi chưa có mô tả" + mã kỹ thuật;
  - `features/conversations/toolErrors.js`: đọc `agent_steps` theo thứ tự; lỗi "đã tự sửa" khi cùng công cụ có lần gọi `ok` sau đó; "gọi trùng" (`deduplicated`) đếm riêng, không phải thành công;
  - kết luận đầu bảng: `crm_query` có ít nhất một lần thành công → "Câu trả lời có số liệu từ CRM" (+ "AI gặp lỗi n lần rồi tự sửa"); không thành công lần nào → "Không lấy được số liệu từ CRM; câu trả lời có thể thiếu hoặc sai số liệu";
  - màn Diễn biến dùng cùng bảng nghĩa (cột Kết quả, hộp cảnh báo, chi tiết bước).
- Kiểm chứng: `npm test` → 70 đạt (thêm `toolErrors.test.js` theo đúng hai ví dụ Toma gửi); eslint → 0 lỗi; build đạt. Dữ liệu thật: lượt 90 "Câu trả lời có số liệu từ CRM. AI gặp lỗi 1 lần rồi tự sửa"; lượt 95 "Không lấy được số liệu từ CRM". Sửa trong lúc kiểm: bảng tràn ngang do quy tắc `nowrap` cũ của cột 2.
- Mở tiếp: mã HTTP cụ thể của lỗi CRM (vd 404) chỉ có trong trace; muốn có ở mọi lượt thì backend ghi thêm vào từng bước khi lưu lượt.

## 2026-11-18 · Kiểm B3 với lượt thật (khóa OpenAI hết hạn) · loại: kiểm chứng

- Lượt mới (phiên `10507a81…`) lỗi vì khóa OpenAI hết hạn (chi tiết ở LOG của chat-platform).
- Giao diện: Diễn biến báo "thất bại ở bước Phân tích câu hỏi" + "Khóa API OpenAI của hệ thống đã hết hạn" (thêm câu cho mã `expired_secret_key`, `invalid_api_key` vào `strings.vi.js`, thêm kiểm trong test); Chi tiết kỹ thuật hiện "Token vào / ra 0 / 0 · Số lần gọi AI 1 · Chi phí AI 0 đ"; khung nguồn "Lượt bị lỗi trước khi tra cứu…".
- Kiểm chứng: `npm test` → 65 đạt; eslint → 0 lỗi.
- Chưa kiểm: số liệu của một lượt thành công (cần khóa mới).

## 2026-11-18 · B3: chi phí và token thật trong "Chi tiết kỹ thuật" · loại: thay đổi

- Vấn đề: "Token (ước tính) 82", "Chi phí AI 0,000045 USD" thấp hơn thực tế nhiều lần (chỉ đếm chữ câu hỏi + câu trả lời, giá gpt-4o-mini).
- Quyết định/luật (Toma yêu cầu làm B3): backend ghi usage thật từ trace (LOG của chat-platform). Giao diện: lượt có `usage.source = trace` hiện "Token vào / ra", "Số lần gọi AI", "Chi phí AI" (VND, ghi model chưa có giá nếu có); lượt cũ giữ "(ước tính)" kèm câu giải thích thấp hơn thực tế.
- File: `ConversationDetailPage.jsx`, `strings.vi.js`, `utils/format.js` (`formatVnd`), `detail.module.css`, test.
- Kiểm chứng: `npm test` → 65 đạt; eslint → 0 lỗi; build đạt. Với backend thật: 94 lượt cũ hiện "ước tính", lượt bị chặn không có số liệu; **chưa có lượt mới để thấy số liệu thật**.

## 2026-11-18 · Kiểm B5 với backend thật · loại: kiểm chứng

- Cách kiểm: Toma chạy backend từ `backend/` của worktree (lần đầu chạy nhầm bản ở checkout chính: `/history` không có `sources`, `/retrieval` bỏ qua `history_id`); preview 5174 với `VITE_WORKSPACE_FIXTURES=auth`.
- Kết quả API: hội thoại `c999efd3…` 95 lượt → 81 `crm_data`, 8 `direct`, 3 `documents/no_hits`, 2 `documents/ok`, 1 `none` (bị chặn); `history_id` của phiên khác → 404.
- Kết quả giao diện: nhãn dưới lượt và khung "Nguồn câu trả lời" đúng cho cả 5 loại có trong dữ liệu; lượt 2 (hỏi giá F86, ngoài phạm vi) là "Không tra cứu" đúng; lượt cũ có tài liệu không có tên tài liệu/mục (dữ liệu trước W1).
- Chưa thấy trong dữ liệu thật: "Tra cứu lỗi", "Tài liệu + CRM" (đã kiểm bằng dữ liệu giả và test).

## 2026-11-18 · B5 và khung "Nguồn câu trả lời" (Q28) · loại: thay đổi

- Vấn đề: Toma duyệt mock version 49 và kế hoạch B5 (gộp đoạn trùng theo `chunk_id`, tên tài liệu tạm `doc_id`).
- Backend (luồng chat-platform, chi tiết ở LOG của luồng đó): `sources` trong `/history`, `/retrieval?history_id`, nguồn của chunk trong snapshot, mã lỗi nhà cung cấp trong trace.
- Frontend:
  - `features/conversations/sources.js` (loại nguồn từ `sources` + trạng thái lượt, nhãn, bảng công cụ, trích dẫn), `SourcePanel.jsx` (7 loại), `RetrievalDocs.jsx` (nhãn "Được trích dẫn [S1]");
  - `ConversationDetailPage.jsx`: nhận biết B5 qua `sources`; có thì nhãn nguồn dưới mỗi lượt, chọn lượt (mặc định mới nhất), tải `/retrieval?history_id`; chưa có thì giữ đường cũ;
  - `api/conversations.js` `retrievalForTurn`; dữ liệu giả theo dạng B5.
- Kiểm chứng: `npm test` → 64 đạt; eslint → 0 lỗi; build đạt, không có dữ liệu giả; preview (STATE.md). Sửa trong lúc kiểm: bảng công cụ bị bóp cột vì nhãn kết quả không xuống dòng.
- Mở tiếp: kiểm với backend thật có B5 (WU-12).

## 2026-11-18 · Mock version 49: khung "Nguồn câu trả lời" (Q28) · loại: thay đổi

- Vấn đề: Toma cần duyệt giao diện khung nguồn theo lượt trước khi làm B5.
- Thay đổi: màn 3 `ConversationDetail` và M3 `MobileConversationDetail` trên canvas. Hội thoại mẫu 10 lượt đủ 7 loại (tài liệu, CRM, cả hai, trả lời thẳng, không tìm thấy, tra cứu lỗi, không có nguồn); nhãn nguồn dưới mỗi lượt; desktop đổi khung phải theo lượt chọn (mặc định lượt mới nhất), điện thoại mở sheet; tiêu đề = câu hỏi cuối; nhãn "Được trích dẫn [S1]"; tên tài liệu tạm là `doc_id`.
- File: scratchpad `qs-mock/project/*.dc.html` (ghép bằng `scripts/q28/splice.js`), bản sao `mock-preview/`.
- Kiểm chứng: `syncheck.js` 19 màn đạt; preview 5175 ở 1440×900 và 390×844: bấm đủ 7 loại, sheet mở/Esc đóng, focus vào nút Đóng, không tràn ngang.
- Mở tiếp: Toma duyệt version 49 (WU-12).

## 2026-11-18 · Tiêu đề hội thoại, khung "Nguồn câu trả lời" (Q28), kế hoạch B5 · loại: quyết định

- Vấn đề: tiêu đề danh sách (câu hỏi cuối) khác tiêu đề chi tiết (câu hỏi đầu) (WU-10); khung tài liệu không nói gì với lượt CRM chỉ dùng công cụ báo cáo hay lượt không tra cứu.
- Quyết định/luật (Toma):
  - tiêu đề chi tiết = câu hỏi cuối (đã sửa `ConversationDetailPage.jsx`, thêm kiểm trong test);
  - khung phải thành "Nguồn câu trả lời · lượt N" theo lượt chọn, nội dung theo loại lượt (FRONTEND_REQUIREMENTS 19.14);
  - lập kế hoạch B5 sau khi đọc luồng backend (19.15): ghi nguồn chunk, hàm tóm tắt nguồn lượt, `/retrieval?history_id`, `sources` trong `/history`, mã lỗi nhà cung cấp trong trace.
- Căn cứ: `routers/workspace.py`, `repositories/history_repository.py`, `schemas/history.py`, `services/chat_service.py` (`_retrieval_snapshot`, `retrieval_status`), `schemas/system/agent.py` (`AgentStep`), `core/tracing.py`, `tests/chatbot/test_history_api.py`.
- Kiểm chứng: `npm test` → 63 test đạt; eslint Workspace → 0 lỗi; `check_ai_docs.py` → đạt.
- Mở tiếp: WU-12 (duyệt kế hoạch, chốt gộp đoạn trùng và tên tài liệu).

## 2026-11-18 · Kiểm GĐ 2 với backend thật · loại: kiểm chứng

- Vấn đề: GĐ 2 mới chạy trên dữ liệu giả (mục ngay dưới).
- Cách kiểm: Toma chạy backend :8000; preview 5174 với `VITE_WORKSPACE_FIXTURES=auth` (đăng nhập giả, hội thoại thật).
- Kết quả: 13 hội thoại; hội thoại CRM `c999efd3…` 95 lượt, tải hết tới "Đầu hội thoại", tài liệu của lượt 7; trace 12/11 (5/6 lần dùng công cụ lỗi) và 17/11 (lỗi ở Phân tích câu hỏi, chưa có mã lỗi nhà cung cấp vì W2 chưa làm).
- Sửa: span gốc lỗi mang mã SSE (`analysis_error`) nên hiện nguyên mã; nay các mã `*_error` hiện "Lỗi" (`traceModel.js`, thêm test).
- Phát hiện, chưa sửa (cần Toma chốt): WU-10 tiêu đề danh sách là câu hỏi cuối, tiêu đề chi tiết là câu hỏi đầu; WU-11 độ khớp fused ~0,03 làm thanh độ khớp gần rỗng.
- Kiểm chứng: `npm test` → 63 test đạt; eslint Workspace → 0 lỗi; `npm run build` → đạt, không có dữ liệu giả.

## 2026-11-18 · GĐ 2: Lịch sử hội thoại, Chi tiết, Diễn biến (phần đọc) · loại: thay đổi

- Vấn đề: dựng 3 màn hội thoại theo mock v1 khi backend chưa có B2/B5.
- Quyết định/luật:
  - làm theo FRONTEND_REQUIREMENTS 19.13: chỉ tìm (lượt mới nhất) và lọc trạng thái; ẩn bộ lọc, ô số liệu, cột chưa có dữ liệu thay vì lọc hay tính ở trình duyệt;
  - API trả hết một lần nên `listPage` cắt 25 dòng ở trình duyệt, cùng dạng `{ items, next_cursor, total }` như sau B2; chi tiết hiện 20 lượt mới nhất, "Tải lượt cũ hơn" giữ chỗ đang đọc;
  - tài liệu chỉ có ở lượt máy chủ trả về (lượt mới nhất có tra cứu); điện thoại mở tài liệu trong sheet;
  - diễn biến: nhận diện chặn bằng `action=block`, lỗi bằng span lỗi gốc, ngắt bằng `client_disconnected`; 404 `trace_not_found` là trạng thái rỗng;
  - chi phí từng lượt hiện USD ước tính trong "Chi tiết kỹ thuật"; bổ sung `cost_vnd` vào đặc tả 19.4/19.7 để frontend không phải biết tỉ giá;
  - `VITE_WORKSPACE_FIXTURES` nhận danh sách vùng (`auth`, `conversations`) để đăng nhập giả mà hội thoại đọc backend thật; dữ liệu giả nạp có điều kiện `import.meta.env.DEV` (bản build đầu tiên bị lọt dữ liệu giả vì điều kiện chỉ tính lúc chạy, đã sửa).
- File:
  - `src/workspace/features/conversations/` (ConversationsPage, ConversationDetailPage, RetrievalDocs, TracePage, traceModel, status, CSS, test);
  - `api/conversations.js`, `api/fixtures/conversations.js`, `config.js` (`fixturesFor`), `utils/format.js`, `hooks/useMediaQuery.js`, `strings.vi.js`, `WorkspaceApp.jsx`;
  - `api/auth.js`, `features/auth/LoginPage.jsx` (điều kiện dữ liệu giả), `.claude/vite.worktree.config.js`.
- Kiểm chứng: `npm test` → 63 test đạt; eslint Workspace → 0 lỗi; `npm run build` → đạt, không có dữ liệu giả trong bundle; preview 5174 ở 375px và 1280×800 → đạt (STATE.md). **Chưa chạy với backend thật.**
- Ảnh hưởng contract/API/schema: không đổi backend; đặc tả 19.4/19.7 thêm `cost_vnd`.
- Mở tiếp: kiểm với backend thật; WU-7, WU-8, WU-9.

## 2026-11-18 · Chốt cách lấy giờ hỏi (W3) · loại: quyết định

- Vấn đề: `chat_history` ghi một dòng lúc lượt kết thúc nên không có giờ hỏi (FRONTEND_REQUIREMENTS 19.2 W3).
- Quyết định/luật (Toma): `asked_at = created_at − latency_ms`, tính khi đọc; không thêm cột `asked_at`. Thiếu `latency_ms` thì `asked_at = null`.
- File: `docs/ai/FRONTEND_REQUIREMENTS.md` (19.2, 19.7, Trạng thái), STATE luồng này.
- Kiểm chứng: `check_ai_docs.py` → đạt.
- Ảnh hưởng contract/API/schema: không đổi schema; trường `asked_at` của `/history` theo cách tính này.
- Mở tiếp: WU-7 (làm backend B2/B5).

## 2026-11-18 · Đặc tả API hội thoại cho GĐ 2 (B2, B5, registry model) · loại: quyết định

- Vấn đề: màn hội thoại v1 cần lọc/tìm trên toàn bộ dữ liệu, phân trang, chỉ số theo bộ lọc, tài liệu đã dùng theo từng lượt; API hiện trả hết, chỉ xét lượt cuối, chỉ số tính toàn bảng (F8).
- Quyết định/luật (đề xuất, Toma yêu cầu ghi đặc tả): FRONTEND_REQUIREMENTS mục 19.
  - 6 API đọc: sửa `/chatbot/conversations`, `/history`, `/retrieval`; mới `/conversations/metrics`, `/conversations/{id}`, `/product-models`.
  - 3 sửa luồng ghi: lưu nguồn của chunk vào snapshot (W1), mã lỗi nhà cung cấp trong span LLM (W2), giờ hỏi (W3, cần chốt).
  - Chỉ thêm, không gửi `limit` thì trả như cũ để `/legacy` chạy tới GĐ 6.
- Căn cứ: đối chiếu `backend/sql/*.sql`, `db/models/*.py`, `services/chat_service.py` (ghi một dòng `chat_history` lúc lượt kết thúc; `_retrieval_snapshot` bỏ `doc_id`/`section_title`), `repositories/history_repository.py` (`list_conversations`, `aggregate_metrics`).
- File: `docs/ai/FRONTEND_REQUIREMENTS.md` (mục 19, bảng B2/B5, Trạng thái, 18.4), `docs/ai/api_guidelines.md` (trỏ tới mục 19), README và STATE luồng này.
- Kiểm chứng: `check_ai_docs.py` → đạt.
- Ảnh hưởng contract/API/schema: chưa đổi code; khi làm, route thuộc chat-platform phải cập nhật api_guidelines và test (TR-06).
- Mở tiếp: WU-7 (chốt W3, làm backend).

## 2026-11-18 · GĐ 1: đăng nhập, đổi mật khẩu bắt buộc, đặt lại mật khẩu (giao diện) · loại: thay đổi

- Vấn đề: GĐ 0 chỉ có trang đăng nhập tạm; 14.3 cần đăng nhập, đổi mật khẩu bắt buộc, đặt lại từ link admin.
- Quyết định/luật:
  - màn đăng nhập theo mock M1 (Main, MobileLogin); không điền sẵn email mẫu như mock;
  - sai thông tin: một câu chung; khoá: kèm giờ mở nếu backend gửi `locked_until`; vô hiệu: bảo liên hệ admin;
  - `must_change_password` → `RequireAuth` chuyển mọi trang sang `/change-password?next=…`; nút phụ là Đăng xuất;
  - link đặt lại được kiểm ngay khi mở; đặt xong về đăng nhập với email điền sẵn;
  - kiểm mật khẩu ở trình duyệt theo 14.2 (≥ 12 ký tự, không trùng email, khác mật khẩu cũ, nhập lại khớp); server vẫn kiểm cuối;
  - đổi mật khẩu không bỏ qua xử lý 401 (401 = hết phiên); sai mật khẩu hiện tại dự kiến là 400 `invalid_current_password`.
- File:
  - `src/workspace/features/auth/` (LoginPage, ChangePasswordPage, ResetPasswordPage, AuthLayout, NewPasswordFields, usePasswordForm, authMessages, auth.module.css, auth.test.jsx);
  - `api/auth.js`, `api/fixtures/auth.js` (kịch bản giả), `api/errors.js` (giữ trường thêm của `detail`);
  - `auth/` (guard bắt đổi mật khẩu, `setUser`, `changePasswordPath`); `components/ui.jsx` (`PasswordField`, banner thành công);
  - `WorkspaceApp.jsx` (route `/reset-password`, `/change-password`); bỏ `pages/LoginPlaceholderPage.jsx`.
- Kiểm chứng: `npm test` → 43 test đạt; eslint code Workspace → 0 lỗi; `npm run build` → đạt; preview 5174 ở 320px và 1280×800 → đạt (STATE.md).
- Ảnh hưởng contract/API/schema: không đổi backend. Contract B1 giả định ghi ở README mục Contract (WU-4).
- Mở tiếp: WU-4, WU-5, WU-6; GĐ 2.

## 2026-11-18 · GĐ 0: khung app, lớp API, đăng nhập phía giao diện, component dùng chung · loại: thay đổi

- Vấn đề: chưa có nền để dựng giao diện v1 (mock version 47); `App.jsx` chỉ có bản Workspace cũ.
- Quyết định/luật (duyệt: Toma, FRONTEND_REQUIREMENTS.md 18.6):
  - thêm Vitest + Testing Library + jsdom (devDependencies; `@testing-library/dom` là gói bắt buộc đi kèm);
  - Workspace mới ở `/`, bản cũ ở `/legacy`;
  - dữ liệu giả `VITE_WORKSPACE_FIXTURES` chỉ khi chạy dev;
  - v1 chỉ tiếng Việt;
  - mở luồng tài liệu này.
- Quyết định thêm: lớp API dùng `fetch` thay vì `axios`. `npm audit` báo nhiều cảnh báo cho `axios` ^1.11 đang có; không thêm gói mới.
- File:
  - `src/workspace/**` (config, strings, tokens, api, auth, hooks, components, layout, pages, test);
  - `src/App.jsx`, `vite.config.js` (proxy `/workspace`, `/chatbot`; cấu hình test), `index.html` (tiếng Việt, font Inter, tiêu đề);
  - `package.json` (script `test`, devDependencies), `package-lock.json`;
  - `.claude/vite.worktree.config.js` (preview bật dữ liệu giả).
- Kiểm chứng:
  - `npm test` → 27 test đạt;
  - `npx eslint src/workspace src/App.jsx vite.config.js` → 0 lỗi;
  - `npm run build` → đạt;
  - preview 5174 ở 335px và 1280×800 → đạt (STATE.md).
- Ảnh hưởng contract/API/schema: không đổi backend. Frontend giả định contract đăng nhập B1 (`/workspace/auth/*`, cookie `ws_csrf`), chốt khi làm B1.
- Mở tiếp: WU-1 (lint có sẵn), WU-2 (axios), WU-3, WU-4; GĐ 1, GĐ 2.
