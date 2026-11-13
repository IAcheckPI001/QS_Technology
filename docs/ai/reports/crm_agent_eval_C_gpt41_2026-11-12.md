# Eval phương án C với gpt-4.1-mini sau hướng Y, 2026-11-12

Chỉ đo gpt-4.1-mini (quyết định của Toma 2026-11-12: không chạy, không so với gpt-4o-mini). Mốc so
sánh là chính gpt-4.1-mini ở đợt sáng cùng ngày ([báo cáo trước](crm_agent_eval_C_2026-11-12.md):
50/81 toàn bộ, 38/63 trên 21 case cũ). Luồng: [crm-agent](../flows/crm-agent/README.md). Log thô
có dữ liệu CRM nên nằm ngoài repo.

## 1. Tóm tắt

| | Mốc sáng | Đợt (a) | Đợt (b) | **Đợt (c)** |
|---|---|---|---|---|
| Thay đổi | | Sửa code (ngày, spam, `is_current`) + sửa eval | (a) + làm gọn guide, bỏ enum bảng, sửa thêm từ (a) | (b) + khôi phục 2 dòng guide |
| Toàn bộ 27 case | 50/81 | 64/81 | 69/81 | **78/81 (96%)** |
| 21 case cũ | 38/63 | 52/63 | 54/63 | **60/63** |
| Đạt nếu bỏ giới hạn số lần gọi | | 66/81 | 75/81 | 78/81 |
| Token vào tb mỗi câu | ~29,9k | 28,7k | 22,1k | **21,0k (−30%)** |
| Bước LLM tb | 4,1 | 3,73 | 3,80 | 3,58 |
| Latency p50 / p95 | | 4,7s / 14,0s | 4,7s / 15,5s | 4,5s / 12,1s |
| Query bị chặn ở dịch vụ AI | | 17 | 22 | 9 |

Điểm chính:
1. **Lỗi nghiệp vụ và lỗi ngày đã hết trong eval.**
   - s1 (khách trừ spam), q13 (`is_current` khi có kỳ), d1, d2 đều đạt 3/3.
   - Không còn năm sai tới CRM: năm câu hỏi không nêu do code đối chiếu.
2. **Phần cố định mỗi bước LLM giảm từ 5.868 xuống 4.251 token (−28%).**
   - guide `crm_query`: 2.044 → 1.525;
   - JSON schema `RawQuery`: 1.989 → 1.440;
   - `SchemaRequest`: 646 → 97 (bỏ enum 116 tên bảng);
   - TABLE_NOTES: 1.234 → 1.074.
3. **Làm gọn guide có giới hạn.** Đợt (b) bỏ quá tay hai dòng, làm tụt q3, r2 và làm d2 trả **số sai**
   (22 thay vì 0). Khôi phục hai dòng đó ở đợt (c) thì hết, và không case nào tụt so với (a).

## 2. Thay đổi giữa các đợt

| Đợt | Thay đổi |
|---|---|
| (a) | Bỏ năm câu hỏi không nêu (`dates.stated_years`); kỳ đặt trong `filters` tự chuyển thành `date_range`; `customers` mặc định loại spam; `support_assignments` có kỳ thì bỏ `is_current`; `<now>` đặt trước tool guide; eval dùng username có thật (`{staff_username}`), nới expect q6, f2, tách chấm "bỏ giới hạn gọi" |
| (b) | Guide gọn lại (2.044 → 1.352 token) kèm 4 luật mới từ dữ liệu (a): có username thì lọc thẳng qua join; mỗi lượt gọi `crm_schema`; câu trả lời nêu tháng/năm đã dùng; không tự đặt lại filter mặc định. Bỏ enum tên bảng, kiểm trong code kèm gợi ý. Bỏ 8 ghi chú chỉ liệt kê cột. Code: bỏ filter lặp kỳ của `date_range`, chuyển `<cột>_month eq "N"`, `not_null` bỏ qua value, gợi ý khoá ngoại khi dùng tên bảng. Eval: `date_field`/`no_date_range` xét body gửi CRM; d1 chấp nhận rỗng nhưng phải nêu "2025" |
| (c) | Khôi phục dòng ngày đầy đủ (ví dụ "tạo tháng 10 nhưng đóng tháng 11", "filter ngày kiểu khác bị từ chối") và ví dụ `select [material_id.name]` (guide 1.525 token) |

Lưu ý: (a) chấm d1, d2 theo expect cũ. Theo expect mới, d2 của (a) đạt 3/3: số liệu đúng, chỉ là
matcher cũ đọc sai cột ngày.

## 3. Kết quả theo case

| Case | (a) | (b) | (c) | Ghi chú |
|---|---|---|---|---|
| r1 sale hỗ trợ bao nhiêu khách | 1 | 1 | 2 | Xem vùng B1 |
| r2 top 10 sale có nhiều khách mới | 1 | 0 | **3** | (b) đặt kỳ trong filters bằng `in`, bị chặn, vượt 4 lần gọi |
| r3, r4, r5, q1, q2, q4, q5, q6, q9, q10, q11, q13, s1, s2, f2, v1–v4 | 3 | 3 | 3 | |
| q3 tồn kho từng vật tư | 3 | 0 | **3** | (b) tra tên vật tư/kho bằng query riêng → 5 lần gọi |
| q7 5 khách mới nhất của sale | 1 | 2 | 2 | Xem vùng B2 |
| q12 vai trò của tài khoản | 0 | 3 | 2 | Xem vùng B2 |
| f1 xem tiếp trang sau | 1 | 3 | 3 | (a) tự nghĩ cột `is_spam` ở lượt 2 |
| d1 "tháng 12" | 0 | 3 | 3 | Tháng 12/2025 có 0 khách (cả 550 khách tạo năm 2026): rỗng là đúng |
| d2 tạo tháng 10, đóng tháng 11 | 0 | 0 | **3** | Đáp số 0 (22 phiếu tạo tháng 10 đều đóng trong tháng 10). (b) trả **22, sai** |

## 4. Phân vùng 3 lượt trượt của đợt (c)

| Vùng | Mô tả | Lượt | Case |
|---|---|---|---|
| B1 | **Nghĩa nghiệp vụ chưa chốt**: "khách" của phiếu hỗ trợ. LLM đếm `customer_organization_id` (trống ở cả 3 phiếu), dùng tên bảng làm đường dẫn 4 lần dù đã có gợi ý, rồi hỏi lại "khách tổ chức hay khách cá nhân". Ghi chú của mình dùng `product_item_id.customer_id`, cho đáp số 3 | 1 | r1 |
| B2 | Tra `auth_users.id` trước rồi mới lọc theo UUID, thay vì lọc thẳng `…username`. Số liệu đúng, chỉ thêm 1–2 lần gọi | 2 | q7, q12 |

## 5. Kiểm thêm: câu hỏi nhiều sale (sau đợt c)

Câu hỏi: "còn 2 sale kìa thì có số khách hàng đang phụ trách là bao nhiêu, với khách hàng đầu tiên
tên gì". Agent chạm giới hạn gọi tool. Kiểm bằng `POST /reports/query` (token admin):

| Query | Kết quả |
|---|---|
| Username LLM dùng (`hieu.nguyen-sm`, `son`) | 0 tài khoản: thiếu `@qstcnc.com`. LLM tự suy username, nên query ra rỗng và gọi lại tới hết lượt |
| Số khách của nhiều sale: một query, `filter in` + `dimensions [assigned_sales_id.username]` | Đúng: 259, 76, 8 (đã trừ spam) |
| Khách đầu tiên của từng sale: một danh sách, `in` + `order_by [username, created_at]` | Hợp lệ, nhưng 50 dòng đầu đều của một người, người kia bị che. Phải tách mỗi người một query `limit 1` |
| `min:created_at` theo nhóm | CRM 400: `min` chỉ nhận cột số |

Sửa sau kiểm tra này (chưa eval, Toma tự kiểm):
- Runner: call bị `tool_call_limit` không trừ trần chung `AGENT_MAX_TOOL_CALLS`.
- `crm_query`: trần 4 chỉ đếm lần gửi CRM; tổng số lần thử tối đa 6. Lần bị compile chặn không tốn lượt CRM.

## 6. Vấn đề mở

1. **"Khách được hỗ trợ" của phiếu** (r1): `customer_organization_id` hay `product_item_id.customer_id`
   (chủ hiện tại của máy)? Cần Toma/CRM chốt.
2. **Username tự suy** từ tên hoặc từ câu trả lời trước. Nên có luật trong guide: username chỉ lấy
   nguyên văn từ kết quả tool.
3. B2: còn tra id trước khi lọc (q7, q12 1/3).
4. Câu trả lời khi chạm giới hạn nói "thử lại sau" và không nêu phần đã có.
5. Đề nghị CRM sửa mô tả cột `is_current` ("Count current workload with is_current = true") thêm
   điều kiện "khi không có kỳ".
6. Đặt `AGENT_MODEL=gpt-4.1-mini` ở môi trường chạy thật. Chi phí LLM mỗi câu khoảng 2,5 lần
   gpt-4o-mini; token giảm 30% bù một phần.
