# Kết quả duyệt chunk CRM `crm-1.0-a` (2026-11-21)

> **Lưu ý:** số `ok`/`fix`/`pending` chỉ đúng cho run `crm-1.0-a` và verdict ghi lúc 2026-11-21 (người duyệt tự động, chưa người xác nhận). Run đã nạp vào DB và các run sau (`crm-1.7-a`) có số khác; xem mục Tóm tắt của [STATE.md](../flows/doc-ingest/STATE.md). Nguồn `chunk_review.json` nằm trong `data/ingest_runs/` (gitignored) nên có thể bị xoá hoặc ghi đè.

Nguồn: `data/ingest_runs/<tài liệu>/crm-1.0-a/build/chunk_review.json` (10 tài liệu, gitignored; file ghi lúc 13:40–13:45 ngày 2026-11-21). Người duyệt ghi trong file: `Codex PDF comparison` (đối chiếu PDF tự động, **chưa người xác nhận**). Hash nội dung của cả 847 mục khớp `chunks.jsonl`. Nhóm lý do chọn thô theo từ khoá trong ghi chú; ghi chú gốc nằm trong file JSON.

## Tổng hợp

| Tài liệu | Lá ok | Lá fix | Lá pending | Cha ok | Cha fix |
|---|---|---|---|---|---|
| 10iv-operation-en | 47 | 50 | 0 | 11 | 7 |
| 6ah-operation-en | 47 | 54 | 6 | 8 | 10 |
| 6ave-installation-vi | 24 | 6 | 0 | 0 | 0 |
| 6ave-operation-en | 49 | 55 | 4 | 10 | 10 |
| f10t-installation-vi | 17 | 6 | 0 | 0 | 0 |
| f10t-operation-vi | 5 | 100 | 4 | 0 | 19 |
| f54-installation-en | 14 | 3 | 0 | 0 | 0 |
| f54-operation-en | 57 | 65 | 4 | 9 | 9 |
| f86-installation-en | 17 | 3 | 2 | 0 | 0 |
| f86-operation-en | 66 | 30 | 4 | 9 | 6 |
| **Tổng** | **343** | **372** | **24** | **47** | **61** |

## Chunk lá cần sửa (`fix`), theo tài liệu

Cột Trang là trang PDF (`page_start`–`page_end`). Chunk cha `fix` không liệt kê ở đây (61 chunk, xem JSON).

### 10iv-operation-en (50 chunk)

Nhóm: Chữ OCR sai / ký tự lỗi 24; Thiếu / mất nội dung 23; Nhãn rời / thiếu ngữ cảnh 1; Bảng / hàng / cột 1; Khác 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0001 | 1–1 | Thiếu / mất nội dung | Trang PDF 1: chỉ còn dòng “Controller features”, là nhãn rời không có thông tin chức năng/ngữ cảnh để dùng độc lập. |
| B0005 | 10–10 | Chữ OCR sai / ký tự lỗi | Trang PDF 10: chú thích hình OCR model “10l” thay vì “10i”; sai ký tự định danh model. |
| B0007 | 11–14 | Chữ OCR sai / ký tự lỗi | Trang PDF 11–14: OCR bảng sai/mất nhãn phím (ví dụ COORD thành “人 COORD”, PARAM thành “114 PARAM”, Shift/INC JOG và các nút/scale bị dính hoặc đảo)… |
| B0008 | 13–16 | Chữ OCR sai / ký tự lỗi | Trang PDF 13–16: vùng hình phím/knob bị rút thành dãy số; thang spindle OCR sai/đảo thứ tự và mất nội dung nhận diện các nút. |
| B0009 | 16–16 | Chữ OCR sai / ký tự lỗi | Trang PDF 16: các hàng Cycle start, Feed hold, Movement & Selection và USB slot không có nhãn nút OCR tương ứng; mô tả không xác định được đầy đủ n… |
| B0016 | 23–23 | Chữ OCR sai / ký tự lỗi | Trang PDF 23: model trong heading OCR thành “ASTRO 1OI” (chữ O) thay cho mã nguồn “ASTRO 10I”; sai mã model. |
| B0018 | 23–23 | Chữ OCR sai / ký tự lỗi | Trang PDF 23: chỉ OCR được tiêu đề/caption sơ đồ; thiếu ánh xạ dây, màu dây, chân X56 và 24V/0V trong hình. |
| B0019 | 24–24 | Thiếu / mất nội dung | Trang PDF 24: chỉ có tiêu đề/caption; thiếu sơ đồ đấu dây NPN, màu dây và chân X56/X57. |
| B0020 | 24–24 | Thiếu / mất nội dung | Trang PDF 24: chỉ có tiêu đề/caption; thiếu sơ đồ đấu dây PNP, màu dây và chân X56/X57. |
| B0021 | 25–25 | Thiếu / mất nội dung | Trang PDF 25: chỉ có tiêu đề/caption; thiếu ánh xạ dây và chân X56/X57 trong sơ đồ 6-wire NPN. |
| B0022 | 25–33 | Chữ OCR sai / ký tự lỗi | Trang PDF 25–33: sơ đồ nguồn đọc được, nhưng chunk chỉ giữ caption đầu và hai dòng OCR tiếng Việt vỡ (“ết ối với biế tầ…”); mất phần lớn nhãn/chân … |
| B0023 | 34–34 | Thiếu / mất nội dung | Trang PDF 34: chỉ có tiêu đề/caption; thiếu CN16/CN17, chân tín hiệu và các nhãn tín hiệu ground/I_IN của sơ đồ 4–20 mA. |
| B0024 | 35–35 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 35: ba caption khớp nhưng chunk bỏ nội dung sơ đồ dây CN4/CN10–CN11 và nhãn các cổng input/output của I/O link board. |
| B0025 | 36–36 | Chữ OCR sai / ký tự lỗi | Trang PDF 36: chỉ có tiêu đề; OCR bỏ toàn bộ nhãn IN0–IN31, CX.0–CX.3 và phân loại low input trong sơ đồ. |
| B0026 | 37–37 | Chữ OCR sai / ký tự lỗi | Trang PDF 37: chỉ có tiêu đề; OCR bỏ toàn bộ nhãn IN0–IN31, CX.0–CX.3 và phân loại high input trong sơ đồ. |
| B0027 | 38–39 | Thiếu / mất nội dung | Trang PDF 38–39: có tiêu đề/cảnh báo dây chống nhiễu, nhưng thiếu các nhãn OUT0–OUT31 và sơ đồ cổng đầu ra ở trang 38. |
| B0028 | 40–40 | Thiếu / mất nội dung | Trang PDF 40: chỉ có caption; thiếu ánh xạ pin CN2, tín hiệu A/Z/Y/X/X1/X10/X100, EMG, GND và +5V. |
| B0029 | 41–41 | Thiếu / mất nội dung | Trang PDF 41: chỉ có caption; thiếu ánh xạ 6-axis và các tín hiệu/pin CN2. |
| B0030 | 42–42 | Thiếu / mất nội dung | Trang PDF 42: chỉ có caption; thiếu ánh xạ 4-axis NPN và các tín hiệu/pin CN2. |
| B0031 | 43–43 | Thiếu / mất nội dung | Trang PDF 43: chỉ có caption; thiếu ánh xạ 6-axis NPN và các tín hiệu/pin CN2. |
| B0032 | 44–44 | Thiếu / mất nội dung | Trang PDF 44: chỉ có caption; thiếu ánh xạ 4-axis PNP và các tín hiệu/pin CN2. |
| B0033 | 45–45 | Thiếu / mất nội dung | Trang PDF 45: chỉ có caption; thiếu ánh xạ 6-axis PNP và các tín hiệu/pin CN2. |
| B0040 | 50–50 | Chữ OCR sai / ký tự lỗi | Trang PDF 50: dòng Machine coordinate system trong bảng có số thứ tự 9 ở nguồn nhưng OCR thành 6; sai nhãn số. |
| B0043 | 51–51 | Chữ OCR sai / ký tự lỗi | Trang PDF 51: mục Switch screen bị OCR thành chuỗi vô nghĩa “swn S sin s sn :n en”; mất tên và chức năng. |
| B0045 | 52–52 | Thiếu / mất nội dung | Trang PDF 52: chỉ giữ heading Switch Screen; mất Step 1, Step 2 và ghi chú về thứ tự coordinate systems. |
| B0046 | 53–53 | Thiếu / mất nội dung | Trang PDF 53: chỉ giữ heading Half; mất hướng dẫn chọn trục và chia tọa độ cho 2. |
| B0047 | 54–55 | Thiếu / mất nội dung | Trang PDF 54–55: chỉ giữ heading Zero/Zero All; mất các bước đưa trục hoặc toàn bộ trục về 0. |
| B0051 | 57–57 | Thiếu / mất nội dung | Trang PDF 57: chỉ giữ heading Copy data from USB; mất hai bước chọn file và sao chép. |
| B0052 | 58–59 | Thiếu / mất nội dung | Trang PDF 58–59: chỉ giữ heading Execute Program; mất các bước mở file, chọn chương trình, chạy và kiểm tra kết quả. |
| B0055 | 61–61 | Thiếu / mất nội dung | Trang PDF 61: chunk con chỉ còn Step 3–4, thiếu heading/tên thao tác; đứng riêng không đủ ngữ cảnh, đồng thời chunk cha cũng thiếu Step 1. |
| B0057 | 62–64 | Thiếu / mất nội dung | Trang PDF 62–64: chunk con bắt đầu ở Step 3 và thiếu hai bước đầu Search nên không đủ quy trình khi truy xuất riêng. |
| B0059 | 65–66 | Thiếu / mất nội dung | Trang PDF 65–66: chỉ giữ Step 3, mất Step 1–2 về chọn lệnh và xóa command line. |
| B0060 | 67–68 | Thiếu / mất nội dung | Trang PDF 67–68: chỉ giữ heading Copy and Paste; mất các bước Copy From, Copy To và Paste. |
| B0064 | 70–72 | Chữ OCR sai / ký tự lỗi | Trang PDF 70–72: sau heading Manual Data Input, OCR đưa vào “ES S EM” và Step 1 APPLY MACH thuộc phần Assign Machine/Auxiliary; mất các bước nhập d… |
| B0069 | 75–75 | Chữ OCR sai / ký tự lỗi | Trang PDF 75: câu mở đầu về thông tin monitor bị OCR thành chuỗi rời “At ss t sin s i t ine”; mất nội dung chính. |
| B0082 | 84–84 | Chữ OCR sai / ký tự lỗi | Trang PDF 84: Step 2 bị OCR lặp lại hành động Step 1 “Press PART LOG button”; nguồn Step 2 chỉ giải thích các cột lịch sử, tên chương trình và cycl… |
| B0087 | 86–86 | Chữ OCR sai / ký tự lỗi | Trang PDF 86: chunk overview lặp lỗi OCR “diagnostic tale” thay cho “diagnostic table”. |
| B0090 | 87–87 | Chữ OCR sai / ký tự lỗi | Trang PDF 87: đoạn cảnh báo tham số bị OCR thành chuỗi rời; không giữ được nội dung nguồn. |
| B0097 | 93–93 | Chữ OCR sai / ký tự lỗi | Trang PDF 93: câu giải thích định dạng thư mục bị OCR thành chuỗi rời “If th e t e s ed”; thiếu nội dung hướng dẫn. |
| B0098 | 93–95 | Bảng / hàng / cột | Trang PDF 93–95: chunk chỉ chứa hàng PLC đầu tiên; bảng nguồn còn các hàng Macro, Parameter, Offset và PLC cùng định dạng/tên file. |
| B0100 | 95–96 | Thiếu / mất nội dung | Trang PDF 95–96: chỉ còn Step 5–6 của quy trình import PLC, thiếu tiêu đề và Step 1–4; chunk còn cắt qua trang bắt đầu mục System Setting. |
| B0103 | 98–100 | Khác | Trang PDF 98–100: chunk bắt đầu ở Step 2, bỏ Step 1 đăng nhập/chọn FIRMWARE; các tên file/version cuối trang khớp. |
| B0104 | 101–102 | Thiếu / mất nội dung | Trang PDF 101–102: chỉ giữ Step 3; mất Step 1 chọn SYS.INIT và Step 2 chọn TIME/DATE. |
| B0105 | 103–105 | Chữ OCR sai / ký tự lỗi | Trang PDF 103–105: mã lệnh M100 bị OCR thành M1o0; Stage 4–5 thành chuỗi vô nghĩa; mất nội dung thao tác/parameter. |
| B0109 | 106–107 | Chữ OCR sai / ký tự lỗi | Trang PDF 106–107: bảng nguồn đọc được nhưng OCR làm hỏng hầu hết mã tham số (#0000–#0007 thành “# - # 7”), tên AX.ENA/AX.DIR/AX.HDRF và các đơn vị… |
| B0110 | 108–108 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF trang 108: OCR làm hỏng mã tham số (ví dụ #8150/#8152/#8154, #8170/#8172/#8174), ký tự và đơn vị; bảng nguồn đọc được. Cần OCR/đối so… |
| B0111 | 109–109 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF trang 109: mã tham số và giá trị ở bảng spindle bị OCR sai/mất ký tự; đối chiếu từng mã với tiêu đề bảng nguồn. |
| B0112 | 109–110 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF trang 109–110: bảng spindle/general bị OCR làm méo mã và ký hiệu; chunk nối qua trang, cần sửa và xác nhận ranh bảng. |
| B0113 | 110–110 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF trang 110: các dải mã thanh ghi user-defined bị tách sai cột/ký tự; cần phục hồi chính xác mã #2000–#2079, #10000–#10049, #14000–#140… |
| B0114 | 110–110 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF trang 110: mã T.Macro/Macro.M98 và các dải M/G Macro ID bị OCR méo/mất ký tự; cần đối chiếu lại từng mã và điều kiện. |

### 6ah-operation-en (54 chunk)

Nhóm: Thiếu / mất nội dung 32; Chữ OCR sai / ký tự lỗi 16; Hình / ảnh / sơ đồ 5; Bảng / hàng / cột 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0005 | 11–15 | Chữ OCR sai / ký tự lỗi | Trang PDF 11–15: nhiều nhãn phím OCR sai/mất/gộp, gồm COORD thành “人 COORD”, PARAM thành “$9$ PARAM”, hàng MONTR/JOG/MDI thiếu nhãn và Page Up/Down… |
| B0006 | 11–14 | Chữ OCR sai / ký tự lỗi | Trang PDF 11–14: nhãn phím COORD/PARAM bị OCR sai; các mức override 0/25/50/100 và hệ số x1/x10/x100/x1000 bị rút khỏi ngữ cảnh hàng. |
| B0007 | 17–17 | Hình / ảnh / sơ đồ | Trang PDF 17: chunk chỉ giữ caption/lưu ý; bỏ mapping nguồn AC-220V, FG, 0V và 24V trong sơ đồ cấp nguồn. |
| B0008 | 18–18 | Chữ OCR sai / ký tự lỗi | Trang PDF 18: câu mô tả sensor sau heading bị OCR thành chuỗi rời “hh e (ud…”, không đọc được phần giới thiệu. |
| B0009 | 18–18 | Hình / ảnh / sơ đồ | Trang PDF 18: caption/high-input đúng nhưng chunk bỏ mapping tín hiệu CX/X và 24V của CN16–CN18 trong sơ đồ. |
| B0010 | 19–19 | Thiếu / mất nội dung | Trang PDF 19: caption và lưu ý đúng nhưng thiếu mapping chân/đường tín hiệu của sơ đồ low-input CN16–CN18. |
| B0013 | 20–20 | Thiếu / mất nội dung | Trang PDF 20: chỉ có caption 3-wire; mất màu dây, X56 (probe signal), 24V và 0V của sơ đồ. |
| B0014 | 21–21 | Thiếu / mất nội dung | Trang PDF 21: chỉ có caption 4-wire NPN; mất dây/màu và mapping X56/X57. |
| B0015 | 21–21 | Chữ OCR sai / ký tự lỗi | Trang PDF 21: caption PNP bị OCR vỡ thành “Fign- g np)”; mất nội dung sơ đồ. |
| B0016 | 22–22 | Thiếu / mất nội dung | Trang PDF 22: chỉ có caption 6-wire NPN; mất mapping dây và X56/X57. |
| B0017 | 22–22 | Thiếu / mất nội dung | Trang PDF 22: chỉ có caption 6-wire PNP; mất màu dây và mapping X56/X57. |
| B0018 | 23–23 | Thiếu / mất nội dung | Trang PDF 23: chỉ có caption X/Y pulse-direction; mất CN11/CN12, PUL/DIR/Z-phase và mapping sang driver. |
| B0021 | 24–24 | Chữ OCR sai / ký tự lỗi | Trang PDF 24: caption Z/A đúng nhưng OCR bỏ mapping CN12/CN13, PUL/DIR, Z phase và driver. |
| B0022 | 25–25 | Thiếu / mất nội dung | Trang PDF 25: heading B/C wiring và note còn lại; thiếu mapping CN14/CN15, PUL/DIR/Z-phase trong sơ đồ. |
| B0024 | 25–25 | Hình / ảnh / sơ đồ | Trang PDF 25: note cáp chống nhiễu và caption ảnh đúng nhưng phần mapping CN14/CN15 và driver B/C bị bỏ. |
| B0025 | 26–26 | Thiếu / mất nội dung | Trang PDF 26: chỉ giữ caption inverter; thiếu mapping CN4, Z/B/A phase và các chân GND/DA.V/V_IN. |
| B0027 | 27–27 | Hình / ảnh / sơ đồ | Trang PDF 27: caption ba hình khớp nhưng bỏ mapping CN3↔CN10/CN11 và các port input/output trên board. |
| B0028 | 28–28 | Thiếu / mất nội dung | Trang PDF 28: chỉ giữ heading Low Input; mất mapping IN0–IN31, CX.0–CX.3 và phân loại low input. |
| B0029 | 29–29 | Thiếu / mất nội dung | Trang PDF 29: chỉ giữ heading High Input; mất mapping IN0–IN31, CX.0–CX.3 và phân loại high input. |
| B0030 | 30–31 | Bảng / hàng / cột | Trang PDF 30–31: note shield-wire/caption đúng nhưng bỏ toàn bộ bảng OUT0–OUT31, Y300–Y337 và chân nguồn. |
| B0031 | 32–32 | Thiếu / mất nội dung | Trang PDF 32: chỉ có caption 4-axis differential; thiếu CN2, pin 1–15, A/B/Z/X signals, EMG, GND và +5V. |
| B0032 | 33–33 | Thiếu / mất nội dung | Trang PDF 33: chỉ có caption 6-axis differential; thiếu pinout CN2 và tín hiệu MPG. |
| B0033 | 34–34 | Thiếu / mất nội dung | Trang PDF 34: chỉ có caption 4-axis NPN; thiếu mapping tín hiệu và pin CN2. |
| B0034 | 35–35 | Thiếu / mất nội dung | Trang PDF 35: chỉ có caption 6-axis NPN; thiếu mapping tín hiệu và pin CN2. |
| B0035 | 36–36 | Thiếu / mất nội dung | Trang PDF 36: chỉ có caption 4-axis PNP; thiếu mapping tín hiệu và pin CN2. |
| B0036 | 37–37 | Thiếu / mất nội dung | Trang PDF 37: chỉ có caption 6-axis PNP; thiếu mapping tín hiệu và pin CN2. |
| B0037 | 38–38 | Hình / ảnh / sơ đồ | Trang PDF 38: chỉ còn heading Home Switch; bỏ cấu trúc COM/Normal Closed/Normal Open, sơ đồ PNP/NPN, 24V/0V và X40–X45. |
| B0046 | 43–43 | Chữ OCR sai / ký tự lỗi | Trang PDF 43: câu mô tả coordinate page bị OCR thành chuỗi rời; nội dung chính không đọc được. |
| B0048 | 44–44 | Thiếu / mất nội dung | Trang PDF 44: chỉ giữ heading Switch Screen; mất Step 1/2 và ghi chú thứ tự Machine→Absolute→DIS→Relative. |
| B0049 | 45–45 | Thiếu / mất nội dung | Trang PDF 45: chỉ giữ heading Half; mất hai bước chuyển sang Relative và chia tọa độ trục cho 2. |
| B0050 | 46–47 | Thiếu / mất nội dung | Trang PDF 46–47: chỉ giữ heading Zero/Zero All; mất các bước đặt trục hoặc toàn bộ trục về 0. |
| B0054 | 49–49 | Thiếu / mất nội dung | Trang PDF 49: chỉ giữ heading Copy Data from USB; mất hai bước mở file, chọn chương trình và copy. |
| B0055 | 50–51 | Chữ OCR sai / ký tự lỗi | Trang PDF 50–51: chỉ còn Step 3–4, thiếu Step 1–2; OCR nút “EXCECUTE” sai chính tả so với EXECUTE trong nguồn. |
| B0058 | 53–53 | Thiếu / mất nội dung | Trang PDF 53: chunk con chỉ có Step 3–4 và model, thiếu tên thao tác; chunk cha cũng không có Step 1. |
| B0060 | 54–56 | Thiếu / mất nội dung | Trang PDF 54–56: chunk con bắt đầu ở Step 3 nên thiếu quy trình mở đầu Search/Replace. |
| B0062 | 57–58 | Thiếu / mất nội dung | Trang PDF 57–58: chỉ giữ Step 3 kiểm tra sau xóa; mất bước chọn lệnh và Delete Line. |
| B0063 | 59–60 | Thiếu / mất nội dung | Trang PDF 59–60: chỉ còn heading Copy and Paste; mất các bước copy from/copy to/paste. |
| B0065 | 61–61 | Chữ OCR sai / ký tự lỗi | Trang PDF 61: dòng Apply AUX bị OCR thành chuỗi rời; nguồn nói 6 hệ tọa độ nhưng chỉ liệt kê G54/G55/G57/G58/G59. |
| B0067 | 62–62 | Thiếu / mất nội dung | Trang PDF 62: chỉ còn heading Manual Data Input; mất Step 1 chọn G54 và Step 2 nhập/confirm giá trị. |
| B0076 | 67–68 | Chữ OCR sai / ký tự lỗi | Trang PDF 67–68: OCR kéo cả nội dung màn hình nhỏ vào chunk, làm vỡ tên chương trình, tọa độ và nhiều dòng G-code; dữ liệu số/mã không đáng tin. |
| B0080 | 70–70 | Chữ OCR sai / ký tự lỗi | Trang PDF 70: OCR “control pahel” thay cho “control panel”; lỗi nằm trong hướng dẫn thao tác MDI. |
| B0087 | 74–75 | Thiếu / mất nội dung | Trang PDF 74–75: ghi chú NC CUT enable mất từ “program” sau “secondary”; phần còn lại khớp nguồn. |
| B0088 | 76–76 | Chữ OCR sai / ký tự lỗi | Trang PDF 76: Step 2 bị OCR lặp “Press PART LOG button to open…” từ Step 1; nguồn Step 2 chỉ nêu nội dung bảng history. |
| B0096 | 79–79 | Chữ OCR sai / ký tự lỗi | Trang PDF 79: đoạn cảnh báo về thay đổi parameter bị OCR thành chuỗi rời, không đủ nghĩa. |
| B0099 | 80–82 | Chữ OCR sai / ký tự lỗi | Trang PDF 80–82: nội dung screenshot parameter bị OCR vỡ và password 1415 bị tách; thiếu Step 1–2 của quy trình. |
| B0100 | 82–82 | Thiếu / mất nội dung | Trang PDF 82: chỉ giữ Step 5–6, thiếu tiêu đề/ngữ cảnh và các bước parameter 1–4. |
| B0103 | 83–84 | Chữ OCR sai / ký tự lỗi | Trang PDF 83–84: chunk hình chứa các địa chỉ PLC OCR sai (“月1933”, “x47”, “-A1205]”); caption không đủ để tin phần dữ liệu màn hình. |
| B0108 | 88–89 | Thiếu / mất nội dung | Trang PDF 88–89: chỉ có Step 5–6 của import PLC, thiếu tiêu đề và bốn bước đầu; đây là continuation. |
| B0111 | 91–93 | Thiếu / mất nội dung | Trang PDF 91–93: chunk bắt đầu ở Step 2, thiếu Step 1 vào System; nội dung update firmware không giữ đủ bước đầu. |
| B0112 | 94–95 | Thiếu / mất nội dung | Trang PDF 94–95: chỉ giữ Step 3 Establish date/time; mất Step 1 chọn SYS.INIT và Step 2 chọn TIME/DATE. |
| B0113 | 96–98 | Chữ OCR sai / ký tự lỗi | Trang PDF 96–98: M100 bị OCR thành M1o0, #14008 thành #14o08 và nội dung Stage 6–8 bị vỡ; sai mã và mất bước. |
| B0115 | 98–98 | Chữ OCR sai / ký tự lỗi | Trang PDF 98: bản overview lặp lỗi #1401o và chuỗi OCR vỡ ở phần cuối. |
| B0117 | 99–100 | Thiếu / mất nội dung | Trang PDF 99–100: nhiều hàng đầu khớp, nhưng bảng bị cắt sau #4010–#4017 và giá trị “0: DOG on” gộp vào hàng Axis zero digit visible; mất các hàng … |
| B0118 | 100–100 | Thiếu / mất nội dung | PDF trang 100: phần PARAMETER INSTRUCTIONS bị mất/đảo cột. Các lựa chọn Axis type và Axis encoder port bị trộn vào nhau, ví dụ #4140/#4150; nội dun… |

### 6ave-installation-vi (6 chunk)

Nhóm: Bảng / hàng / cột 3; Thiếu / mất nội dung 2; Chữ OCR sai / ký tự lỗi 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0000 | 1–2 | Chữ OCR sai / ký tự lỗi | Trang PDF 1–2: phần mục lục OCR chỉ lấy một mục, còn nhiều mục/trang nguồn bị bỏ; mã model cuối “ASTRO 6AV-HMI-” bị cắt trước hậu tố. |
| B0003 | 6–7 | Bảng / hàng / cột | Đối chiếu PDF trang 7: hàng CN5 là tải Y50–Y57, nhưng chunk ghi “cùng lúc trên 1 cổng CN6”; sai mã cổng. Sửa CN6 thành CN5. |
| B0004 | 7–8 | Bảng / hàng / cột | Đối chiếu PDF trang 7–8: các hàng CN7, CN8, CN9 bị gộp/lệch cột; chân X60–X67 thuộc CN9 nhưng mô tả bị gán X50–X57. Cần dựng lại hàng/cột theo PDF. |
| B0005 | 8–9 | Bảng / hàng / cột | Đối chiếu PDF trang 8–9: hàng CN10 và CN11 bị cắt qua ranh chunk; đoạn P1 tiếp nối lặp lại ở B0006 và mô tả P1+ sai cực tính (“đảo”). Cần gom tiếp … |
| B0006 | 9–10 | Thiếu / mất nội dung | Đối chiếu PDF trang 9–10: chứa hàng tiếp nối không có tên cổng; lặp phần P1 của B0005. Cần gắn đúng CN10/CN11/CN12 và giữ các dòng tiếp nối cùng hàng. |
| B0007 | 10–11 | Thiếu / mất nội dung | Đối chiếu PDF trang 10–11: chứa tiếp nối không có tên cổng và lặp đoạn P3+ từ B0006; cần gắn đúng CN12/CN13/CN14/CN15 theo PDF. |

### 6ave-operation-en (55 chunk)

Nhóm: Nhãn rời / thiếu ngữ cảnh 27; Thiếu / mất nội dung 9; Chữ OCR sai / ký tự lỗi 9; Hình / ảnh / sơ đồ 5; Bảng / hàng / cột 3; Khác 2

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0002 | 1–2 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 1–2: nội dung giới thiệu khớp nguồn nhưng tiêu đề OUR WEBSITE bị dính thành OURWEBSITE. |
| B0004 | 8–9 | Thiếu / mất nội dung | Trang PDF 8–9: chỉ có tiêu đề/chú thích; bỏ sót kích thước 220/280/180 mm và nhiều nhãn cổng trên hình mặt sau. |
| B0005 | 10–10 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 10: chỉ có tiêu đề và chú thích, bỏ toàn bộ nhãn/nội dung của sơ đồ cấu trúc phần mềm. |
| B0007 | 11–13 | Chữ OCR sai / ký tự lỗi | Trang PDF 11–13: OCR sai nhãn PARAM, gộp Page Up/Page Down, làm nhiễu nhãn Jog/Inc Jog và ký hiệu CCW; cần sửa bảng theo từng hàng. |
| B0008 | 12–15 | Thiếu / mất nội dung | Trang PDF 14–15: thiếu trị số trên phím (feed −10/100/+10%, rapid ×1/×10/×100) và thiếu nhãn hướng trục; các nội dung này có trên bảng nguồn. |
| B0010 | 17–17 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 17: phần ghi chú khớp nhưng văn bản chunk bỏ nhãn đấu dây 24V/0V/FG/0VE/24VE, AC-220V và Ground Cooper Bar trong sơ đồ. |
| B0012 | 19–19 | Hình / ảnh / sơ đồ | Trang PDF 19: bỏ dữ liệu chân CX.0–CX.5 và X40–X67 trên sơ đồ. Chú thích nguồn ghi CN16–CN18 trong khi sơ đồ và câu dẫn ghi CN7–CN9; cần giữ ghi ch… |
| B0014 | 20–20 | Thiếu / mất nội dung | Trang PDF 20: figure chunk không có văn bản; sơ đồ high-input chứa ánh xạ CX.0–CX.5, X40–X67 và CN7–CN9 nhưng bị bỏ hoàn toàn. |
| B0017 | 22–22 | Chữ OCR sai / ký tự lỗi | Trang PDF 22: OCR sai “wear” thành “ware” trong “tool wear compensation”; chú thích hình khớp. |
| B0018 | 22–22 | Hình / ảnh / sơ đồ | Trang PDF 22: chỉ có tên sơ đồ; bỏ ánh xạ dây BROWN=24V, BLACK=X56 (Probe signal), GREEN=0V. |
| B0019 | 23–23 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 23: chỉ có tiêu đề/chú thích; bỏ màu dây và ánh xạ X56/X57, 24V/0V của sơ đồ 4-wire NPN. |
| B0020 | 23–23 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 23: chỉ có tiêu đề/chú thích; bỏ màu dây và ánh xạ X56/X57, 24V/0V của sơ đồ 4-wire PNP. |
| B0021 | 24–24 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 24: chỉ có tiêu đề/chú thích; bỏ màu dây và ánh xạ tín hiệu/nguồn của sơ đồ 6-wire NPN. |
| B0022 | 24–24 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 24: chỉ có tiêu đề/chú thích; bỏ màu dây và ánh xạ tín hiệu/nguồn của sơ đồ 6-wire PNP. |
| B0023 | 25–26 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 25–26: chỉ có tiêu đề/chú thích; bỏ các chân CN11/CN12, số chân và tín hiệu PULSE/DIR/encoder/alarm của sơ đồ X/Y. |
| B0024 | 27–28 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 27–28: chỉ có tiêu đề/chú thích; bỏ các chân CN13/CN14, số chân và tín hiệu PULSE/DIR/encoder/alarm của sơ đồ Z/A. |
| B0026 | 29–29 | Hình / ảnh / sơ đồ | Trang PDF 29: chỉ có tên sơ đồ B-axis; bỏ số chân và ánh xạ tín hiệu từ CN15 sang Driver B. |
| B0027 | 30–30 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 30: nội dung chỉ còn “Note:” trong khi trang có sơ đồ C-axis và bảng encoder feedback; ngữ cảnh bị tách khỏi dữ liệu. |
| B0028 | 30–30 | Bảng / hàng / cột | Trang PDF 30: hàng PBO/PBO bị gộp với ghi chú “Encoder feedback signal wiring (A,B,Z)”; cần tách ghi chú khỏi hàng dữ liệu. |
| B0029 | 30–31 | Hình / ảnh / sơ đồ | Trang PDF 30–31: câu hướng dẫn shield được chép đúng, nhưng chunk bỏ toàn bộ sơ đồ đấu dây C-axis ở trang 30. |
| B0030 | 31–31 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 31: chỉ có tiêu đề/chú thích; bỏ các chân CN17 và ánh xạ tín hiệu điều khiển inverter analog. |
| B0031 | 32–32 | Chữ OCR sai / ký tự lỗi | Trang PDF 32: tiêu đề OCR “±1OV” dùng chữ O thay số 0; chỉ có chú thích, bỏ sơ đồ với các chân và tín hiệu. |
| B0032 | 33–33 | Khác | Trang PDF 33: chú thích đúng nhưng bỏ toàn bộ chân CN17, tín hiệu PAO/PBO/PCO, S.GND, DAC và I_IN. |
| B0033 | 34–34 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 34: chỉ có chú thích hình; bỏ các nhãn CN3/CN10/CN11 và phân bố input/output port 0–3 trên board I/O Link. |
| B0034 | 35–35 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 35: chỉ có tiêu đề; bỏ toàn bộ sơ đồ low-input gồm các cổng IN0–IN31, X300–X327 và CX.0–CX.3. |
| B0035 | 36–36 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 36: chỉ có tiêu đề; bỏ toàn bộ sơ đồ high-input gồm các cổng IN0–IN31, X300–X327 và CX.0–CX.3. |
| B0036 | 37–38 | Hình / ảnh / sơ đồ | Trang PDF 37–38: ghi chú shield được chép đúng nhưng chunk bỏ các sơ đồ output port 0–3 và mapping Y300–Y337. |
| B0037 | 39–39 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 39: chỉ có tiêu đề/chú thích; bỏ mapping chân CN2 và các tín hiệu A/Z/Y/X, EMG, X1/X10/X100 của MPG 4-axis. |
| B0038 | 40–40 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 40: chỉ có tiêu đề/chú thích; bỏ mapping chân CN2 và các tín hiệu C/B/A/Z/Y/X, EMG, X1/X10/X100 của MPG 6-axis. |
| B0039 | 41–41 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 41: chỉ có tiêu đề/chú thích; bỏ mapping chân và các tín hiệu OUT A/OUT B, EMG, trục và bước MPG 4-axis NPN. |
| B0040 | 42–42 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 42: chỉ có tiêu đề/chú thích; bỏ mapping chân và các tín hiệu OUT A/OUT B, trục và bước MPG 6-axis NPN. |
| B0041 | 43–43 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 43: chỉ có tiêu đề/chú thích; bỏ mapping chân và các tín hiệu OUT A/OUT B, EMG, trục và bước MPG 4-axis PNP. |
| B0042 | 44–44 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 44: chỉ có tiêu đề/chú thích; bỏ mapping chân và các tín hiệu OUT A/OUT B, trục và bước MPG 6-axis PNP. |
| B0049 | 49–49 | Chữ OCR sai / ký tự lỗi | Trang PDF 49: hàng 5 bị OCR hỏng thành “C'o o d d ss nal…” thay cho Coordinate systems/Feedrate/Spindle speed/current tool; hàng cuối số 9 bị đọc t… |
| B0052 | 50–50 | Chữ OCR sai / ký tự lỗi | Trang PDF 50: cùng lỗi OCR ở gạch đầu dòng “Switch screen”; các mô tả Half/Zero/Zero all còn lại đúng. |
| B0054 | 51–51 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 51: chỉ còn tiêu đề; bỏ Step 1–2, chỉ dẫn chọn COORD/FULL SCREEN và ghi chú thứ tự hiển thị tọa độ. |
| B0055 | 52–52 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 52: chỉ còn tiêu đề HALF; bỏ Step 1–2 về chuyển sang RELATIVE và chia tọa độ trục cho 2. |
| B0056 | 53–54 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 53–54: chỉ còn tiêu đề ZERO-ZERO ALL; bỏ các bước ZERO/ZERO ALL và kết quả đưa tọa độ về 0. |
| B0060 | 56–56 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 56: chỉ có tiêu đề; bỏ Step 1–2 về mở file và copy chương trình từ USB vào controller. |
| B0061 | 57–58 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 57–58: chỉ có tiêu đề; bỏ Step 1–4 về mở, chọn, execute chương trình và kiểm tra sau khi chạy. |
| B0066 | 61–63 | Thiếu / mất nội dung | Trang PDF 61–63: child chunk lặp nội dung từ Step 3, thiếu Step 1–2 của quy trình tìm/thay; ghi chú “REALCE ALL” là lỗi có sẵn trong PDF. |
| B0068 | 64–65 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 64–65: chunk chỉ giữ tiêu đề và Step 3; bỏ Step 1–2 về chọn DELETE LINE và chọn dòng cần xóa. |
| B0069 | 66–67 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 66–67: chỉ có tiêu đề COPY AND PASTE; bỏ các bước chuyển trang, chọn dòng, COPY FROM/COPY TO và PASTE. |
| B0074 | 69–71 | Thiếu / mất nội dung | Trang PDF 69–71: child lặp nội dung APPLY MACH của mục 3.4.2 nhưng gắn nhãn 3.4.1; thiếu hai bước Manual Data Input trên PDF p69. |
| B0080 | 74–74 | Chữ OCR sai / ký tự lỗi | Trang PDF 74: child chứa cùng câu mở đầu Monitor bị OCR hỏng thành “At ss t sin s i t ine…”. |
| B0101 | 86–86 | Chữ OCR sai / ký tự lỗi | Trang PDF 86: bản child lặp cảnh báo Parameter page với nhiều từ bị OCR hỏng/mất. |
| B0103 | 87–89 | Thiếu / mất nội dung | Trang PDF 87–89: thiếu Step 1–2 (chọn loại parameter, cuộn tìm parameter); giữ được Step 3–6. Chuỗi mật khẩu “1 415” khớp cách in trong PDF. |
| B0108 | 92–92 | Chữ OCR sai / ký tự lỗi | Trang PDF 92: câu điều kiện bị OCR rơi gần hết thành “If th e t e s s ed”; nguồn nói sai directory name/format thì data không được nạp. |
| B0111 | 95–96 | Thiếu / mất nội dung | Trang PDF 94–95: chunk chỉ giữ Step 5–6 nhưng bỏ Step 3–4 xuất hiện trong nguồn; quy trình PLC import bị thiếu bước trước. |
| B0114 | 98–100 | Thiếu / mất nội dung | Trang PDF 98–100: thiếu Step 1–2 (vào System, chọn Firmware, nhấn Update); Step 3 và tên firmware khớp nguồn. |
| B0115 | 101–102 | Khác | Trang PDF 101–102: chỉ giữ Step 3; bỏ Step 1–2 để vào SYS.INT/TIME-DATE. |
| B0116 | 103–105 | Chữ OCR sai / ký tự lỗi | Trang PDF 103–105: OCR M100 thành M1o0; Stage 4–5 bị hỏng thành “Zx e d…” và bỏ chỉ dẫn touch lần đầu bằng #14007. |
| B0120 | 106–107 | Thiếu / mất nội dung | Trang PDF 107: các hàng parameter được chép đúng đến #4010 nhưng chunk thiếu tiêu đề 4.1 Axis Parameter và tiêu đề cột Parameter/Description/Work r… |
| B0121 | 107–107 | Bảng / hàng / cột | PDF trang 107: hàng #4150/#4160 bị lệch cột; lựa chọn port 6 bị chuyển sang Axis encoder multiply, trộn với X1/X2/X4. |
| B0126 | 110–110 | Bảng / hàng / cột | PDF trang 110: dải mã user-defined bị tách qua hai cột (#2000- và #2079; tương tự #10000/#10049, #14000/#14049); cần nối lại chính xác. |

### f10t-installation-vi (6 chunk)

Nhóm: Bảng / hàng / cột 3; Thiếu / mất nội dung 2; Chữ OCR sai / ký tự lỗi 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0000 | 1–2 | Chữ OCR sai / ký tự lỗi | Trang PDF 1–2: model “F10T” bị OCR thành “F1OT” (số 0 thành chữ O); mục lục chỉ nhận được một phần. |
| B0004 | 7–8 | Bảng / hàng / cột | Đối chiếu PDF trang 7-8: cấu trúc cột bảng CN1-CN7 bị vỡ, một phần mô tả chuyển cột; cần dựng lại theo hàng/cột nguồn. |
| B0005 | 8–9 | Thiếu / mất nội dung | Đối chiếu PDF trang 8-9: bảng tiếp nối bị chia ở ranh trang/chunk, làm mất/lẫn ngữ cảnh cổng; nối lại từng hàng. |
| B0006 | 9–10 | Bảng / hàng / cột | Đối chiếu PDF trang 9-10: bảng servo có dòng tiếp nối không mang tên cổng; gắn lại CN11/CN12 theo nguồn. |
| B0007 | 10–11 | Bảng / hàng / cột | Đối chiếu PDF trang 10-11: phần tiếp nối P2+ và các dòng servo bị tách khỏi hàng/cổng; ghép theo PDF. |
| B0008 | 11–12 | Thiếu / mất nội dung | Đối chiếu PDF trang 11-12: phần tiếp nối bảng thiếu tên cổng; cần giữ quan hệ từng hàng. PDF nguồn ghi X40-X47 dưới CN18 dù chân liệt kê X60-X67; c… |

### f10t-operation-vi (100 chunk)

Nhóm: Chữ OCR sai / ký tự lỗi 27; Thiếu / mất nội dung 25; Nhãn rời / thiếu ngữ cảnh 24; Khác 17; Bảng / hàng / cột 5; Hình / ảnh / sơ đồ 2

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0001 | 1–2 | Chữ OCR sai / ký tự lỗi | Trang PDF 1–2: child lặp phần mở đầu với nhiều từ/dấu tiếng Việt bị mất; OCR FIOT cũng sai model F10T. |
| B0002 | 2–4 | Thiếu / mất nội dung | Trang PDF 2–4: ghép OUR WEBSITE với một dòng mục lục 2.8; dòng mục lục mất dấu và rơi chữ “đấu nối công tắc”, khiến ngữ cảnh lẫn. |
| B0003 | 7–7 | Thiếu / mất nội dung | Trang PDF 7: tên mục TỔNG QUAN và nhiều từ trong chú thích hình bị mất dấu tiếng Việt. |
| B0004 | 8–9 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 8–9: chỉ có tiêu đề/chú thích; bỏ số đo 255/235/195/150/50 mm và các nhãn cổng trên bản vẽ mặt sau. |
| B0005 | 10–10 | Thiếu / mất nội dung | Trang PDF 10: chỉ có tiêu đề/chú thích; bỏ toàn bộ nhãn của sơ đồ cấu trúc phần mềm; tiêu đề/chú thích cũng mất nhiều dấu. |
| B0007 | 12–12 | Thiếu / mất nội dung | Trang PDF 12: chú thích ảnh nguồn bị mất nhiều dấu; chunk không có phần chữ thay thế cho thông tin đấu nguồn. |
| B0008 | 12–12 | Thiếu / mất nội dung | Trang PDF 12: ghi chú mất nhiều dấu và chunk bỏ nhãn đấu dây CN1, AC-220V, FG/0V/24V cùng thanh tiếp địa. |
| B0009 | 13–13 | Chữ OCR sai / ký tự lỗi | Trang PDF 13: dòng Low input (NPN) OCR gần như hỏng hoàn toàn; PNP đọc được. Thiếu cách đấu PNP/NPN theo CX/0V/24V trong sơ đồ. |
| B0010 | 13–13 | Thiếu / mất nội dung | Trang PDF 13: chỉ còn câu dẫn/chú thích; bỏ ánh xạ CX.0–CX.5, X40–X67 của sơ đồ PNP; văn bản tiếng Việt mất dấu. |
| B0012 | 14–14 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 14: child cũng bỏ mapping CX/X40–X67; câu “đầu ra” khớp lỗi có sẵn trong PDF dù tiêu đề ghi đầu vào. |
| B0013 | 14–14 | Thiếu / mất nội dung | Trang PDF 14: nội dung ghi chú mất dấu ở nhiều từ; các ghi chú về CX0–CX5 và không trộn hai loại áp còn đọc được. |
| B0014 | 15–15 | Chữ OCR sai / ký tự lỗi | Trang PDF 15: tiêu đề/giới thiệu 2.2.3 mất dấu nhiều và OCR F10T thành FIOT; chunk chỉ giữ câu dẫn, chưa có bảng mapping ở mục tham chiếu. |
| B0015 | 15–15 | Chữ OCR sai / ký tự lỗi | Trang PDF 15: mô tả tool length sensor mất nhiều dấu; thông tin về chiều dài/độ mòn và bù dao cần OCR lại để giữ tiếng Việt chính xác. |
| B0016 | 15–15 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 15: chỉ có tiêu đề/chú thích; bỏ mapping dây BROWN=24V, BLACK=X56 (tín hiệu probe), GREEN=0V. |
| B0017 | 15–15 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 15: chỉ có tiêu đề/chú thích; bỏ màu dây, X56/X57 và các đầu 24V/0V của sơ đồ 4-wire NPN. |
| B0018 | 16–16 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 16: chỉ có tiêu đề/chú thích; bỏ màu dây và ánh xạ X56/X57, 24V/0V của sơ đồ 4-wire PNP. |
| B0019 | 16–16 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 16: chỉ có tiêu đề/chú thích; bỏ các nhãn màu/đầu dây và tín hiệu X56/X57, 24V/0V của sơ đồ 6-wire NPN. |
| B0020 | 16–16 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 16: chỉ có tiêu đề/chú thích; bỏ các nhãn màu/đầu dây và tín hiệu X56/X57, 24V/0V của sơ đồ 6-wire PNP. |
| B0021 | 18–18 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 18: chỉ có tiêu đề/chú thích; bỏ mapping CN10/CN11, Z±/DIR/PUL, encoder phase, driver X/Y. |
| B0022 | 18–19 | Hình / ảnh / sơ đồ | Trang PDF 18–19: chunk bỏ Figure 2-13/B-axis caption và toàn bộ mapping CN14/CN15; sơ đồ B/C chỉ còn chú thích C-axis. |
| B0023 | 19–19 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 19: chỉ có tiêu đề/chú thích; bỏ chân CN4 và các tín hiệu Z/B/A, PUL/DIR, GND, DA.V, V_IN của sơ đồ biến tần. |
| B0024 | 19–19 | Thiếu / mất nội dung | Trang PDF 19: hàng table gộp nhãn GND/GND và DAC/DA.V/V_IN vào cùng một ô thay vì giữ cặp đấu nối; mất dấu trong mô tả. |
| B0025 | 20–20 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 20: ba chú thích board I/O Link không chứa nhãn CN4/CN10/CN11, port 0–3 và chức năng input/output thể hiện trong hình. |
| B0026 | 21–21 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 21: chỉ có tiêu đề; bỏ mapping các chân IN0–IN31/X300–X327 và CX.0–CX.3 của low-input board. |
| B0027 | 22–22 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 22: chỉ có tiêu đề; bỏ mapping các chân IN0–IN31/X300–X327 và CX.0–CX.3 của high-input board. |
| B0028 | 23–24 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 23–24: ghi chú/caption được giữ nhưng bỏ sơ đồ output port 0–3, các Y300–Y337 và nhãn dây shield. |
| B0029 | 25–25 | Chữ OCR sai / ký tự lỗi | Trang PDF 25: mô tả mục MPG và nhãn trên sơ đồ bị OCR hỏng (còn “y s ai”); hình có mapping CN5/EMG/trục nhưng không được chép. |
| B0030 | 26–26 | Thiếu / mất nội dung | Trang PDF 26: caption 6-wire MPG mất dấu và chunk bỏ mapping CN5, A/B/C/X/Y/Z, EMG, X1/X10/X100. |
| B0031 | 27–27 | Thiếu / mất nội dung | Trang PDF 27: caption 4-wire NPN mất dấu; chunk bỏ CN5, OUT A/B, EMG, trục và bước MPG. |
| B0032 | 28–28 | Thiếu / mất nội dung | Trang PDF 28: caption 6-wire NPN mất dấu; chunk bỏ mapping các chân CN5, OUT A/B, trục và bước MPG. |
| B0033 | 29–29 | Thiếu / mất nội dung | Trang PDF 29: caption 4-wire PNP mất dấu; chunk bỏ mapping CN5, OUT A/B, EMG, trục và bước MPG. |
| B0034 | 30–30 | Thiếu / mất nội dung | Trang PDF 30: caption 6-wire PNP mất dấu; chunk bỏ mapping CN5, OUT A/B, trục và bước MPG. |
| B0035 | 31–31 | Chữ OCR sai / ký tự lỗi | Trang PDF 31: dữ liệu COM/HOME SIGNAL, 24V/0V và X40–X45 còn đủ; nhưng tên mục/chú thích mất dấu tiếng Việt, ký tự O là tiếp điểm trong sơ đồ. |
| B0036 | 32–32 | Chữ OCR sai / ký tự lỗi | Trang PDF 32: bảng trục giữ đủ X–C và cặp PUL/DIR ± cho kênh 1–6; tiêu đề OCR mất dấu thành “DIÊU KHIN TRC”. |
| B0038 | 33–33 | Thiếu / mất nội dung | Trang PDF 33: chỉ còn hai tiêu đề “Tín hiệu đầu ra/Kết nối khác”, mất dấu và không có nội dung bảng trong cùng chunk. |
| B0041 | 35–35 | Thiếu / mất nội dung | Trang PDF 35: chú thích giao diện main screen mất dấu nhiều từ; bảng nhãn màn hình được tách sang chunk kế tiếp. |
| B0042 | 35–35 | Thiếu / mất nội dung | Trang PDF 35: bảng 1–11 giữ các số hàng, nhưng nhiều mô tả tiếng Việt bị mất dấu và row 8 bị dồn thành đoạn khó đọc. |
| B0043 | 35–35 | Chữ OCR sai / ký tự lỗi | Trang PDF 35: định nghĩa Distance to go bị OCR hỏng (“Di… c…”) và mất nhiều từ; định nghĩa Absolute cũng mất dấu. |
| B0045 | 36–36 | Thiếu / mất nội dung | Trang PDF 36: bản child lặp mô tả coordinate page với nhiều dấu/từ bị mất. |
| B0046 | 36–37 | Chữ OCR sai / ký tự lỗi | Trang PDF 36–37: model bị OCR F1oT thay F10T; các bước hướng dẫn tiếng Việt bị mất dấu và rơi ký tự. |
| B0047 | 37–37 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 37: chỉ có tiêu đề Switch Screen; bỏ Step 1–2 và ghi chú thứ tự hiển thị màn hình tọa độ. |
| B0048 | 38–38 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 38: chỉ có tiêu đề Half; bỏ Step 1–2 về chọn HALF và chia tọa độ trục cho 2. |
| B0049 | 39–40 | Chữ OCR sai / ký tự lỗi | Trang PDF 39–40: nội dung OCR chỉ còn chuỗi “3 TI) G G H G G G RO”; mất toàn bộ bước ZERO/ZERO ALL và điều kiện/giá trị tọa độ. |
| B0051 | 41–41 | Thiếu / mất nội dung | Trang PDF 41: child lặp danh sách Program features nhưng làm hỏng mục Replace và mất dấu tiếng Việt; model cũng cần chuẩn hóa F10T. |
| B0052 | 41–42 | Chữ OCR sai / ký tự lỗi | Trang PDF 41–42: model OCR F1OT thay F10T và phần heading/link tiếng Việt mất nhiều dấu. |
| B0053 | 42–42 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 42: chỉ còn tiêu đề COPY dữ liệu từ USB; bỏ Step 1–2 về mở file và copy chương trình từ USB. |
| B0054 | 43–44 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 43–44: chỉ còn tiêu đề Execute Program; bỏ Step 1–4 về mở, chọn, chạy chương trình và kiểm tra sau chạy. |
| B0055 | 45–46 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 45–46: chỉ còn tiêu đề Go to command line; bỏ Step 1–4 và thao tác nhập số dòng/GO TO. |
| B0056 | 47–50 | Khác | Trang PDF 47–50: chỉ giữ Step 5 và ghi chú; bỏ Step 1–4 của Search/Replace. “REALCE ALL” là lỗi đánh máy có sẵn trong PDF. |
| B0057 | 51–51 | Nhãn rời / thiếu ngữ cảnh | Trang PDF 51: chỉ còn tiêu đề Delete line; bỏ Step 1–2 về chọn dòng và xác nhận xóa. |
| B0058 | 52–52 | Thiếu / mất nội dung | Trang PDF 52: mã G-code trong screenshot đọc được nhưng các dòng bị ghép thành một câu và nối thêm nhãn Go To Line/Search/Replace/Delete Line; mất … |
| B0059 | 53–54 | Nhãn rời / thiếu ngữ cảnh | fix — Đối chiếu PDF tr. 53–54: chunk chỉ giữ tiêu đề 3.3.6, bỏ toàn bộ 4 bước Copy From/Copy To/Paste hiển thị trong trang nguồn. |
| B0061 | 55–55 | Chữ OCR sai / ký tự lỗi | fix — Phần tóm tắt Offset ở PDF tr. 55 bị mất dấu tiếng Việt trên diện rộng và đọc sai “Apply MACH” thành “Apply MAH”; nội dung cần hiệu chỉnh OCR.… |
| B0062 | 55–56 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 55–56 ghi model F10T; chunk đọc thành “F1oT”. OCR cũng làm hỏng dấu tiếng Việt ở các mục hướng dẫn thao tác. |
| B0063 | 56–56 | Thiếu / mất nội dung | fix — PDF tr. 56 có hai bước nhập dữ liệu tọa độ (chọn G54 và nhập giá trị); chunk chỉ còn tiêu đề 3.4.1, mất hướng dẫn. |
| B0064 | 57–58 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 57–58 có Bước 1, 2, 3 và ghi chú gán tọa độ máy/phôi; chunk chỉ giữ Bước 3 và ghi chú, mất hai bước đầu. Nhiều từ còn bị OCR rụng dấu. |
| B0065 | 59–60 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 59–60 gồm hướng dẫn lấy tâm theo 4 điểm và theo 3 điểm; chunk chỉ giữ phần 3 điểm, bỏ quy trình 4 điểm. OCR còn làm hỏng dấu trong nộ… |
| B0067 | 61–61 | Thiếu / mất nội dung | fix — PDF tr. 61 ghi đủ ba mô tả Auto Option; chunk làm hỏng gần như toàn bộ gạch đầu dòng về chạy tiếp sau sự cố/mất điện (“ns d … d s O c, mt đin… |
| B0068 | 61–62 | Khác | fix — PDF tr. 61–62 ghi Model F10T và Figure 3-5; chunk đọc sai model thành “FloT” và làm hỏng các mục hướng dẫn do rụng dấu. |
| B0069 | 62–63 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 62–63 có mô tả Work set, Workpiece information và ba chế độ toolpath; chunk rụng dấu/sai chữ trên diện rộng (“Mô phồng”, “Khc”), làm … |
| B0070 | 64–64 | Thiếu / mất nội dung | fix — PDF tr. 64 có Bước 1 chuyển từ AUTO sang MDI và Bước 2 nhập lệnh, xác nhận OK rồi CLEAR; chunk chỉ còn tiêu đề 3.5.2, mất hướng dẫn. |
| B0071 | 65–65 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 65 có câu giới thiệu tính năng Auto Option đầy đủ; OCR làm rụng dấu nhiều từ (“t đng”, “hõ tr”, “s c”), cần phục hồi văn bản. |
| B0073 | 66–66 | Thiếu / mất nội dung | fix — PDF tr. 66 ghi ví dụ “chương trình câu lệnh thứ 100”; chunk đọc sai/mất chữ ở cụm này (“câu Inh th 100”) và rụng dấu tiếng Việt. |
| B0074 | 66–67 | Khác | fix — PDF tr. 66–67 có thao tác nhập 100, SET NEW LINE, START FROM LINE và kết quả chỉ định vị dòng; chunk giữ các nút/số nhưng làm hỏng nhiều từ v… |
| B0076 | 68–68 | Chữ OCR sai / ký tự lỗi | fix — PDF tr. 68 có đủ Bước 1–2 về LAST LINE, CONTINUE, AUTO và CYCLE START; chunk giữ tên nút nhưng OCR làm hỏng nhiều từ tiếng Việt. |
| B0077 | 68–69 | Khác | fix — PDF tr. 68–69 ghi rõ bật/tắt NC CUT và khác biệt tạo chương trình con; chunk làm sai “chương trình con” thành “chương trình còn”, sai “lệnh” … |
| B0078 | 70–70 | Nhãn rời / thiếu ngữ cảnh | fix — PDF tr. 70 có Bước 1 mở PART LOG và Bước 2 xem lịch sử vận hành/tên chương trình/thời gian chu kỳ; chunk chỉ còn tiêu đề 3.5.4. |
| B0080 | 71–71 | Thiếu / mất nội dung | fix — PDF tr. 71 có mô tả Create NC và các mục Face/Add/Modify/Delete/Tool/Adjust position; chunk mất dấu tiếng Việt trên diện rộng. |
| B0081 | 71–72 | Khác | fix — PDF tr. 71–72 ghi model F10T và Figure 3-6; chunk đọc model thành “F1oT” và rụng dấu ở chú thích/hướng dẫn. |
| B0083 | 72–75 | Hình / ảnh / sơ đồ | fix — PDF tr. 72–75 có các bước 3–7; chunk bỏ bước 5–6 (nhập L1/R1/R2 và cập nhật hình dạng), ngoài ra còn rụng dấu tiếng Việt. |
| B0084 | 75–76 | Khác | fix — PDF tr. 75–76 có bước 8–10 và các trường T/L/D/C, Vertical/Horizontal milling; chunk rụng dấu ở giải thích trường và kiểu phay (“Phay dc”, “N… |
| B0085 | 76–77 | Nhãn rời / thiếu ngữ cảnh | fix — PDF tr. 76–77 ghi nhãn tốc độ trục chính “SPL”, FR, PR; chunk đọc “SPL” thành “sPL” và làm hỏng dấu trong phần giải thích. |
| B0086 | 77–78 | Khác | fix — PDF tr. 77–78 có bước 14–16, Layer 1/2, D1/D2 và nút COMPLIE; chunk giữ cấu trúc nhưng rụng dấu diện rộng trong hướng dẫn. |
| B0088 | 79–79 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 79 có mô tả cách vào màn hình bảo trì và đủ bốn mục Alarm/Warning/Operation/Backup; chunk bị rơi chữ giữa câu hướng dẫn, rụng dấu ở các nhã… |
| B0089 | 79–79 | Khác | PDF tr. 79 ghi Model F10T và Figure 3-6; chunk đọc sai model thành “F1oT”. |
| B0091 | 80–80 | Chữ OCR sai / ký tự lỗi | PDF tr. 80 có ba mục NC bit, NC register và Macro debug; OCR làm mất gần hết nội dung Macro debug và làm sai dấu/chữ các mục còn lại. |
| B0092 | 80–80 | Khác | PDF tr. 80 ghi Model F10T, Figure 3-7; chunk đọc model thành “F1oT”. |
| B0094 | 81–81 | Chữ OCR sai / ký tự lỗi | PDF tr. 81 có cảnh báo không tự ý đổi thông số và đủ bốn nhóm General/Axis/Spindle/Hardware; OCR làm hỏng cụm cảnh báo và rụng dấu trên diện rộng. |
| B0095 | 81–82 | Khác | PDF tr. 81–82 ghi Model F10T, Figure 3-8 và mục hướng dẫn 3.9.1; chunk đọc model thành “F1OT” và rụng dấu ở chú thích. |
| B0097 | 82–82 | Khác | PDF tr. 82 có Bước 1 chọn nhóm thông số và Bước 2 cuộn tìm thông số; chunk giữ ý chính nhưng rụng dấu diện rộng. |
| B0098 | 83–83 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 83 có Bước 3 nhập giá trị 1 và Bước 4 nhập mật khẩu 1415/OK; chunk giữ số và nút nhưng rụng dấu, đồng thời một nhãn model bị đọc thành “F1OT”. |
| B0099 | 84–84 | Khác | PDF tr. 84 có Bước 5 nhập lại giá trị và RESET, Bước 6 khởi động lại bộ điều khiển; chunk giữ trình tự nhưng rụng dấu tiếng Việt trên diện rộng. |
| B0101 | 85–85 | Chữ OCR sai / ký tự lỗi | PDF tr. 85 ghi đủ bốn mục SYS BIT/SYS REG/FIND REV/FIND NEXT; OCR rụng dấu ở các mô tả tiếng Việt và sai chữ hoa/thường trong nhãn SYS REG. |
| B0102 | 85–86 | Khác | PDF tr. 85–86 ghi Model F10T, Figure 3-9; chunk đọc sai model thành “F1oT”. |
| B0103 | 86–86 | Chữ OCR sai / ký tự lỗi | PDF tr. 86 có đủ hai bước tìm đối tượng PLC, dùng SEARCH/ENTER và FIND NEXT/FIND REV; chunk giữ các tên nút nhưng rụng dấu và sai chữ (“Sáu đó”). |
| B0104 | 87–89 | Bảng / hàng / cột | PDF tr. 87–89 có bảng định dạng PLC và các bước 1–6; chunk chỉ giữ Bước 5–6, bỏ bảng tên/đuôi tệp cùng Bước 1–4. Các câu còn lại cũng bị rụng dấu n… |
| B0105 | 90–90 | Bảng / hàng / cột | PDF tr. 90 có mô tả vào trang System để thiết lập thông số và nạp/xuất dữ liệu; chunk rụng dấu nhiều từ trong câu. |
| B0108 | 90–90 | Chữ OCR sai / ký tự lỗi | PDF tr. 90 có đủ ghi chú và ví dụ M0100.txt → M0100; chunk giữ tên tệp nhưng làm hỏng nhiều từ tiếng Việt do OCR rụng dấu. |
| B0109 | 91–91 | Khác | PDF tr. 90–91 ghi Model F10T, Figure 3-10 và hai mục hướng dẫn; chunk đọc model thành “F1oT” và rụng dấu trong mục cập nhật firmware. |
| B0110 | 92–94 | Chữ OCR sai / ký tự lỗi | PDF tr. 92–94 có Bước 1–4 và ghi chú hai tên firmware; chunk chỉ giữ Bước 3 cùng danh sách firmware, bỏ thao tác vào System/mật khẩu/Firmware/Updat… |
| B0111 | 95–96 | Khác | PDF tr. 95–96 có ba bước đặt ngày giờ; chunk chỉ giữ Bước 3 SET TIME, bỏ Bước 1 vào SYS INIT và Bước 2 TIME/DATE. |
| B0113 | 97–97 | Chữ OCR sai / ký tự lỗi | PDF tr. 97 ghi M100, tắt tưới nguội và đưa trục Z về home; chunk giữ ý chính nhưng OCR rụng dấu/sai chữ ở gần như mọi cụm. |
| B0114 | 97–98 | Khác | PDF tr. 97–98 liệt kê đúng các bước 2–7 và tham số #14003/#14004/#14005/#14007/#14008/#14009/#14010; chunk đọc #14010 thành “#1401o” và rụng dấu nh… |
| B0115 | 98–98 | Chữ OCR sai / ký tự lỗi | PDF tr. 98 ghi giai đoạn 8 với tham số #14011; chunk giữ mã nhưng rụng dấu/sai chữ khiến câu hướng dẫn bị hỏng. |
| B0116 | 98–99 | Thiếu / mất nội dung | PDF tr. 98–99 có giai đoạn 9–10, phép so sánh hai lần đo với #14012 và ghi Offset H; chunk làm hỏng đoạn mở đầu giai đoạn 9, rụng dấu nhiều và mất … |
| B0118 | 99–99 | Chữ OCR sai / ký tự lỗi | PDF tr. 99 có các cảnh báo theo giai đoạn 4–7 và nguyên nhân/giá trị cần kiểm tra; OCR làm vỡ phần lớn câu và một số tham số, không đủ tin cậy để t… |
| B0119 | 100–100 | Khác | PDF tr. 100 có hai cách gọi M100 và M100Hxxx, ví dụ T5→Offset H5 và M100H3→Offset H3; chunk giữ mã/lựa chọn nhưng làm hỏng dấu và cấu trúc gạch đầu… |
| B0120 | 101–102 | Bảng / hàng / cột | PDF tr. 101–102 có bảng thông số trục với nhiều hàng từ #4020–#8087 và #8090–#12367; chunk chỉ giữ 14 hàng đầu đến #4010–#4017, bỏ phần lớn bảng ng… |
| B0121 | 102–102 | Bảng / hàng / cột | PDF trang 102: cột tham số bị lệch từ #4160 trở đi; mô tả Axis encoder multiply rỗng, lựa chọn bị đẩy sang #8010 và các hàng #8011/#8013/#8080 bị g… |
| B0126 | 105–105 | Bảng / hàng / cột | PDF trang 105: dải mã user-defined bị tách qua hai cột (#2000- và #2079; tương tự các dải kế tiếp); cần nối mã theo nguồn. |

### f54-installation-en (3 chunk)

Nhóm: Bảng / hàng / cột 2; Chữ OCR sai / ký tự lỗi 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0000 | 1–1 | Chữ OCR sai / ký tự lỗi | Trang PDF 1: tên model F54 trên bìa bị OCR thành “カS-”; mất mã model. |
| B0004 | 7–8 | Bảng / hàng / cột | Đối chiếu PDF trang 7-8: bảng cổng CN10/CN9 bị gộp/lệch cột; chân DIR/PUL và mô tả trục không ghép đúng hàng. |
| B0005 | 9–10 | Bảng / hàng / cột | Đối chiếu PDF trang 9-10: hàng tiếp nối bị tách khỏi tên cổng; X47 thuộc CN6 nhưng chunk gán CN7, đồng thời phần CN8 bị chia qua chunk. |

### f54-operation-en (65 chunk)

Nhóm: Thiếu / mất nội dung 27; Chữ OCR sai / ký tự lỗi 21; Nhãn rời / thiếu ngữ cảnh 10; Bảng / hàng / cột 4; Khác 3

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0002 | 8–9 | Thiếu / mất nội dung | PDF tr. 8–9 có kích thước 212, 220, 140 và 30 mm trên các hình trước/sau/bên; chunk chỉ giữ tiêu đề và chú thích, mất toàn bộ số đo cần tra cứu. |
| B0003 | 10–10 | Thiếu / mất nội dung | PDF tr. 10 có sơ đồ cấu trúc phần mềm với các trang Coordinate, Program, Offset, Monitor, Maintenance, Diagnostic, Parameter, PLC, System và chức n… |
| B0004 | 12–12 | Chữ OCR sai / ký tự lỗi | PDF tr. 12 có sơ đồ CN1 với 24V/0V/FG, AC-220V và nối đất; chunk mất dòng cảnh báo điện áp bị OCR thành chuỗi rời (“Vol s t e…”) và không giữ các n… |
| B0005 | 13–13 | Chữ OCR sai / ký tự lỗi | PDF tr. 13: dòng giới thiệu hai loại cảm biến bị OCR thành chuỗi không đọc được; đồng thời nguồn ghi 0V cho PNP còn chunk ghi “OV” (chữ O thay số 0). |
| B0006 | 13–13 | Thiếu / mất nội dung | PDF tr. 13 sơ đồ high input ghi CN6/CN7, CX.0–CX.3 và chân X40–X47/X50–X57; chunk chỉ có câu khái quát và chú thích hình, thiếu toàn bộ mapping chân. |
| B0007 | 14–14 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 14 sơ đồ low input có mapping CN6/CN7, CX và X40–X57; chunk không giữ mapping. Câu nguồn dưới tiêu đề low input lại ghi “high input voltage… |
| B0008 | 15–15 | Bảng / hàng / cột | PDF tr. 15 ghi cảnh báo phải tham khảo bảng chân kết nối để tránh hỏng thiết bị; chunk làm câu thành chuỗi không đọc được (“Reg o e on signal…”). |
| B0010 | 15–15 | Thiếu / mất nội dung | PDF tr. 15 sơ đồ 3 dây ghi Brown=24V, Black=X44 probe signal, Green=0V; chunk chỉ có chú thích hình, mất mapping màu dây/chân. |
| B0011 | 16–16 | Thiếu / mất nội dung | PDF tr. 16 sơ đồ NPN 4 dây ghi Yellow=X44, Green=0V, Red=X45, Black=0V; chunk chỉ còn tiêu đề/chú thích, mất mapping. |
| B0012 | 16–16 | Thiếu / mất nội dung | PDF tr. 16 sơ đồ PNP 4 dây ghi Yellow/Red=24V, Green=X44, Black=X45; chunk chỉ còn tiêu đề/chú thích, mất mapping. |
| B0013 | 17–17 | Thiếu / mất nội dung | PDF tr. 17 sơ đồ NPN 6 dây có X44/X45, màu dây, 24V và 0V; chunk chỉ còn chú thích hình, mất các kết nối. |
| B0014 | 17–17 | Thiếu / mất nội dung | PDF tr. 17 sơ đồ PNP 6 dây có X44/X45, màu dây, 24V và 0V; chunk chỉ còn chú thích hình, mất các kết nối. |
| B0015 | 18–18 | Thiếu / mất nội dung | PDF tr. 18 sơ đồ X/Y dùng CN9, PUL/DIR 1–2 và các chân driver; chunk chỉ giữ tiêu đề/chú thích, thiếu mapping tín hiệu. |
| B0016 | 18–18 | Thiếu / mất nội dung | PDF tr. 18 sơ đồ Z/A dùng CN10, PUL/DIR 3–4 và các chân driver; chunk chỉ giữ tiêu đề/chú thích, thiếu mapping tín hiệu. |
| B0017 | 19–19 | Thiếu / mất nội dung | PDF tr. 19 sơ đồ CN8 nối phản hồi Z-phase tới driver X/Y/Z/A có các nhãn Z1–Z4/Pco; chunk chỉ giữ tiêu đề và lưu ý chống nhiễu, thiếu mapping dây. |
| B0018 | 20–20 | Thiếu / mất nội dung | PDF tr. 20 sơ đồ analog CN2 có DAV/DAI, GND và V_IN/I_IN; chunk chỉ giữ tiêu đề/chú thích, thiếu chân kết nối. |
| B0019 | 20–20 | Thiếu / mất nội dung | PDF tr. 20 sơ đồ INVT 0–10V cần giữ đúng 0–10V, DAV/AI1/GND; chunk ghi “O-1OV” bằng chữ O và không có mapping chân. |
| B0020 | 20–20 | Thiếu / mất nội dung | PDF tr. 20 sơ đồ INVT 0–20mA cần giữ đúng đơn vị và DAI/AI2/GND; chunk ghi “O-2OmA” bằng chữ O và không có mapping chân. |
| B0021 | 20–21 | Thiếu / mất nội dung | PDF tr. 20–21 có sơ đồ CN4↔CN10/CN11, cổng I/O Link input/output và nguồn; chunk chỉ giữ tên các hình, thiếu mapping cổng/dây. |
| B0022 | 22–22 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 22 sơ đồ 4 cổng input low-level ánh xạ IN0–IN31 sang X300–X327 cùng CX.0–CX.3/24V; chunk chỉ còn tiêu đề. |
| B0023 | 23–23 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 23 sơ đồ 4 cổng input high-level ánh xạ IN0–IN31 sang X300–X327 cùng CX.0–CX.3/24V; chunk chỉ còn tiêu đề. |
| B0024 | 24–25 | Bảng / hàng / cột | PDF tr. 24 có mapping output OUT0–OUT31, Y300–Y337 và các chân tải; chunk chỉ giữ lưu ý shield cable/ảnh cáp, bỏ bảng đấu output. |
| B0025 | 26–26 | Thiếu / mất nội dung | PDF tr. 26 sơ đồ MPG 4 trục differential có CN5, chân 1–15, A/B và EMG; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0026 | 27–27 | Thiếu / mất nội dung | PDF tr. 27 sơ đồ MPG 6 trục differential có CN5 và tín hiệu C/B/A/Z/Y/X; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0027 | 28–28 | Thiếu / mất nội dung | PDF tr. 28 sơ đồ MPG 4 trục NPN có OUT A/B, EMG và các nút trục; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0028 | 29–29 | Thiếu / mất nội dung | PDF tr. 29 sơ đồ MPG 6 trục NPN có OUT A/B, EMG và các nút trục; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0029 | 30–30 | Thiếu / mất nội dung | PDF tr. 30 sơ đồ MPG 4 trục PNP có OUT A/B, EMG và các nút trục; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0030 | 31–31 | Thiếu / mất nội dung | PDF tr. 31 sơ đồ MPG 6 trục PNP có OUT A/B, EMG và các nút trục; chunk chỉ giữ chú thích hình, thiếu mapping. |
| B0031 | 32–32 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 32 có sơ đồ công tắc home PNP/NPN với COM, 24V/0V và mapping X40–X43; chunk chỉ giữ tiêu đề. |
| B0040 | 37–37 | Khác | PDF tr. 37: danh sách coordinate features bị hỏng mục Switch screen (“sw S si s sn : en”), dù các mục Half/Zero/Zero all còn đúng. |
| B0041 | 37–37 | Chữ OCR sai / ký tự lỗi | PDF tr. 37: OCR ảnh màn hình làm sai/rời rạc nhiều nhãn tọa độ và trạng thái, như XYZ/YZA, DIS TO GO, các giá trị trục và CMD T; cần sửa để không g… |
| B0042 | 37–37 | Chữ OCR sai / ký tự lỗi | PDF tr. 37: OCR bảng từ ảnh màn hình gộp cột Relative/Machine/Absolute và các giá trị tọa độ (50.800, 4.903, 97.461, -109.878, 64.900); không xác đ… |
| B0043 | 37–38 | Chữ OCR sai / ký tự lỗi | PDF tr. 38: danh sách ba thao tác chuyển hệ tọa độ, Half và Zero được chép, nhưng có ký tự “X” thừa đứng trước tiêu đề instruction parts do OCR lẫn… |
| B0044 | 38–38 | Thiếu / mất nội dung | PDF tr. 38 có Bước 1 chọn COORD, Bước 2 nhấn SWITCH và ghi chú thứ tự Machine→Absolute→DIS→Relative; chunk chỉ giữ tiêu đề, mất hướng dẫn. |
| B0046 | 40–40 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 40 có Bước 1 nhấn ZERO và Bước 2 chọn trục cần đưa về 0; chunk chỉ có tiêu đề 3.2.3. |
| B0050 | 42–42 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 42 có Bước 1 mở OPEN FILE và Bước 2 cắm USB/chọn chương trình/nhấn COPY; chunk chỉ còn tiêu đề 3.3.1. |
| B0051 | 43–44 | Khác | PDF tr. 43–44 có Bước 1–4; chunk chỉ giữ Bước 1–2, bỏ nhấn EXECUTE và kiểm tra chương trình sau khi chạy. |
| B0056 | 50–51 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 50–51 có Bước 1–3 xóa dòng lệnh; chunk chỉ giữ tiêu đề 3.3.5. |
| B0057 | 52–53 | Thiếu / mất nội dung | PDF tr. 52–53 có đủ 4 bước Copy/Paste; chunk bị cụt sau “press” ở Bước 3, mất tên nút COPY TO. |
| B0061 | 55–55 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 55 có Bước 1 chọn G54 và Bước 2 nhập giá trị trục; chunk chỉ giữ tiêu đề 3.4.1. |
| B0069 | 60–60 | Chữ OCR sai / ký tự lỗi | PDF tr. 60: ba mô tả Auto Option bị OCR chèn “O” vào câu và sai “form/from”; phần ý Auto Option/Continue bị méo. |
| B0070 | 60–61 | Chữ OCR sai / ký tự lỗi | PDF tr. 60–61 ghi đủ các mục Toolpath simulation/MDI/Auto features/Continue/Working history; OCR chèn chữ “O” trước mục Start program from any comm… |
| B0085 | 69–69 | Chữ OCR sai / ký tự lỗi | PDF tr. 69: OCR ảnh màn hình gộp MACHINE/ABSOLUTE/DIS TO GO và các tọa độ trục vào cùng ô; một số nhãn/value bị ghép, không thể gán chắc đúng cột. |
| B0086 | 69–69 | Chữ OCR sai / ký tự lỗi | PDF tr. 69: bảng lịch sử 105–113 bị OCR gộp với các nút điều hướng ở hàng cuối và đọc sai nhóm A thành “À”; cần tách lại hàng/cột để dùng lịch sử c… |
| B0088 | 70–70 | Chữ OCR sai / ký tự lỗi | PDF tr. 70: bảng SNC BIT có địa chỉ và cột +0 đến +7 nhưng OCR làm mất địa chỉ từng hàng, lặp các giá trị 0 và gộp nhãn/cột; bảng không đủ để tra bit. |
| B0090 | 71–71 | Chữ OCR sai / ký tự lỗi | PDF tr. 71: đoạn cảnh báo không tự ý đổi parameter bị OCR thành nhiều chuỗi không đọc được (“Th n p o…”, “whrd…”), làm mất nội dung an toàn quan tr… |
| B0091 | 71–71 | Chữ OCR sai / ký tự lỗi | PDF tr. 71: OCR ảnh giao diện gộp tọa độ MACHINE/ABSOLUTE/DIS TO GO, giá trị trục và thanh trạng thái vào sai cột. |
| B0092 | 71–71 | Bảng / hàng / cột | PDF tr. 71: bảng SDAXIS bị gộp địa chỉ 00000/00008/00016/00024/00032 với các tên AX*.ENA/DIR/SODI/HDIR/HDRF và giá trị; các hàng không còn ranh giớ… |
| B0094 | 72–74 | Chữ OCR sai / ký tự lỗi | PDF tr. 72–74 có đủ sáu bước cài thông số, nhưng Bước 4 chứa password 1415 bị OCR vỡ thành “e se n”/chuỗi lỗi; mã truy cập không còn đọc được. |
| B0096 | 75–75 | Chữ OCR sai / ký tự lỗi | PDF tr. 75: tên nút “SYS REG” bị OCR thành “sYs REG”; các dòng khác khớp nội dung. |
| B0097 | 75–75 | Thiếu / mất nội dung | PDF tr. 75 có hình trang PLC và hình ladder; chunk chỉ giữ “Model: F54 controller”, thiếu tên trang/chú thích nên không đủ ngữ cảnh. |
| B0098 | 75–75 | Chữ OCR sai / ký tự lỗi | PDF tr. 75: OCR ảnh màn hình gộp MACHINE/ABSOLUTE/DIS TO GO, tọa độ trục và nút PLC/Diagnostics thành các ô lẫn nhau. |
| B0101 | 77–77 | Chữ OCR sai / ký tự lỗi | PDF tr. 77: câu điều kiện “If the directory names or formats are incorrect, the data will not be loaded” bị OCR thành “If thc t ed.”, mất nội dung … |
| B0104 | 79–80 | Nhãn rời / thiếu ngữ cảnh | PDF tr. 78–80: Bước 5–6 được chép nhưng chunk kéo thêm ghi chú macro ở System section; đây là nội dung ngoài quy trình PLC và làm lẫn ngữ cảnh. |
| B0107 | 81–81 | Chữ OCR sai / ký tự lỗi | PDF tr. 81: OCR ảnh giao diện gộp tọa độ MACHINE/ABSOLUTE/DIS TO GO và thanh nút SYSTEM vào các giá trị, không giữ ranh giới cột. |
| B0112 | 81–81 | Chữ OCR sai / ký tự lỗi | PDF tr. 81–82: danh sách Firmware/Date & Time/Access permission khớp, nhưng OCR ghép nhãn “HARDWARE” từ ảnh trang trước vào đầu danh sách, làm lẫn … |
| B0114 | 82–83 | Khác | PDF tr. 82–83: password hiển thị là 1415; chunk đọc “1 415”, chèn dấu cách làm sai mã nhập. |
| B0117 | 85–86 | Thiếu / mất nội dung | PDF tr. 85–86: Bước 1 ghi nút “SYS.INIT”; chunk đọc “SYS.INT”, mất chữ I trong tên chức năng. Bước 2/3 còn đúng. |
| B0123 | 89–90 | Thiếu / mất nội dung | Đối chiếu trang PDF 89–90: chunk chỉ giữ tiêu đề/câu về lắp antenna, bỏ mất hướng dẫn nhấn SYSTEM và nhập mật khẩu 1415 ở trang 89. |
| B0129 | 93–94 | Chữ OCR sai / ký tự lỗi | Đối chiếu trang PDF 93–94: dòng OCR phần dẫn bị vỡ nặng; không giữ được thông tin IP và hướng dẫn bắt đầu truyền. |
| B0130 | 94–96 | Chữ OCR sai / ký tự lỗi | Đối chiếu trang PDF 94–96: chỉ còn Steps 1, 4, 5; thiếu Steps 2–3 và OCR hỏng chỉ dẫn kéo thả ở Step 5. |
| B0132 | 99–101 | Chữ OCR sai / ký tự lỗi | Đối chiếu trang PDF 99–101: M100 bị OCR thành “M1o0”; mô tả Stage 4–5 bị hỏng (“Zx e d…”), nên mất tốc độ tiếp xúc #14007. |
| B0136 | 102–103 | Thiếu / mất nội dung | Đối chiếu trang PDF 103: bảng trục bị cắt ngay trong trang; sau #4040–#4047 còn các dòng #4050–#8087 nhìn thấy trên cùng trang nhưng không có trong… |
| B0137 | 103–103 | Nhãn rời / thiếu ngữ cảnh | PDF trang 103: hàng #8010/#8011/#8013 bị lệch cột; nhãn Init rapid override, Init federate override và Feedrate default bị ghép sai với giá trị. |
| B0142 | 106–106 | Bảng / hàng / cột | PDF trang 106: dải mã user-defined bị tách qua hai cột (#2000- và #2079; tương tự các dải kế tiếp); cần nối mã theo nguồn. |

### f86-installation-en (3 chunk)

Nhóm: Thiếu / mất nội dung 3

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0005 | 9–9 | Thiếu / mất nội dung | Đối chiếu PDF trang 9: phần nối tiếp bảng servo không có tên cổng trong chunk; khi truy xuất riêng mất quan hệ với CN10/CN11. |
| B0006 | 10–10 | Thiếu / mất nội dung | Đối chiếu PDF trang 10: phần nối tiếp bảng servo thiếu tên cổng và phụ thuộc chunk trước; cần gắn theo CN12-CN14. |
| B0007 | 11–11 | Thiếu / mất nội dung | Đối chiếu PDF trang 11: phần tiếp nối bảng servo thiếu tên cổng; cần gắn theo CN14-CN15. PDF nguồn ghi mô tả X40-X47 dưới CN17 dù chân liệt kê X60-… |

### f86-operation-en (30 chunk)

Nhóm: Thiếu / mất nội dung 14; Chữ OCR sai / ký tự lỗi 10; Bảng / hàng / cột 4; Khác 1; Nhãn rời / thiếu ngữ cảnh 1

| Chunk | Trang | Nhóm | Ghi chú rút gọn |
|---|---|---|---|
| B0000 | 1–2 | Khác | Đối chiếu PDF Trang 1–2: “OURWEBSITE” bị dính chữ; địa chỉ www.qstcnc.com trên bìa không được giữ trong content. |
| B0008 | 15–15 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 15: hàng dẫn bảng input bị OCR hỏng thành “Reg g o o on signal”; không đọc được câu dẫn nguồn. |
| B0011 | 16–16 | Nhãn rời / thiếu ngữ cảnh | Đối chiếu PDF Trang 16: tiêu đề/caption cảm biến 4 dây NPN bị hỏng thành “i- ns dpn”. |
| B0016 | 18–18 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 18: bảng nhãn pha Z bị OCR sai pin “/PCO PC q”; nguồn ghi /PCO, PCO và Z PHASE. |
| B0017 | 19–19 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 19: bảng nhãn pha Z bị OCR sai chuỗi pin thành “/PCO PCO d”. |
| B0020 | 20–20 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 20: bảng nhãn pha Z bị OCR thành “/PCO PC Z PHASE”, mất/sai tên pin so với sơ đồ. |
| B0023 | 21–21 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 21: các nhãn GND, DAC, DA.V, V_IN trong bảng bị OCR sai, làm hỏng cấu trúc đấu nối. |
| B0040 | 37–37 | Bảng / hàng / cột | Đối chiếu PDF Trang 37: hàng cuối nguồn là số 9 (Machine coordinate system), nhưng chunk ghi số 6, trùng hàng 6. |
| B0043 | 38–38 | Thiếu / mất nội dung | Đối chiếu PDF Trang 38: tính năng đầu tiên bị vỡ thành “swn S sin s sn :sn ten”; mất tên Switch screen. |
| B0045 | 39–39 | Thiếu / mất nội dung | Đối chiếu PDF Trang 39: chỉ có tiêu đề SWITCH SCREEN; thiếu Steps 1–2 (COORD, FULL SCREEN) trong nguồn. |
| B0046 | 40–40 | Thiếu / mất nội dung | Đối chiếu PDF Trang 40: chỉ có tiêu đề HALF; thiếu Steps 1–2 chọn trục và chọn HALF. |
| B0047 | 41–42 | Thiếu / mất nội dung | Đối chiếu PDF Trang 41–42: chỉ có tiêu đề ZERO-ZERO ALL; thiếu Steps 1–4 và kết quả đưa tọa độ về 0. |
| B0051 | 44–44 | Thiếu / mất nội dung | Đối chiếu PDF Trang 44: chỉ có tiêu đề COPY DATA FROM USB TO CONTROLLER; thiếu các thao tác mở/chọn file và COPY. |
| B0052 | 45–46 | Thiếu / mất nội dung | Đối chiếu PDF Trang 45–46: chỉ còn Steps 3–4; hướng dẫn mở/chọn file ở đầu thủ tục bị thiếu. |
| B0054 | 47–48 | Thiếu / mất nội dung | Đối chiếu PDF Trang 47–48: chunk con chỉ có tiêu đề và Step 2; thiếu bước mở trang trước đó, không đủ thủ tục độc lập. |
| B0055 | 48–48 | Thiếu / mất nội dung | Đối chiếu PDF Trang 48: chunk con chỉ có Steps 3–4, thiếu thao tác mở Go To Line và các bước trước. |
| B0057 | 49–51 | Thiếu / mất nội dung | Đối chiếu PDF Trang 49–51: chunk con chỉ có Steps 3–5; thiếu thao tác tìm ban đầu ở Steps 1–2. |
| B0059 | 52–53 | Thiếu / mất nội dung | Đối chiếu PDF Trang 52–53: chỉ còn Step 3; thiếu thao tác DELETE LINE và chọn dòng ở Steps 1–2. |
| B0060 | 54–55 | Thiếu / mất nội dung | Đối chiếu PDF Trang 54–55: chỉ có tiêu đề COPY AND PASTE; toàn bộ Steps 1–4 không có trong content. |
| B0064 | 57–59 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 57–59: có OCR rác “ES S EM”; chỉ còn Steps 1–2, thiếu Step 3 và ghi chú trang 59. |
| B0083 | 72–72 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 72: OCR bảng trong hình mất/trộn cột No./Group/ID/Time/Content và làm cụt nhiều cảnh báo. |
| B0088 | 74–74 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 74: cùng đoạn cảnh báo Parameter bị OCR hỏng và mất nội dung; phần tính năng phía sau còn đọc được. |
| B0092 | 78–78 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 78: tên nút “SYS BIT/SYS REG” bị OCR sai thành “sYs BIT/REG”. |
| B0095 | 80–80 | Thiếu / mất nội dung | Đối chiếu PDF Trang 80: câu về sai tên thư mục/định dạng bị vỡ thành “If th e t e s ed”; mất phần dẫn bảng. |
| B0101 | 85–87 | Thiếu / mất nội dung | Đối chiếu PDF Trang 85–87: Steps 1–2 thiếu/để trống (đăng nhập, chọn FIRMWARE và nhấn UPDATE); chỉ Step 3 còn hướng dẫn rõ. |
| B0102 | 88–89 | Thiếu / mất nội dung | Đối chiếu PDF Trang 88–89: chỉ có Step 3; Steps 1–2 (SYS.INIT và TIME/DATE) không có trong chunk. |
| B0103 | 90–92 | Chữ OCR sai / ký tự lỗi | Đối chiếu PDF Trang 90–92: M100 bị OCR thành M1o0; mô tả Stage 4–5 hỏng thành “Zx e d…” và mất tốc độ #14007. |
| B0107 | 93–94 | Bảng / hàng / cột | Đối chiếu PDF Trang 94: bảng dừng ở #4010–#4017; các dòng ngay dưới đến #8080–#8087 trên cùng trang bị bỏ. |
| B0108 | 94–94 | Bảng / hàng / cột | PDF trang 94: cột Axis encoder port/multiply bị lệch; lựa chọn port 6 bị gán sang hàng #4160 (encoder multiply). |
| B0113 | 97–97 | Bảng / hàng / cột | PDF trang 97: mã user-defined bị tách cột (#10000- và #10049; #14000- và #14049), không giữ nguyên dải tham số. |

## Chunk lá `pending` (24)

| Chunk | Trang | Ghi chú |
|---|---|---|
| 6ah-operation-en:B0119 | 101–101 | PDF trang 101 đọc được. Giữ pending: cần so từng mã tham số, dải trục và giá trị trong chunk với bảng nguồn ở độ phóng đại lớn; không kết luận chỉ từ  |
| 6ah-operation-en:B0120 | 101–101 | PDF trang 101 đọc được. Giữ pending: cần đối chiếu từng dải #12130-#12330, nhãn hành trình và đơn vị BLU với bảng nguồn. |
| 6ah-operation-en:B0121 | 102–102 | PDF trang 102 đọc được. Giữ pending: cần so từng mã spindle, dải gear và giá trị mặc định; tránh bỏ sót sai ký tự/mã. |
| 6ah-operation-en:B0122 | 102–103 | PDF trang 102-103 đọc được. Giữ pending: chunk nối bảng spindle/general; cần xác minh đầy đủ ranh bảng và từng mã ở hai trang. |
| 6ah-operation-en:B0123 | 103–103 | PDF trang 103 đọc được. Giữ pending: cần phóng to kiểm tra ba dải user-defined và cột mặc định trước khi chấp nhận. |
| 6ah-operation-en:B0124 | 103–103 | PDF trang 103 đọc được. Giữ pending: cần đối chiếu đủ các mã macro và phạm vi giá trị với bảng nguồn. |
| 6ave-operation-en:B0122 | 108–108 | PDF trang 108 đọc được. Giữ pending: cần so từng mã tham số/dải trục, đơn vị và giá trị với bảng nguồn. |
| 6ave-operation-en:B0123 | 108–108 | PDF trang 108 đọc được. Giữ pending: cần xác nhận từng mã #12130-#12330 và nội dung hàng tiếp nối trước khi chấp nhận. |
| 6ave-operation-en:B0124 | 109–109 | PDF trang 109 đọc được. Giữ pending: cần đối chiếu từng mã spindle/gear và giá trị mặc định. |
| 6ave-operation-en:B0125 | 109–110 | PDF trang 109-110 đọc được. Giữ pending: chunk nối bảng spindle/general; cần xác minh ranh bảng và từng mã qua hai trang. |
| f10t-operation-vi:B0122 | 103–103 | PDF trang 103 đọc được. Giữ pending: cần so từng mã tham số, dải trục, đơn vị và giá trị với bảng nguồn. |
| f10t-operation-vi:B0123 | 103–103 | PDF trang 103 đọc được. Giữ pending: cần xác nhận từng mã #12130-#12330 và nội dung hàng tiếp nối. |
| f10t-operation-vi:B0124 | 104–104 | PDF trang 104 đọc được. Giữ pending: cần đối chiếu từng mã spindle/gear và giá trị mặc định. |
| f10t-operation-vi:B0125 | 104–105 | PDF trang 104-105 đọc được. Giữ pending: chunk nối bảng spindle/general; cần kiểm tra đủ nội dung hai trang và ranh bảng. |
| f54-operation-en:B0138 | 104–104 | PDF trang 104 đọc được. Giữ pending: cần đối chiếu từng mã tham số/dải trục, đơn vị và giá trị với bảng nguồn. |
| f54-operation-en:B0139 | 104–104 | PDF trang 104 đọc được. Giữ pending: cần xác nhận từng mã #12130-#12330 và hàng tiếp nối. |
| f54-operation-en:B0140 | 105–105 | PDF trang 105 đọc được. Giữ pending: cần so từng mã spindle/gear và giá trị mặc định. |
| f54-operation-en:B0141 | 105–106 | PDF trang 105-106 đọc được. Giữ pending: chunk nối bảng spindle/general; cần kiểm tra đủ nội dung hai trang và ranh bảng. |
| f86-installation-en:B0003 | 6–7 | PDF trang 6-7 đọc được. Giữ pending: chunk bao phủ phần PORT TABLE nhiều hàng; cần so từng cổng/chân và mô tả trước khi xác nhận đủ/nguyên văn. |
| f86-installation-en:B0004 | 7–8 | PDF trang 7-8 đọc được. Giữ pending: bảng chuyển tiếp từ CN5/CN6 sang CN7-CN10; cần xác định chính xác ranh hàng/cột trong chunk. |
| f86-operation-en:B0109 | 95–95 | PDF trang 95 đọc được. Giữ pending: cần so từng dải mã tham số, đơn vị và giá trị với bảng nguồn. |
| f86-operation-en:B0110 | 95–95 | PDF trang 95 đọc được. Giữ pending: cần xác nhận từng mã #12130-#12330 và quan hệ các hàng giới hạn trục. |
| f86-operation-en:B0111 | 96–96 | PDF trang 96 đọc được. Giữ pending: cần so từng mã spindle/gear và giá trị mặc định. |
| f86-operation-en:B0112 | 96–97 | PDF trang 96-97 đọc được. Giữ pending: chunk nối bảng spindle/general; cần kiểm đủ hai trang và ranh bảng. |
