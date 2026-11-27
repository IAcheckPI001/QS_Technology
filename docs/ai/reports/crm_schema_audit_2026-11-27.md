# Kiểm duyệt schema CRM của `crm_schema`/`crm_query` (2026-11-27)

Phạm vi: chất lượng thông tin bảng, cột, khóa ngoại mà agent nhận được. Đo trên schema sống của CRM dev
(`GET /reports/datasets` + `GET /reports/tables/{t}` cho 116 bảng truy vấn được), đối chiếu index tĩnh
`reporting/raw/schema_index.py` (126 bảng) và `hints.py`. Chỉ đọc schema, không gọi `/reports/query`, không có
dòng dữ liệu. Token của Toma dùng một lần qua biến môi trường tạm, không lưu. Kết quả thô (`live.json`) và script
nằm ở thư mục scratchpad của phiên, không commit; số liệu cần thiết đã chép vào đây.

## 1. Số đo

| Chỉ số | Kết quả |
|---|---|
| Mô tả bảng | 116/116 bảng truy vấn được (142 mô tả; 26 thuộc bảng bị chặn/không mở) |
| Mô tả cột (bỏ `id`, `created_at`, `updated_at`) | 926/927 |
| Độ dài mô tả cột | trung vị 50, p90 104, tối đa 285 ký tự; 14 mô tả > 160 ký tự |
| Khóa ngoại sống / tĩnh | 276 / 253 (133 tuỳ chọn, 7 loại 1-1) |
| `deleted_at_meaning` | 12 bảng `deleted`, 3 bảng `ended`, 101 không có |
| Bảng có bảng con (`referenced_by`) | 47; vượt trần 12 mục: `auth_users` (109), `customers`, `materials`, `organizations`, `product_items`, `warehouses` |
| Bảng lệch index tĩnh | 21: 2 chỉ vì CRM ẩn cột bí mật (`password_hash`, `secret_hash`), 19 lệch thật |
| Cột `*_id`/`*_by` không có khóa ngoại | 45 cột ở 33 bảng; 12 mô tả nói "no foreign key"/"polymorphic"; chỉ 6 nêu đúng tên bảng đích |
| Ghi chú nghiệp vụ trong code (`TABLE_NOTES`) | 13/116 bảng truy vấn được; 93 bảng có khóa ngoại mà chưa có ghi chú |

Index tĩnh 126 bảng: 116 truy vấn được, 10 bị chặn/không mở (phiên, mã xác thực, cấu hình), đều ngoài 9 nhóm
trong `TABLE_GROUPS`.

## 2. Đánh giá

1. **Mô tả của CRM đã đầy đủ.** Mô tả nêu nullable, nghĩa trạng thái, chu kỳ sống và cả cột không có khóa ngoại.
   Phần thiếu là tên bảng đích: "User who…" ngầm hiểu `auth_users`; mơ hồ thật là `customer_id` của
   `support_waiting_messages` và `product_item_recall_requests` (khách hay tài khoản?), `support_cases.document_id`,
   `customer_logs.target_id`, `iot_devices.device_id`. Đây là loại LC-5.
2. **Cột người không có khóa ngoại không dùng được với `person_filter`.** `crm_schema.describe_table` chỉ đưa vào
   `person_filter` các cột có quan hệ sống tới `auth_users`, nên `created_by`/`handled_by`/`assigned_by` của
   `support_waiting_messages` không được hướng dẫn lọc theo username/tên; chỉ lọc được bằng UUID. Suy từ đọc
   code, chưa thử bằng query thật.
3. **Lệch index tĩnh chỉ ảnh hưởng quan hệ của bảng đích join chưa cache.** `crm_query.known_columns` chỉ dùng schema
   sống đã cache và trả `None` (không kiểm) khi bảng chưa cache, nên không chặn nhầm cột. Nhưng `relation_target`
   rơi về index tĩnh khi bảng chưa cache, và `crm_query` chỉ tải trước schema của bảng gốc: khóa ngoại mới ở
   bảng đích (ví dụ `goods_receipts.supplier_id`, `purchase_orders.org_id`, `materials.category_id`) có thể bị
   `check_path` báo lỗi nhầm, khóa ngoại đã bỏ (`manufacturing_work_orders.task_id`) có thể lọt qua. Suy từ đọc code,
   chưa tái hiện bằng query thật; các bảng lệch đều ở Mua hàng/kho và Sản xuất, ít nằm trong câu hỏi CRM thường gặp.
4. **`crm_schema` cắt bớt thông tin tốt:** mô tả cột cắt ở 160 ký tự (`MAX_COLUMN_NOTE_CHARS`), `referenced_by` cắt ở 12.

## 3. Kế hoạch 4 mục (đề xuất, chờ Toma duyệt; chưa làm)

### SCH-1 · Quan hệ của bảng đích join không còn đi theo index tĩnh lệch (đã làm 2026-11-27, xem LOG)
- Mục tiêu: `check_path` đúng với schema sống cho cả bảng gốc lẫn bảng đi qua trong đường dẫn.
- Phương án khuyến nghị: trong `crm_query.run`, khi lần biên dịch đầu (`compile_now(None)`, trước mọi lần gọi CRM) báo
  lỗi đường dẫn/khóa ngoại, tải schema sống của các bảng dọc đường dẫn (đi từng đoạn: tải bảng hiện tại, lấy bảng
  đích từ quan hệ sống, tối đa vài bảng, qua `cache.table`) rồi biên dịch lại một lần; lỗi tải thì giữ lỗi cũ. Cache
  dùng chung nên chi phí chỉ ở lần đầu mỗi bảng. (Đính chính 2026-11-27: bản đầu đặt bước tải sau `compile_now(None)`
  nên không cứu được lỗi khóa ngoại mới, vì lỗi đó nổ ngay ở lần biên dịch đầu.)
- Phương án phụ: sinh lại `schema_index.py`. Chỉ làm khi có dump schema mới từ CRM (`build_crm_schema_index.py` đọc
  `database-structure.sql`; dump hiện tại cũ). Có thể mở rộng script nhận `live.json` làm nguồn, nhưng đó là thay
  đổi script, cần duyệt riêng.
- File: `tools/crm_query.py` (`relation_target`, tải trước), có thể `reporting/raw/schema.py`; test mới trong
  `tests/chatbot/test_crm_query_tool.py` với fake client: bảng đích có khóa ngoại mới chỉ có ở schema sống thì query qua
  được; khóa ngoại đã bỏ thì bị chặn.
- Chấp nhận khi: test trên đạt; `pytest tests\chatbot` không thêm lỗi; thử lại 2–3 câu qua bảng lệch trên CRM thật.
- Rủi ro: thêm một vòng gọi CRM ở lượt đầu; giảm bằng gọi song song và bỏ qua lỗi.

### SCH-2 · Hint "bảng đích" cho cột không có khóa ngoại
- Mục tiêu: LLM biết cột `*_id` không khóa ngoại trỏ đâu và dùng thế nào.
- Việc: thêm vào `TABLE_NOTES` (`reporting/raw/hints.py`) các câu ngắn cho: `support_waiting_messages`
  (`customer_id`, `created_by`, `handled_by`, `assigned_by`: kiểu của UUID, lọc bằng UUID lấy từ `user_profiles`),
  `product_item_recall_requests` (`customer_id`, `*_by`), `support_cases.document_id`, `customer_logs.target_id`
  (cùng LC-5). Thêm quy tắc chung vào guide `crm_query`: cột người không có khóa ngoại không join được, lọc bằng UUID.
- Bắt buộc xác nhận trước với Toma/CRM: `customer_id` của hai bảng trên trỏ `customers.id` hay `auth_users.id`
  (hiện chưa chắc; không tự đoán). Đổi `hints.py` là đổi chính sách hướng dẫn dữ liệu, cần người duyệt (rule flow).
- Test: `test_crm_schema_tool.py` kiểm note có trong output; eval lại 1–2 câu LC-5/LC-6 sau khi có xác nhận.

### SCH-3 · Giảm cắt thông tin trong `crm_schema` (đã làm 2026-11-27: trần 300, +~100 token cho cả 116 bảng; xem LOG)
- Việc: `MAX_COLUMN_NOTE_CHARS` 160 → 300 (mô tả dài nhất 285) hoặc cắt theo câu; chỉ ảnh hưởng 14 mô tả.
  `MAX_REFERENCED_BY` giữ 12, bổ sung cho `auth_users` (109 bảng con) một dòng chỉ dẫn "nhiều bảng con; lấy bảng
  con làm bảng gốc" nếu `note` hiện tại chưa nói.
- Chi phí: tăng token output của `crm_schema` (mỗi mô tả dài thêm ≤ 140 ký tự; đo bằng `crm_schema` thật). Ảnh hưởng
  trần `AGENT_TURN_INPUT_BUDGET` (30000 ở môi trường kiểm thử): kiểm lại một lượt 3 bước.
- File: `tools/crm_schema.py`; test `test_crm_schema_tool.py` cập nhật ngưỡng.

### SCH-4 · Đính chính tài liệu
- Sửa "13 bảng lệch" thành "21 bảng (19 lệch thật), đo 2026-11-27" ở `STATE.md` và
  `flows/crm-agent/crm-reporting-api-requests.md` (mục "Dump schema mới"). Làm trong cùng đợt ghi này.

### Thứ tự và phụ thuộc
SCH-4 xong ngay. SCH-1 độc lập, làm trước (sửa code, ít cần quyết định). SCH-2 chờ câu trả lời của Toma/CRM về
`customer_id`. SCH-3 sau khi đo token. Dump schema mới từ CRM giúp SCH-1 phương án phụ nhưng không chặn phương án chính.

## 4. Chưa đo / giới hạn

- Số dòng dữ liệu, chất lượng dữ liệu thật, hiệu năng query: không nằm trong phạm vi (chỉ đọc schema).
- Sơ đồ tương tác (Artifact, 126 bảng, 9 nhóm) dựng từ index tĩnh trước khi có số đo live; chưa cập nhật số live.
- Mới đo CRM dev; CRM production có thể khác.
