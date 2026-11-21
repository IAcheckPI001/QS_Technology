# Kiểm duyệt chunk bị chặn của 10 tài liệu CRM: nhóm lỗi và giải pháp (2026-11-20)

Phạm vi: run `crm-1.0-a` (10 tài liệu bộ điều khiển, 739 chunk lá). 653 chunk bị chặn: 592 chỉ vì OCR chưa kiểm
chứng, 61 do lỗi phát hiện (bảng, hụt text). Báo cáo này xác định nguyên nhân gốc của từng nhóm bằng cách **đối
chiếu chunk với PDF gốc** (ảnh vùng, text layer), và đề xuất giải pháp. Nó **không** ghi verdict vào
`chunk_review.json`: verdict là việc của người duyệt (Toma).

## Phương pháp và mức bằng chứng

- 61 chunk lỗi: mỗi chunk có một verdict đề xuất (`ok`, `ok_ghi_chu`, `can_sua`) kèm nhóm lỗi và mức bằng chứng:
  **16 chunk tôi tự đối chiếu** (ảnh vùng PDF và text layer), **27 chunk do agent độc lập đối chiếu** (tôi kiểm lại hai
  kết luận: dấu âm của F54 `B0085`, chân `X57` của F86 `B0007`, cả hai đúng), **18 chunk suy ra theo nhóm** (nội dung
  trùng hash với chunk đã xem, chưa xem ảnh riêng).
- 592 chunk OCR: chỉ lấy mẫu 24 chunk (4 mỗi tài liệu) nên chỉ là chỉ báo, không phải kết luận thống kê.
- Bảng đề xuất đầy đủ 61 chunk: `data/ingest_runs/_summary/chunk_review_proposed.csv` (không commit, sinh lại được).

Kết quả đề xuất 61 chunk lỗi: **21 `can_sua`**, 38 `ok_ghi_chu`, 2 `ok`. Lưu ý I-53: chunk có mã chặn không thể
`approved` dù verdict là `ok`.

## Nhóm lỗi, nguyên nhân gốc và giải pháp

| ID | Nhóm | Chunk | Ưu tiên |
|---|---|---|---|
| I-55 | Text layer PDF hỏng (10iV tr.107–110) | 3 `can_sua` (+ B0109 ở tr.107) | P0, dễ |
| I-56 | Hàng bảng cổng gán sai, mất hàng (Installation) | 6 `can_sua`, 9 `ok_ghi_chu` | P0, khó |
| I-57 | Ảnh màn hình và sơ đồ dựng thành bảng | 9 `can_sua` | P1, vừa |
| I-58 | Chữ trong ảnh trên trang có text layer bị mất (phụ lục tham số) | 1 `can_sua`, 20 `ok_ghi_chu` | P1, vừa |
| I-59 | Ảnh nuốt chữ thủ tục (`picture_swallows_text`) | ngoài 61 chunk (mẫu OCR) | P1, dễ |
| I-60 | Chunk hình gộp nhiều trang; nhãn tiếng Việt OCR mất chữ | 1 `can_sua` | P2 |
| I-54 | V-01 báo động giả (và bỏ sót lỗi thật) | 8 chunk chỉ trượt V-01 | P1, dễ |

### I-55: text layer của PDF hỏng
- **Triệu chứng:** 10iV `B0110–B0112` (phụ lục tham số): `#8090 - #8097` thành `# 9 - # 97`, `(0.1us)` thành `( . us)`,
  `limit` thành `li it`. Chỉ 1/61 mã `#` của tr.108 còn đủ chữ số.
- **Nguyên nhân:** chính text layer nhúng trong PDF mất các chữ số 0,1,2,4,5,6,8 và chữ `m` (đã kiểm bằng pdfium: text
  layer p108 thiếu y hệt chunk; ảnh trang đúng). Pipeline chép đúng text layer sai; V-01 đối chiếu cùng text layer
  nên không thấy.
- **Giải pháp đã kiểm chứng:** chạy lại `run --ocr force` chỉ trên tr.107–110 (run thăm dò `10iv-probe/probe-ocr-force`):
  số mã `#` đủ ≥ 3 chữ số tăng từ **1/61, 1/30, 0/22** (tr.108, 109, 110) lên **88/88, 54/54, 33/33**; chữ số 88 → 598 ở
  tr.108. Chưa so từng ô với ảnh, nhưng mọi mã đều đủ chữ số và có header (`Parameter | Description | Work range | Default`).
- **Đề xuất:** (1) ngay: manifest 10iV cho phép chỉ định trang ép OCR; (2) luật chung: S0 thêm kiểm toàn vẹn text layer
  (tỉ lệ token `#` không có ≥ 3 chữ số, chữ số quá ít so với số mã) → đánh trang `poor` để dùng nhánh OCR sẵn có.

### I-56: hàng bảng cổng gán sai, mất hàng
- **Triệu chứng (đã đối chiếu PDF):** F54 Installation: `X47` (chân CN6) nằm ở hàng CN7; `Y40`, `CY0` (chân CN5) ở hàng CN4.
  F86 `B0007` và F10T `B0008`: `X57` (chân cuối CN16/CN17) nằm ở đầu cổng kế tiếp (đã kiểm bằng text layer F86). 6AVE `B0003`:
  **hàng ANT mất hẳn** (bị hạ thành header, `header_demotion_unsure`); `B0004`: CN7, CN8, CN9 gộp thành một hàng. F10T `B0004`:
  câu của CN4 bị cắt, CN2 hỏng cột. Hàng bị tách qua ngắt trang tạo mảnh mồ côi không nhãn cổng (13 chunk, không mất dữ liệu).
- **Nguyên nhân:** ô nhiều dòng (danh sách chân, mô tả) gán theo vị trí dọc gần ranh giới hàng của Docling; dòng đầu hoặc cuối ô
  rơi sang hàng kề; hàng đầu trang có ô khóa rỗng không nối được với hàng cuối trang trước.
- **Mức nghiêm trọng:** cao: sai chân tín hiệu có thể dẫn tới đấu nối sai. Toàn bộ 10 run chỉ mất im lặng **1 hàng dữ liệu**
  (ANT) trên 1.342 dòng bảng (7 dòng không thuộc chunk nào, 6 dòng còn lại là hàng header thứ hai của bảng ảnh màn hình).
- **Đề xuất:** (1) trên trang có text layer, dựng lại ô từ từ trong `raw/pN.words.json` và đường kẻ, nền xen kẽ
  (`objects.json`), gán từ theo tâm; (2) gộp hàng nối tiếp qua ngắt trang khi ô khóa rỗng ở đầu trang; (3) hàng bị hạ thành header
  nhưng có hình dạng dữ liệu thì giữ làm dữ liệu và gắn cờ, không bỏ; (4) CQ mới "mọi hàng có chữ của bảng phải thuộc một chunk".
  Tạm thời: không xuất bản 6 chunk `can_sua`.

### I-57: ảnh chụp màn hình và sơ đồ dựng thành bảng
- **Triệu chứng:** F54 Operation chương 3 (`B0042`, `B0085`, `B0086`, `B0088`, `B0091`, `B0092`, `B0098`, `B0107`): ảnh giao diện
  bộ điều khiển thành bảng 5–11 cột; số lớn mất dấu âm (`154.497` thay `-154.497`), `-154.497` dính nhãn `DIS TO GO`, đồng hồ lẫn vào
  header. Năm ảnh COORD gần như trùng (cùng giá trị mẫu), gây nhiễu tra cứu. 6AVE Installation `B0026`: sơ đồ nguồn thành bảng 2 cột.
- **Nguyên nhân:** không có đường kẻ thật trong vùng; Docling suy ra cột và hàng từ chữ OCR; T-09 chưa nhận ra màn hình.
- **Đề xuất:** mở rộng T-09: coi là screenshot nếu có ≥ 2 dấu hiệu: không có nét vector kẻ bảng trong bbox (`objects.json`) nhưng bitmap
  phủ lớn, chuỗi đồng hồ `hh:mm:ss dd/mm/yyyy`, nhãn soft key, nhiều ô rỗng. Khi đó tạo chunk hình + chú thích, không dựng bảng.
  Bảng phím chức năng (cột trái là ảnh biểu tượng) thì giữ bảng: cột mô tả đúng.

### I-58: chữ trong ảnh trên trang có text layer bị mất im lặng
- **Triệu chứng:** phụ lục tham số (Chapter 4, 3 trang cuối) của 5 bản Operation: nội dung bảng đúng so với ảnh nhưng **thiếu tiêu đề mục**
  (`4.2 SPINDLE PARAMETER`, `4.4 USER PARAMETER`) và **hàng tiêu đề cột**; `section_path` chỉ còn `CHAPTER 4.`; kéo theo cảnh báo
  `ambiguous_continuation`. F86 `B0113`: ô khóa `#10000 - #10049` bị tách làm hai ô.
- **Nguyên nhân:** tiêu đề và hàng header là ảnh/vector, không nằm trong text layer (đã kiểm p96); trang có text layer nên không OCR;
  V-01 chỉ đối chiếu text layer nên mù. 5 bản dùng chung nội dung phụ lục (cùng hash), một lần sửa dùng được cho cả 5.
- **Đề xuất:** S0: trang có text layer mà còn vùng ảnh/vector lớn không có chữ phủ → OCR cục bộ vùng đó (mở rộng `figure-ocr`); bảng
  tiếp nối không header thì kế thừa header của đoạn bảng trước.

### I-59: ảnh nuốt chữ thủ tục
- **Triệu chứng (mẫu OCR):** 6AH và 6AVE mất Step 1 và Step 2 của thủ tục 3.8.1: cụm "Select parameter type" có trong dữ liệu thô và trong
  `elements.jsonl` nhưng bị phân loại `figure_text`, không vào chunk nào (F86, F54, 10iV còn đủ). Tín hiệu `picture_swallows_text` cũng có ở F54,
  F10T, 6AH, 6AVE, nên có thể còn mất bước ở thủ tục khác.
- **Đề xuất:** chỉ coi chữ trong vùng ảnh là `figure_text` khi ngắn và sát nhãn; câu hoàn chỉnh hoặc dòng "Step N" giữ làm văn bản thân.
  Kiểm: chạy lại và xác nhận cụm này xuất hiện trong chunk của 6AH, 6AVE.

### I-60: chunk hình gộp nhiều trang; nhãn tiếng Việt
- 10iV `B0022` gộp 9 trang (tr.25–33) gồm nhiều sơ đồ servo vào mục "2.3.4 6-WIRE-PNP TYPE"; nhãn trong hình `ết ối với biế tầ chạy x g`
  (đúng: "Kết nối với biến tần chạy trục X"). F10T (tiếng Việt) rớt chữ có dấu phức (`kt ni`, `bt buc`) do OCR tiếng Anh (I-29).
- **Đề xuất:** CQ: chunk hình không quá 2 trang và một chú thích hình; tách theo hình. OCR theo ngôn ngữ của manifest.

### I-54: V-01 báo động giả và bỏ sót lỗi thật
- 17 trang trượt; 15 chỉ trượt vì lặp > 10% (độ phủ ≥ 91,6%). Các token thiếu thuộc: nhãn hình, dòng chấm dẫn mục lục, chỉ số trên (`1 st` so
  với `1st`), ký tự hỏng U+FFFE. 10iV tr.26–31 số đo y hệt vì cùng mẫu sơ đồ servo mỗi trục. Chưa trang nào cho thấy mất chữ văn xuôi, nhưng chưa
  xem ảnh của cả 17 trang.
- Ngược lại V-01 **không bắt** các lỗi thật: hàng ANT mất, tiêu đề trong ảnh (I-58), text layer hỏng (I-55).
- **Đề xuất:** chuẩn hoá token (bỏ U+FFFE, gộp chỉ số trên, bỏ dòng chấm), loại chữ nhãn hình và trang mục lục khỏi mẫu số, tách ngưỡng lặp thành cảnh
  báo không chặn chunk. Đo lại bằng `quality-report` (trước/sau).

## OCR của 6 bản Operation: kết quả mẫu (24 chunk)

Đúng 6 (25%), lỗi nhẹ 5 (21%), lỗi nặng 11 (46%), không dùng được 2 (8%). Phần lớn lỗi nặng là lỗi chunker (I-58, I-59) chứ không phải OCR đọc
sai chữ rõ. Bảng văn bản thuần đúng gần tuyệt đối. Lỗi OCR thật còn lại: chữ đậm sát lề (6AH `B0113`: mất `#14010`, `#14011`, `M1o0`, `#14o08`),
tiếng Việt rớt dấu (F10T), nhãn phím nhiễu. Nhãn hình không có trong `content` nhưng **được giữ** trong `metadata.figure_labels` (khoảng 300–600
nhãn mỗi tài liệu) theo thiết kế. Xin PDF có text layer sẽ **không** sửa I-58, I-59; chỉ có lợi cho 10iV (I-55) và có thể F10T.

## Quyết định cần Toma

1. **Cơ chế gỡ mã chặn (I-53):** hiện chunk OCR không thể `approved`. Đề xuất: xác nhận theo trang trong manifest (người, ngày, mẫu đã kiểm) chỉ cho
   `ocr_required`, không cho mã lỗi cấu trúc.
2. **Nhãn hình vào `content`** cho chunk `wiring` và `pinout` ("Nhãn trong hình: …")? Hiện chỉ là từ khóa; câu hỏi kiểu "chân nào của CN2" khó trả lời.
3. **Thứ tự sửa:** I-55 → I-59 → I-54 → I-57 → I-58 → I-56 → I-60 (dễ và có kiểm chứng trước). Sau mỗi bước chạy lại `quality-report`.
4. **Xuất bản:** Installation sau khi sửa I-56 (6 chunk `can_sua`); không xuất bản bảng ảnh màn hình; 10iV chương 4 chờ I-55.

## 21 chunk `can_sua`

| Tài liệu | Chunk | Nhóm | Lỗi chính |
|---|---|---|---|
| 10iv-operation-en | B0110, B0111, B0112 | I-55 | Mất chữ số và chữ `m` trong mã tham số |
| 10iv-operation-en | B0022 | I-60 | Gộp 9 trang sơ đồ; nhãn Việt mất chữ |
| f54-installation-en | B0004, B0005 | I-56 | `X47`, `Y40`, `CY0` gán sai cổng; hàng tách qua trang |
| 6ave-installation-vi | B0003 | I-56 | Hàng ANT mất; dòng đầu mô tả CN6 ở hàng CN5 |
| 6ave-installation-vi | B0004 | I-56 | CN7+CN8+CN9 gộp một hàng |
| 6ave-installation-vi | B0026 | I-57 | Sơ đồ nguồn thành bảng |
| f10t-installation-vi | B0004, B0008 | I-56 | Câu CN4 cắt; CN2 hỏng cột; `X57` sang CN18 |
| f86-installation-en | B0007 | I-56 | `X57` sang CN17 |
| f86-operation-en | B0113 | I-58 | Ô khóa `#10000 - #10049` tách đôi; thiếu tiêu đề |
| f54-operation-en | B0042, B0085, B0086, B0088, B0091, B0092, B0098, B0107 | I-57 | Ảnh màn hình thành bảng; mất dấu âm; header lẫn đồng hồ |
