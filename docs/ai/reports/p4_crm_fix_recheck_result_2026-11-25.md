# Kết quả đối chiếu chunk `fix`/`pending` đợt 1: 4 bản CRM F54 và F86 (2026-11-25)

Run `crm-1.2-a` (dựng từ raw `crm-1.0-a`, code Bậc 0, build bằng venv có `tiktoken`). Kế hoạch: [p4_crm_fix_recheck_plan_2026-11-25.md](p4_crm_fix_recheck_plan_2026-11-25.md).
Verdict ghi trong `data/ingest_runs/<tài liệu>/crm-1.2-a/build/chunk_review.json` (bản sao `.bak-before-recheck`) và `data/ingest_runs/_summary/recheck-2026-11-25/fix_recheck.csv` (gitignored).

**Độ tin cậy:** người duyệt là model, **chưa người xác nhận**. `f54-installation-en` và `f86-installation-en` do Claude duyệt trực tiếp trên ảnh trang; `f86-operation-en` và `f54-operation-en` do hai subagent duyệt, Claude kiểm mẫu lại 2 chunk mỗi tài liệu trên ảnh trang (4/4 đúng). Các chunk lân cận không nằm trong danh sách duyệt chưa được kiểm; một số kết luận "thiếu bước" có thể thực ra nằm ở chunk kề.

## Kết quả

| Tài liệu | Chunk duyệt | Lỗi xác nhận (`fix`) | Dùng được kèm ghi chú | Báo động giả |
|---|---|---|---|---|
| f54-installation-en | 3 | 3 | 0 | 0 |
| f86-installation-en | 6 | 5 | 0 | 1 |
| f86-operation-en | 37 | 27 | 9 | 1 |
| f54-operation-en | 71 | 56 | 14 | 1 |
| **Tổng** | **117** | **91** | **23** | **3** |

Mức nghiêm trọng (117 chunk): S1 sai giá trị/mã/chân/bước 32; S2 thiếu nội dung 56; S3 hình thức 26; 3 chunk không có mức. Hành động đề xuất: `manual_curate` 51, `rule_fix` 38, `re_ocr` 15, `merge` 6, `drop_chunk` 4, `none` 2, `exclude_pages` 1.
Cả 24 chunk `pending` đã có verdict; không còn chunk `pending` trong đợt này.

## Nguyên nhân gốc (chunk `fix_confirmed`, phân nhóm thô theo ghi chú)

| Nhóm | Chunk | Biểu hiện | Hướng xử lý |
|---|---|---|---|
| I-58 / I-57: chữ trong ảnh bị mất, ảnh màn hình thành bảng | 38 | Chunk chỉ còn tiêu đề/caption của sơ đồ đấu dây, board I/O, MPG; thông tin (màu dây, chân) nằm trong ảnh. Ảnh màn hình COORD mất dấu trừ (`-154.497` thành `154.497`) | `manual_curate` (đã có ánh xạ đọc từ trang trong ghi chú) hoặc đọc ảnh; `drop_chunk` cho ảnh COORD lặp (B0085, B0091, B0098, B0107 của F54) |
| I-59: ảnh nuốt chữ thủ tục | 19 | Mất Step 1–2 hoặc cả thủ tục (chữ Step nằm trong khung Memo cạnh ảnh) | Sửa luật T-20 mở rộng, `merge` với chunk kề |
| I-51: OCR hỏng chữ | 16 | `0-10V` thành `O-1OV`, `M100` thành `M1o0`, mất IP `192.168.1.225`, mất mật khẩu `1415`, mất cảnh báo an toàn | `re_ocr` hoặc sửa tay; mức S1 |
| I-56 / I-56b: bảng gán sai hàng, hàng nối tiếp mất tên cổng | 13 | F54 Installation: X47 gán CN7 thay vì CN6, Y40/CY0 gán CN4; F86 Installation: X57 gán CN17, FG gán CN3; bảng tham số chương 4: `6: port 6` gán sang hàng #4160, `pulse/round` gán sang hàng #12350 | Luật T-15b và xếp lại cell theo `words.json` (cần Toma duyệt) |
| Bảng bị tách (`chunk_split`) | 5 | Các phần sau không có tiêu đề cột, hàng #8090 bị dùng làm hàng tiêu đề giả | Lặp tiêu đề cột và tiêu đề mục khi tách |

Bằng chứng nền: lỗi X47, Y40, CY0 của F54 Installation đã có trong raw Docling (cell CN7 chứa `…CX2 X47`); luật T-15 `merge_continuation_rows` chỉ gộp hàng nối tiếp trong cùng trang nên hàng đầu mỗi trang không có tên cổng thành `orphan_row`.

## Ví dụ lỗi S1 đã kiểm trên ảnh trang
- F54 Installation B0005: X47 thuộc CN6, chunk ghi vào CN7; Y40, CY0 thuộc CN5, chunk ghi vào CN4.
- F86 Installation B0008: X57 thuộc CN16, chunk ghi vào đầu CN17.
- F86 Operation B0040: hàng cuối bảng chú thích hình 3-1 là số 9 (Machine coordinate system), chunk ghi số 6 trùng hàng 6.
- F86 Operation B0108: `6: port 6` thuộc hàng #4150 (Axis encoder port), chunk gán sang hàng #4160 (Axis encoder multiply).
- F54 Operation B0129: IP `192.168.1.225` có trên trang 94 nhưng chunk bị OCR thành chữ rác.

## Phát hiện về nguồn PDF (chunk chép đúng chữ nguồn, nên báo tác giả)
- F54 Installation: nguồn in `DIR+` thay `DIR3+` ở CN10.
- F86 Installation: lỗi chính tả `combie`, `X40 – X47` ở mô tả CN17 (đúng là X60–X67), nhắc `axis 1, combie with (D1-)` ở D2+.
- F86 Operation: bước 2 của một thủ tục ghi `divided by 2` dù ảnh cho thấy X về 0.000.
- F54 Operation: trang 22–23 `Input port 3 in IN24-IN31 = X320-X327` trùng port 2; số hình 2-21/2-22 và 2-23/2-24 bị trùng; trang 52 ghi `arrow on the left` nhưng ảnh bấm mũi tên phải; trang 14 ghi `high input` dưới tiêu đề low input.
- Cả hai tài liệu Installation: số hiệu cổng trong sơ đồ (CN2, CN3…) khác số hiệu trong bảng (ví dụ sơ đồ F86 có CN3 là D+, D-, FG, bảng gọi là CN2); chưa kiểm hết.

## Báo động giả của bộ duyệt tự động cũ
3 chunk `false_positive` (F86 Installation B0004, F86 Operation B0107, F54 Operation B0117) và 23 chunk chỉ cần ghi chú. Ghi chú cũ sai ở ít nhất: F54 Installation B0004 ("lệch cột"; thực tế là hàng nối tiếp mất tên cổng), F86 Operation B0017/B0023 (quá nặng), F54 Operation B0069/B0088/B0136.

## Đề xuất luật (chờ Toma duyệt; chưa sửa code)
1. **T-15b:** gộp hàng đầu trang có ô khoá rỗng vào hàng cuối trang trước của cùng bảng logic. Ảnh hưởng mọi bảng nhiều trang trong 10 tài liệu; cần chạy `pytest tests\doc_ingest` và so trước/sau trên cả 10 tài liệu.
2. **I-56 (gán sai chân):** xếp lại chân theo hàng bằng toạ độ chữ trong `words.json`; phức tạp hơn T-15b, hoặc biên soạn tay các bảng cổng (như catalog).
3. **Bảng bị tách:** lặp tiêu đề cột và tiêu đề mục ở mỗi phần.
4. **I-59:** mở rộng T-20 cho khung Memo cạnh ảnh.

## Quyết định cần Toma
1. Duyệt T-15b và hướng xử lý I-56 (luật hay biên soạn tay).
2. Chính sách chunk hình chỉ có caption: biên soạn tay nhãn trong ảnh (đã có ánh xạ), gộp với chunk kề, hay bỏ.
3. Xác nhận mẫu verdict (đặc biệt 32 chunk S1 và 23 chunk "dùng được kèm ghi chú") trước khi ghi vào `chunk_review.json` chính thức.
4. I-53 (gỡ mã chặn) để chunk đã duyệt có thể sang `approved`.

## Chưa làm
- Chunk không nằm trong danh sách duyệt (343 chunk `ok` cũ của 4 tài liệu và chunk cha) chưa kiểm ngược.
- Mục 4.5 MACRO PARAMETER (trang 106, `#0048`, `#0049`, `#8110–#8149`) không nằm trong danh sách duyệt nên chưa đánh giá.
- 6 tài liệu còn lại (10iv, 6ah, 6ave ×2, f10t ×2) được đối chiếu ở đợt 2, phần dưới.

---

# Đợt 2: 6 tài liệu còn lại (2026-11-25)

Cùng run `crm-1.2-a` (dựng từ raw `crm-1.0-a`; `10iv-operation-en` vẫn dùng raw cũ nên I-55 ở trang 107–110 chưa sửa). Verdict ghi trong `crm-1.2-a/build/chunk_review.json` của từng tài liệu và `fix_recheck.csv` (gitignored). Người duyệt: 5 subagent Claude mở ảnh trang; Claude kiểm mẫu 1–2 chunk mỗi tài liệu (F10T Installation mở ảnh trang 12; các tài liệu còn lại kiểm qua nội dung chunk). Chưa người xác nhận.

| Tài liệu | Chunk duyệt | Lỗi xác nhận (`fix`) | Dùng được kèm ghi chú | Báo động giả | Ghi chú |
|---|---|---|---|---|---|
| 6ave-installation-vi | 11 | 8 | 2 | 1 | |
| f10t-installation-vi | 13 | 11 | 1 | 1 | |
| 10iv-operation-en | 52 | 46 | 3 | 3 | chương 4 mất chữ số (I-55) |
| 6ave-operation-en | 61 | 49 | 11 | 1 | |
| 6ah-operation-en | 63 | 51 | 10 | 2 | |
| f10t-operation-vi | **55/115 (mẫu)** | 24 | 29 | 2 | 29 chunk rớt dấu giữ verdict `fix` (I-29) |
| **Tổng** | **255** | **189** | **56** | **10** | |

**Cả 10 tài liệu (372 chunk đã duyệt):** lỗi xác nhận 280, dùng được kèm ghi chú 79, báo động giả 13. Mức nghiêm trọng: S1 72, S2 202, S3 85, 13 chunk không có mức. Nhóm nguyên nhân (chunk lỗi): I-58/I-57 120, I-59 59, I-51 42, I-56/I-56b 39, bảng bị tách 14, I-60 3, khác 3. Hành động đề xuất: `manual_curate` 148, `rule_fix` 118, `re_ocr` 67, `merge` 17, `drop_chunk` 7, `exclude_pages` 2, `none` 13.

## Điểm đáng chú ý của đợt 2
- **10iv chương 4 (B0109–B0116, S1):** mã parameter mất chữ số 0, 1, 2, 4, 5, 6, 8 và chữ "m" (`#0000 - #0007` thành `# - # 7`, `0:Disable – 1:Enable` thành `:Disable - :Enable`, cột Default trống). Đây là lỗi text layer đã biết (I-55); cần re-OCR hoặc trích lại cả chương, vì mã parameter không dùng được.
- **Bảng cổng Installation (F10T B0014/B0015, S1):** X57 thuộc CN17 nhưng chunk ghi vào CN18 (đã kiểm trên ảnh trang 12), cùng mẫu lỗi X47 (F54) và X57 (F86).
- **Số hàng "9" ghi thành "6"** ở bảng chú thích hình 3-1 của 6AVE (B0049) và 10iV (B0040), giống F86 Operation.
- **Bảng tham số chương 4** (cả 5 tài liệu Operation): tách chunk không có tiêu đề cột và tiêu đề mục 4.x, hàng `#8090` bị lặp làm tiêu đề giả, `6: port 6` và `pulse/round` gán sai hàng (S1), `#0064/#0065` của mục 4.3 dính vào mục 4.2.
- **F10T, OCR tiếng Anh trên tài liệu Việt (I-29):** 45/46 chunk có chữ Việt trong mẫu bị rớt dấu (~98%); 3 chunk hỏng tới mức không đọc được (B0001, B0029, B0135). Heading chương 3 bị OCR thành rác (`3 TI) G G H G G G RO`) trong section path của 34/55 chunk mẫu. Mất nội dung thật ước ~15–25% cho cả tài liệu (ước lượng của agent, mẫu thiên về chunk hình và pending).
- **Thủ tục 3.8.1** của 6AH, 6AVE đã có Step 1–2 sau Bậc 0 (xác nhận); lỗi còn lại là nhiễu lặp "Model: ASTRO 6AV…" và mật khẩu `1 415`.
- **Quan sát chưa kiểm chứng (từ agent):** ảnh trang F10T trông là chữ sắc nét chứ không phải scan; nếu PDF có text layer, trích trực tiếp có thể thay OCR cho I-29 (trong thư mục run chỉ có ảnh trang, chưa kiểm PDF).

## Lỗi của chính PDF nguồn (đợt 2; chunk chép đúng chữ nguồn)
- Input port 3 ghi `IN24(X320)–IN31(X327)` trùng port 2 (6AH tr.28–29, 6AVE tr.35–36, 10iV tr.36–37).
- 3.2.3 Step 2 ghi `divided by 2 automatically` (chép nhầm từ HALF) ở 6AH, 6AVE, 10iV.
- 3.3.6 Step 1 ghi mũi tên bên trái, ảnh bấm mũi tên bên phải (6AVE tr.66).
- Tên firmware trong văn bản và ảnh không khớp (6AVE ghi `ASTRO 6AV_…`, ảnh `ASTRO10i_…`; 6AH ghi `ASTRO 6AH_…`, ảnh `F86_…`).
- Số hiệu cổng: 6AH CN12 xuất hiện cho cả trục Y và Z; 6AVE caption Figure 2-3 ghi CN16–CN18, sơ đồ ghi CN7–CN9.
- Mô tả 6AVE CN9 và F10T CN18 ghi `X50 – X57` thay vì X60–X67; F10T `420mA` có thể là 4–20mA.
- F10T tr.55: ghi `6 hệ tọa độ` nhưng liệt kê 4 mã (thiếu G56); `18 hệ mở rộng G59.1…G59.12` thực tế là 12.
- Lỗi chính tả: `REALCE ALL`, `EXCECUTE`, `SYS.INT`, `diagnostic tale`, `BIn`, `phiển bản`, `hoat động`, `Sáu đó`.

## Đề xuất luật bổ sung sau đợt 2 (chờ Toma duyệt)
5. **Heading chương hỏng trong section path (F10T):** heading `3 TI) G G H G…` do OCR; sửa bằng I-29 hoặc ghi đè heading từ mục lục; ảnh hưởng 34/55 chunk mẫu.
6. **Chương 4 của 10iV:** ép OCR trang 107–110 (luật I-55 đã sửa ở S0; cần parse lại raw 10iV, chưa làm).
7. **Bảng chú thích hình:** kiểm số thứ tự cột 1 liên tục để bắt hàng ghi sai (9 thành 6).

## Chưa làm sau đợt 2
- Chunk không nằm trong danh sách duyệt (chunk `ok` cũ, chunk cha) chưa kiểm ngược; riêng `f10t-operation-vi` còn 60/115 chunk chưa duyệt, giữ verdict cũ của bộ duyệt tự động.
- Nhiều kết luận "thiếu bước" có thể thực ra nằm ở chunk kề ngoài danh sách; các agent ghi `chưa kiểm chunk kề` trong note.
- Mục 4.5 MACRO PARAMETER (cuối chương 4) và "Chú ý" cuối bảng cổng Installation (6AVE tr.11, F10T tr.12) không nằm trong chunk nào của danh sách duyệt; chưa rõ chunk nào giữ.
- Ngưỡng "dùng được kèm ghi chú" là phán đoán của từng agent; `fix_minor` ở `f10t-operation-vi` được giữ `fix`, ở các tài liệu khác đổi sang `ok` theo quy ước.
