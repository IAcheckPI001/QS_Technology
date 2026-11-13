# Báo cáo đo lại phương án C (`crm_schema` + `crm_query`), 2026-11-12

So với đợt đo nền ngày 2026-11-11 (gpt-4o-mini 37/63, gpt-4.1-mini 40/63).
Luồng: [crm-agent](../flows/crm-agent/README.md). Log thô có dữ liệu CRM nên không đưa vào repo.

## 1. Tóm tắt

| | gpt-4o-mini | gpt-4.1-mini |
|---|---|---|
| **Cùng 21 case của đợt nền** | 37/63 → **38/63** (+1) | 40/63 → **38/63** (−2) |
| 6 case mới (4 case vai trò, d1, d2) | 12/18 | 12/18 |
| **Toàn bộ 27 case** | **50/81 (62%)** | **50/81 (62%)** |
| Token vào trung bình mỗi câu (21 case) | 23,9k → 32,2k (+35%) | 22,7k → 31,6k (+39%) |
| Số bước LLM trung bình (21 case) | 3,7 → 4,1 | 3,6 → 4,1 |
| Latency p50 / p95 (21 case) | 4,4s / 12,9s → 6,2s / 19,1s | 4,2s / 9,6s → 5,5s / 15,4s |

Điểm chính:

1. **Các chỗ sửa nhắm đúng lỗi đều hiệu quả.** 4 câu đếm nhân viên theo vai trò đạt 24/24. Tra nhân viên theo tên (q9, q11) với gpt-4o-mini tăng từ 0/6 lên 5/6. "Xem tiếp trang sau" (f1) với gpt-4.1-mini tăng từ 0/3 lên 3/3.
2. **Tổng điểm gần như đứng yên** vì ba nhóm việc kéo xuống:
   - (a) **Ngày tháng** vẫn là nhóm lỗi lớn nhất: LLM đặt kỳ trong `filters` và tự điền năm sai (2023, 2026).
   - (b) **Hồi quy mới:** mô tả cột mới khiến LLM áp luật "trạng thái hiện tại" sai chỗ (`is_current`, `deleted_at`).
   - (c) **Chấm siết hơn:** nhiều lượt lấy đúng dữ liệu nhưng gọi thêm tool để tra tên, vượt giới hạn 4 lần gọi.
3. **Chi phí tăng khoảng 35–39% token mỗi câu.** Nguồn: output `crm_schema` dài hơn (có mô tả của CRM), cộng thêm bước vì query đặt ngày sai chỗ giờ bị chặn và LLM phải gọi lại.
4. **Phân vùng lượt trượt (mục 8):** gpt-4.1-mini có 19/25 lượt trượt do phía eval (dữ liệu case không còn hợp lệ, chấm theo cách viết, vượt số lần gọi). Lỗi thật của nó chỉ còn ở luật nghiệp vụ. gpt-4o-mini có 21/25 lượt trượt là lỗi thật.
5. Lỗi sai giờ đã thành lỗi "ồn ào" thay vì "im lặng": query bị chặn ở dịch vụ AI tăng từ 12 lên 31 (gpt-4o-mini). Trước đây các query này tới CRM và trả 0 dòng mà không báo lỗi.

## 2. Cấu hình đo

| Mục | Đợt nền 2026-11-11 | Đợt này 2026-11-12 |
|---|---|---|
| Tool | `CRM_TOOLS=query` (`crm_schema`, `crm_query`) | như cũ |
| Giới hạn | `AGENT_MAX_STEPS=5`, `AGENT_MAX_TOOL_CALLS=8`, completion 1200 token | như cũ |
| Token CRM | admin | admin |
| Số case × lần | 21 × 3 | 27 × 3 (thêm d1, d2 từ P0 và v1–v4 vai trò) |
| Model | gpt-4o-mini, gpt-4.1-mini | như cũ |
| Script | `evals/compare_agent_models.py --runs 3` | như cũ |

Thay đổi giữa hai đợt:
- **P0:** kiểm giá trị filter theo kiểu cột (chặn tên trên cột uuid, chặn đặt ngày trong `filters`); `date_range` có `preset=month/year`.
- **Schema CRM mới** đưa tới LLM: mô tả bảng và cột, quan hệ 1-1/có thể trống, nghĩa của `deleted_at`, `known_values` (giá trị thật của vai trò, trạng thái).
- **Thời gian** trả về đổi sang giờ Việt Nam.
- **Nhân viên theo vai trò:** dùng `user_roles`, mặc định chỉ tính tài khoản còn dùng, có tham số `include_inactive`.
- **Expect siết hơn:** r2 và q7 kiểm thêm `order_by`; r3 cấm lọc `deleted_at`; f1 đổi câu hỏi. Vì vậy so điểm của r2, r3, q7, f1 giữa hai đợt chỉ mang tính tham khảo.

## 3. Kết quả theo case

Ký hiệu: số lần đạt/3, dạng *nền → mới*. "–" là case chưa có ở đợt nền.

| Case | Câu hỏi | gpt-4o-mini | gpt-4.1-mini | Nguyên nhân chính khi trượt |
|---|---|---|---|---|
| r1 | Sale username an tháng này hỗ trợ bao nhiêu khách? | 0 → 0 | 1 → 2 | Username `an` không tồn tại nên case không thể ra "ok". gpt-4o-mini hiểu "sale" là username |
| r2 | Top 10 sale có nhiều khách mới nhất tháng trước | 3 → 0 | 3 → 0 | **Dữ liệu đúng**, nhưng gọi thêm `auth_users` để tra username → 5 lần gọi tool > 4. Lần đầu đặt ngày trong `filters`, bị chặn, mất 1 bước |
| r3 | Tháng 10 bán được những sản phẩm nào? | 2 → 0 | 3 → 3 | **Hồi quy (gpt-4o-mini):** tự lọc `deleted_at is_null` và tự đặt năm 2023 → rỗng, trả lời "không bán được" |
| r4 | Liệt kê phiếu đã xong | 3 → 3 | 3 → 3 | |
| r5 | Đếm không phải liệt kê | 3 → 3 | 3 → 3 | |
| q1 | Tìm khách theo tên | 3 → 3 | 3 → 3 | |
| q2 | PO theo trạng thái | 3 → 3 | 3 → 3 | |
| q3 | Tồn kho từng vật tư | 3 → 3 | 3 → 0 | **Dữ liệu đúng (gpt-4.1-mini)**, nhưng tra thêm tên vật tư và kho → 5 lần gọi; 1 lần đoán cột `code`, `material_code` không tồn tại |
| q4 | Số tài khoản đang hoạt động | 3 → 3 | 3 → 3 | |
| v1 | Có bao nhiêu nhân viên sales? | – → 3 | – → 3 | Đúng 3 người |
| v2 | Tính cả người đã nghỉ thì bao nhiêu nhân viên sales? | – → 3 | – → 3 | Đúng 4 người |
| v3 | Có bao nhiêu nhân viên kho? | – → 3 | – → 3 | Đúng mã `KHO`, 0 người |
| v4 | Có bao nhiêu nhân viên kế toán? | – → 3 | – → 3 | Đúng 1 người |
| q5 | Liệt kê họ tên và username 5 nhân viên | 3 → 3 | 3 → 3 | |
| q6 | Năm nay mỗi tháng có bao nhiêu khách mới? | 2 → 3 | 0 → 0 | gpt-4.1-mini nhóm theo `created_at_month` thay vì `created_month`: **số đúng** (hai cột cho cùng kết quả), trượt do expect chấm theo tên cột |
| q7 | 5 khách mới nhất của sale username an | 3 → 3 | 0 → 0 | gpt-4.1-mini lọc đúng `username eq an` và trả lời "không có" (**đúng**, username không tồn tại); gpt-4o-mini đạt vì dùng `contains` |
| q9 | Khách của nhân viên theo tên | 0 → 3 | 3 → 3 | **Cải thiện** nhờ chặn tên trên cột uuid (P0) |
| q10 | "Hiện tại" không phải kỳ thời gian | 3 → 3 | 3 → 3 | |
| q11 | Nhân viên không tồn tại | 0 → 2 | 3 → 3 | **Cải thiện** |
| q12 | Tài khoản username an có vai trò nào? | 0 → 0 | 0 → 0 | Username `an` không tồn tại: gpt-4.1-mini trả lời "không tìm thấy" (**đúng**). gpt-4o-mini 2/3 lần hỏi lại username dù câu hỏi đã nêu |
| q13 | Hiện tại tháng 10 nhân viên nào nhiều phiếu nhất? | 0 → 0 | 0 → 0 | Thêm `is_current = true` 6/6 lần: câu có chữ "hiện tại", và mô tả CRM ghi "Count current workload with is_current = true". Expect cấm lọc này; câu hỏi tự nó mơ hồ |
| s1 | Hiện có bao nhiêu khách hàng? | 0 → 0 | 0 → 0 | Không loại khách `spam`/`lost` như ghi chú yêu cầu |
| s2 | Giá trị trạng thái không có ghi chú | 3 → 3 | 3 → 3 | |
| f1 | Lượt sau "xem tiếp" | 0 → 0 | 0 → 3 | **Cải thiện** (gpt-4.1-mini) |
| f2 | Lượt sau "trong số đó model F86" | 0 → 0 | 0 → 0 | gpt-4.1-mini lọc `product_id.code = F86`, **số đúng** (1 phiếu; `code` = `name`) nhưng expect chấm theo `.name`. gpt-4o-mini tự đặt năm 2023 và bỏ điều kiện F86 |
| d1 | Tháng 12 có bao nhiêu khách mới? | – → 0 | – → 0 | LLM tự điền `year: 2026` → tháng tương lai, rỗng. Code tính đúng 12/2025 khi `year = null` |
| d2 | Tạo tháng 10 nhưng tháng 11 mới đóng? | – → 0 | – → 0 | LLM tự đặt năm **2023** (đúng phải là 2026) |

## 4. Chỉ số vận hành (cùng 21 case)

| Chỉ số | gpt-4o-mini nền | gpt-4o-mini mới | gpt-4.1-mini nền | gpt-4.1-mini mới |
|---|---|---|---|---|
| `crm_query` ok | 59 | 64 | 54 | 67 |
| `crm_query` rỗng (0 dòng) | 26 | 24 | 20 | 15 |
| CRM từ chối (400) | 5 | 4 | 7 | 3 |
| Bị chặn ở dịch vụ AI | 12 | **31** | 5 | **29** |
| Phân phối số bước LLM | 3 bước: 37/63 | 3 bước: 28/63 | 3 bước: 45/63 | 3 bước: 35/63 |
| % token cố định (system prompt + định nghĩa tool) | 92% | 87% | 94% | 88% |

Lý do bị chặn (toàn bộ 27 case):
- gpt-4o-mini: đặt ngày trong `filters` 25, uuid 7, khác 12;
- gpt-4.1-mini: đặt ngày trong `filters` 34, đường dẫn 1, khác 6.

Cách đọc:
- **Rỗng giảm, CRM từ chối giảm, bị chặn tăng mạnh:** P0 bắt lỗi trước khi gửi CRM. Lỗi không còn im lặng, nhưng mỗi lần bị chặn tốn thêm một bước LLM.
- **% token cố định giảm** vì phần thay đổi theo câu (output `crm_schema`, các bước gọi lại) tăng, không phải vì phần cố định nhỏ đi.

## 5. Nhóm lỗi còn lại, xếp theo ảnh hưởng

| # | Nhóm lỗi | Case bị ảnh hưởng | Bằng chứng |
|---|---|---|---|
| 1 | **Ngày tháng**: đặt kỳ trong `filters` (`created_at contains "2026-10"`), tự điền năm sai (2023, 2026) dù prompt có ngày hôm nay | r2, r3, d1, d2, f2, q13 | 59 lần bị chặn vì ngày (2 model); d1, d2 0/12 |
| 2 | **Áp luật "hiện tại" sai chỗ** sau khi có mô tả mới | q13 (`is_current`), r3 (`deleted_at`) | 9/9 lượt có lọc thừa |
| 3 | **Gọi thêm tool để tra tên** thay vì nhóm hoặc chọn thẳng `assigned_sales_id.username`, `material_id.name` | r2, q3, q13 | Dữ liệu đúng nhưng 5 lần gọi > 4 |
| 4 | **Ghi chú nghiệp vụ không được áp** | s1 (loại spam/lost), q6 (cột `created_month`) | 0/6 ở cả hai đợt |
| 5 | **Hiểu sai câu hỏi và mất ngữ cảnh qua lượt** (chủ yếu gpt-4o-mini) | r1, q12, q11, f1 | Phần lớn trượt của r1, q7, q12 với gpt-4.1-mini là do dữ liệu case (username `an` không tồn tại), xem mục 8 |

## 6. Đã cải thiện

| Nội dung | Trước | Sau |
|---|---|---|
| Đếm nhân viên theo vai trò (v1–v4) | Câu sales trả lời 46 (sai) | 24/24 đúng, khớp `POST /reports/query` |
| Tra nhân viên theo tên (q9, q11, gpt-4o-mini) | 0/6 | 5/6 |
| Xem tiếp trang sau (f1, gpt-4.1-mini) | 0/3 | 3/3 |
| Query rỗng vì sai kiểu giá trị | Đi tới CRM, ra 0 dòng không báo lỗi | Bị chặn kèm thông báo để LLM sửa |

## 7. Hạn chế của đợt đo

- Mỗi case chỉ chạy 3 lần nên kết quả LLM dao động: chênh ±1–2 lượt trên 63 chưa đủ để kết luận tốt lên hay xấu đi.
- Expect của r2, r3, q7, f1 đã đổi giữa hai đợt (xem mục 2).
- Chỉ đo bằng token admin; chưa đo bằng token sale thường.
- `product_docs_ask` (tìm tài liệu sản phẩm) lỗi trên harness Windows (`psycopg` không chạy trên `ProactorEventLoop`). Lỗi này chỉ xuất hiện khi LLM gọi nhầm tool đó (f2) và không tính là lỗi chạy.
- Một số lượt bị chấm trượt dù câu trả lời có thể đúng: r2, q3 (vượt số lần gọi), f2 (lọc theo `code` thay vì `name`). Nếu chỉ chấm "dữ liệu đúng", điểm thực tế cao hơn bảng trên.

## 8. Phân vùng các lượt trượt (cùng 21 case, mỗi model 25 lượt trượt)

Mỗi lượt trượt được xếp vào **một** vùng theo nguyên nhân chính, dựa trên log từng lượt và đối chiếu
trực tiếp bằng `POST /reports/query`. Đối chiếu cho thấy:
- username `an` không tồn tại (khớp chính xác: 0 tài khoản);
- tháng 11/2026 không có lần giao phiếu nào cho tài khoản có "an" trong username;
- F86 có `code` và `name` giống nhau (đều ra 1 phiếu);
- `created_month` và `created_at_month` cho cùng số theo từng tháng;
- khách trừ spam/lost là 545, trong khi agent trả lời 550.

| Vùng | Mô tả | gpt-4o-mini | gpt-4.1-mini | Case |
|---|---|---|---|---|
| **Phía eval** | | **4** | **19** | |
| E1 | Dữ liệu của case không còn hợp lệ: agent trả lời "không tìm thấy username an" là đúng | 1 | 7 | r1, q7, q12 |
| E2 | Expect chấm theo một cách viết, số liệu đã đối chiếu là đúng | 0 | 6 | q6 (`created_at_month`), f2 (`code` = F86) |
| E3 | Dữ liệu đúng nhưng gọi thêm tool tra tên, vượt giới hạn 4 lần gọi | 3 | 6 | r2, q3 |
| **Phía agent** | | **21** | **6** | |
| A1 | Ngày tháng: LLM tự điền năm 2023 cho "tháng 10" → rỗng, trả lời "không có" | 6 | 0 | r3, f2 |
| A2 | Áp luật "hiện tại" sai chỗ: thêm `is_current` khi câu hỏi có kỳ (r3 còn thêm `deleted_at`) | 3 | 3 | q13 |
| A3 | Không áp định nghĩa nghiệp vụ: không loại khách spam/lost (550 thay vì 545) | 3 | 3 | s1 |
| A4 | Hiểu sai tham số câu hỏi: lấy "sale" làm username; hỏi lại username dù câu hỏi đã nêu; tra người theo username thay vì theo tên | 6 | 0 | r1, q12, q11 |
| A5 | Mất ngữ cảnh qua lượt: lượt "xem tiếp" chọn cột không tồn tại, rồi bỏ điều kiện năm và offset | 3 | 0 | f1 |

Cách đọc:
- **gpt-4.1-mini:** 19/25 lượt trượt do phía eval. Lỗi thật chỉ còn 6 lượt, đều là luật nghiệp vụ
  (A2, A3). Nếu chỉ chấm "số liệu trả lời đúng", gpt-4.1-mini đạt khoảng **57/63**.
- **gpt-4o-mini:** 21/25 lượt trượt là lỗi thật, trải rộng: năm, hiểu câu hỏi, ngữ cảnh qua lượt,
  luật nghiệp vụ. Chấm theo số liệu đúng thì khoảng **42/63**.
- Các case r1, q7, q12 cần sửa dữ liệu: đổi sang username có thật, hoặc chấm "không tìm thấy" là đạt.
  Expect của q6, f2 nên chấp nhận cả `created_at_month` và `code`.

## 9. Đề xuất bước tiếp, theo thứ tự ưu tiên

1. **Ngày tháng (nhóm 1).** Sửa trong code, không thêm câu chữ vào guide:
   - query đặt ngày trong `filters` khi `date_range` trống: tự chuyển thành `date_range` thay vì chặn (bớt một bước);
   - thông báo lỗi ngày kèm ngày hôm nay và luật "tháng không nêu năm thì `year = null`";
   - từ chối kỳ nằm trọn trong tương lai (d1).
2. **Luật "hiện tại" (nhóm 2).**
   - Chỉ lọc `is_current` hoặc `deleted_at` (loại kết thúc) khi câu hỏi không có kỳ thời gian. Có `date_range` thì không tự lọc.
   - Xem lại câu hỏi q13 ("Hiện tại tháng 10…") vì chính câu hỏi đã mơ hồ.
   - Cân nhắc đề nghị CRM bỏ câu "Count current workload with is_current = true" khỏi mô tả cột, hoặc ghi thêm điều kiện.
3. **Tra tên trong cùng query (nhóm 3):** guide hướng dẫn nhóm hoặc chọn thẳng cột tên qua join (`assigned_sales_id.username`, `material_id.name`) thay vì lấy UUID rồi tra.
4. **Tách chấm điểm** thành "dữ liệu đúng" và "trong ngân sách bước", để thấy rõ phần chi phí và phần sai.
5. **Semantic layer (P1):** nhóm 2 và 4 là luật nghiệp vụ mà LLM nhỏ không áp đều. Khai báo trong code, như đã làm với filter mặc định của `user_roles`, cho kết quả ổn định hơn.
6. **Sửa bộ eval (mục 8):** thay username `an` ở r1, q7, q12 bằng tài khoản có thật; nới expect của q6 và f2.
