# Đề nghị bổ sung cho CRM Reporting API (phục vụ chatbot AI)

- Người gửi: nhóm AI Agent (QS Technology)
- Ngày đo: 2026-11-11, trên môi trường CRM đang chạy, bằng tài khoản nhân viên thật
- API liên quan: `GET /api/v1/reports/datasets`, `GET /api/v1/reports/tables/{table}`, `POST /api/v1/reports/query`

## 1. Bối cảnh

Chatbot AI trả lời câu hỏi của nhân viên bằng cách để mô hình ngôn ngữ (LLM) tự dựng query cho `POST /reports/query`. Thông tin duy nhất LLM có về một bảng là kết quả của `GET /reports/tables/{table}`: tên cột, kiểu cột và quan hệ khoá ngoại.

Chúng tôi đã gọi `/reports/tables/{table}` cho 118 bảng và `/reports/datasets` (124 dataset). Kết quả đúng và đồng nhất, nhưng thiếu thông tin về nghĩa. LLM dựng được query đúng cú pháp, nhưng dễ chọn nhầm cột hoặc điền sai giá trị, và query sai kiểu này vẫn chạy được nên không ai phát hiện.

Tài liệu này liệt kê những gì cần CRM bổ sung hoặc xác nhận. Mục 2 là các câu hỏi cần trả lời. Mục 3 là dữ liệu cần bổ sung. Mục 4 là đề xuất định dạng. Các danh sách chi tiết nằm ở phụ lục.

## 2. Câu hỏi cần CRM xác nhận

Các câu này không cần sửa code, chỉ cần câu trả lời. Chúng tôi đang phải giả định, và giả định sai thì số liệu chatbot trả ra sẽ lệch.

| # | Câu hỏi | Vì sao cần |
|---|---|---|
| Q1 | Với 15 bảng có `deleted_at` (phụ lục D), `/reports/query` có tự loại bản ghi đã xoá không? Chúng tôi biết dataset `customers` có tự loại. Các bảng khác thì chưa rõ: đếm thử 8 bảng đều ra 0 dòng có `deleted_at`, nên không phân biệt được "CRM tự lọc" với "chưa có dữ liệu xoá". | Nếu CRM không tự lọc, mọi số đếm của chatbot sẽ tính cả bản ghi đã xoá. |
| Q2 | Cột `timestamp without time zone` lưu giờ Việt Nam hay UTC? Bốn bảng `customers`, `support_cases`, `support_assignments`, `support_messages` có lẫn cả hai kiểu `with` và `without time zone`. `date_range` so sánh theo múi giờ nào? | Câu hỏi "hôm nay", "tháng này" lệch tới 7 giờ ở biên kỳ. |
| Q3 | Khách hàng của một phiếu hỗ trợ có đúng là `support_cases.product_item_id → product_items.customer_id` không? Phiếu không gắn thiết bị thì lấy khách từ đâu? | Dùng cho câu "nhân viên X hỗ trợ bao nhiêu khách". |
| Q4 | "Sản phẩm bán được" có đúng là bản ghi `product_ownerships` với `transferred_from_ownership_id` rỗng, ngày bán là `created_at` không? Có bảng đơn bán hàng nào khác không? | Dùng cho câu hỏi doanh số theo sản phẩm. |
| Q5 | "Model máy" là `products.name`, `products.code` hay `products.model_number`? | Nhân viên hỏi theo tên model. |
| Q6 | Toán tử `contains` hiện không phân biệt hoa thường nhưng phân biệt dấu tiếng Việt ("nguyen" ra 7 khách, "nguyễn" ra 47). Đây là chủ ý hay có thể hỗ trợ tìm không dấu? | Nhân viên thường gõ không dấu và nhận 0 kết quả. |
| Q7 | Mọi bảng ngoài `customers` đang cần quyền `auth.manage_roles`. Có kế hoạch phân quyền theo từng nhóm bảng (hỗ trợ, kho, mua hàng…) không? | Nhân viên kinh doanh thường hiện nhận 403 với hầu hết câu hỏi. |
| Q8 | `/reports/datasets` của `customers` chỉ liệt kê 11 dimension, nhưng query với dimension `full_name` hoặc `created_at_month` vẫn trả HTTP 200. Danh sách trong `/datasets` có phải là giới hạn chính thức không? | Chúng tôi cần biết nên tin `/datasets` hay `/tables`. |
| Q9 | Token đăng nhập của nhân viên có cách làm mới (refresh) cho dịch vụ AI không? | Phiên chat dài bị lỗi xác thực giữa chừng. |

## 3. Dữ liệu cần CRM bổ sung

Xếp theo mức ảnh hưởng tới độ chính xác của chatbot, cao nhất ở trên.

### 3.1. Giá trị hợp lệ của cột trạng thái và phân loại (ưu tiên cao)

46 cột kiểu chuỗi mang nghĩa trạng thái/loại nhưng không có danh sách giá trị (phụ lục A). Ví dụ: `product_items.status`, `work_orders.status`, `support_cases.priority`.

LLM phải đoán giá trị để lọc. Đoán sai (ví dụ `done` thay vì `resolved`) thì query vẫn hợp lệ và trả 0 dòng, chatbot báo "không có dữ liệu".

Đề nghị: với mỗi cột trong phụ lục A, cung cấp danh sách giá trị hợp lệ kèm nghĩa ngắn của từng giá trị. Cột nào là văn bản tự do thì ghi rõ "tự do".

### 3.2. Nghĩa của các khoá ngoại cùng trỏ tới một bảng (ưu tiên cao)

26 bảng có từ 2 khoá ngoại trở lên trỏ tới cùng một bảng đích (phụ lục B). Ví dụ `support_assignments` có `assigned_to` và `assigned_by` cùng trỏ tới `auth_users`.

LLM chọn nhầm cột thì query vẫn chạy và ra số sai nghĩa. Phần lớn tên cột tự giải thích được, nhưng một số thì không: `customers.organization_id` so với `self_of_organization_id`, `stock_movements.warehouse_id` so với `related_warehouse_id`, `company_doc_nodes.parent_id` so với `root_id`.

Đề nghị: một dòng mô tả cho mỗi khoá ngoại trong phụ lục B.

### 3.3. Cột UUID tham chiếu bảng khác nhưng không có trong `relations` (ưu tiên trung bình)

43 cột kiểu `uuid` (không phải `id`) không xuất hiện trong `relations` nên không join được (phụ lục C). Chúng chia hai nhóm:

- **Nhóm 1, có vẻ là khoá ngoại thật nhưng thiếu ràng buộc trong DB** (32 cột). Ví dụ `support_waiting_messages.assigned_to`, `product_item_recall_requests.customer_id`, `manufacturing_work_orders.product_item_id`. Đề nghị: xác nhận bảng đích và thêm vào `relations`.
- **Nhóm 2, tham chiếu đa hình** (11 cột), bảng đích phụ thuộc một cột loại đi kèm. Ví dụ `activities.activityable_id` đi với `activityable_type`. Đề nghị: cho biết cột loại tương ứng và mỗi giá trị loại ứng với bảng nào.

### 3.4. Mô tả nghiệp vụ của bảng và cột (ưu tiên trung bình)

Cả hai API không có mô tả. 97/118 bảng chúng tôi chưa tự viết được ghi chú vì không đủ hiểu nghiệp vụ.

Đề nghị, theo thứ tự cần trước:
1. Một câu mô tả cho mỗi bảng: bảng lưu gì, mỗi dòng là gì.
2. Phân biệt các cặp bảng dễ nhầm:
   - `work_orders` và `manufacturing_work_orders`
   - `goods_receipts` và `po_goods_receipts` và `finished_goods_receipts`
   - `customers`, `leads` và `students`
   - `auth_users`, `sales_users` và `user_profiles`
   - `company_doc_nodes` và `manualhub_documents`
3. Mô tả cho các cột tên không tự giải thích được. Chúng tôi sẽ gửi danh sách cụ thể sau khi có mục 1.

### 3.5. Thông tin cấu trúc còn thiếu trong `/reports/tables/{table}` (ưu tiên thấp)

| Thiếu | Hậu quả |
|---|---|
| Cột có cho phép null không | LLM không biết khi nào cần lọc `is_null`/`not_null` |
| Quan hệ ngược (cha → con) | Không hỏi được "khách này có những phiếu nào" từ bảng `customers`; phải biết trước bảng con |
| Kiểu thật của cột `ARRAY` và `USER-DEFINED` | 2 cột `connection_types` (ARRAY) và `roles.data_scope` (USER-DEFINED) không rõ kiểu phần tử, không rõ lọc bằng toán tử nào |
| Cột `jsonb` có lọc/chọn được không | 14 cột `jsonb`; chưa rõ `select` trả gì và `contains` có chạy không |

### 3.6. Thay đổi schema chưa được thông báo

File `database-structure.sql` chúng tôi đang giữ đã cũ so với CRM đang chạy:

- 4 bảng mới: `issue_types`, `item_categories`, `material_uoms`, `receipt_types`.
- Cột mới ở 7 bảng:
  - `goods_issue_items`: `uom`, `uom_factor`, `uom_qty`
  - `goods_issues`: `issue_type_id`, `reason`
  - `goods_receipt_items`: `uom`, `uom_factor`, `uom_price`, `uom_qty`
  - `goods_receipts`: `reason`, `receipt_type_id`
  - `materials`: `category_id`, `product_id`
  - `purchase_order_items`: `uom`, `uom_factor`, `uom_price`, `uom_qty`
  - `purchase_requisition_items`: `uom`, `uom_factor`, `uom_qty`

Đề nghị: gửi bản dump schema mới, và thống nhất cách báo khi schema đổi (ví dụ gửi lại dump sau mỗi lần migrate).

## 4. Đề xuất định dạng

Cách ít tốn công nhất cho hai bên là thêm các trường tuỳ chọn vào `GET /reports/tables/{table}`. Các trường hiện có giữ nguyên nên không ảnh hưởng client khác.

```json
{
  "table": "support_assignments",
  "description": "Mỗi dòng là một lần giao phiếu hỗ trợ cho người xử lý",
  "soft_delete": "none",
  "columns": [
    {"name": "is_current", "type": "boolean", "nullable": false,
     "description": "Lần giao đang có hiệu lực"},
    {"name": "status", "type": "character varying", "nullable": false,
     "enum": [{"value": "pending", "label": "Chờ nhận"}, {"value": "accepted", "label": "Đã nhận"}]}
  ],
  "relations": [
    {"name": "assigned_to", "table": "auth_users", "description": "Người được giao xử lý"},
    {"name": "assigned_by", "table": "auth_users", "description": "Người thực hiện việc giao"}
  ]
}
```

`soft_delete` nhận một trong ba giá trị: `none` (bảng không có xoá mềm), `auto_filtered` (API tự loại bản ghi đã xoá), `manual` (client phải tự lọc `deleted_at`).

Nếu chưa sửa API được, một file bảng tính hoặc Markdown trả lời các phụ lục dưới đây cũng đủ để chúng tôi nhập tay.

## Phụ lục A. Cột cần danh sách giá trị hợp lệ (46 cột)

| Bảng | Cột |
|---|---|
| `campaigns` | `channel_type` |
| `company_doc_node_versions` | `document_type` |
| `company_doc_nodes` | `document_type`, `manualhub_document_type`, `pre_delete_status`, `pdf_cache_source` |
| `customer_logs` | `target_type` |
| `customers` | `source` |
| `file_links` | `entity_type` |
| `issue_reports` | `category`, `status` |
| `lock_requests` | `status` |
| `manualhub_documents` | `document_type`, `status` |
| `notifications` | `type` |
| `organizations` | `status` |
| `product_agents` | `agent_role` |
| `product_item_logs` | `event_type`, `actor_role`, `source` |
| `product_item_recall_requests` | `status` |
| `product_items` | `status` |
| `product_user_access` | `access_role` |
| `rbac_audit_logs` | `action_type` |
| `roles` | `kind` |
| `sales_users` | `status` |
| `service_logs` | `service_type`, `event_type` |
| `students` | `status` |
| `support_appointments` | `status` |
| `support_cancel_requests` | `status`, `kind` |
| `support_case_events` | `event_type` |
| `support_cases` | `category`, `priority`, `status` |
| `support_entitlement_transactions` | `type`, `kind` |
| `support_messages` | `type`, `translated_source` |
| `support_time_entries` | `source` |
| `support_waiting_message_events` | `type` |
| `support_waiting_messages` | `status` |
| `work_orders` | `type`, `priority`, `status` |

Riêng `support_cases.status`, chúng tôi đang dùng: `new`, `pending`, `in_progress`, `resolved`, `closed`, `rejected`, `cancelled`, `reopened`. Nhờ xác nhận danh sách này đủ và đúng.

## Phụ lục B. Khoá ngoại cùng trỏ tới một bảng đích (26 trường hợp)

| Bảng | Bảng đích | Các cột khoá ngoại |
|---|---|---|
| `campaigns` | `auth_users` | `assigned_person_id`, `created_by` |
| `chat_conversations` | `auth_users` | `created_by`, `owner_id` |
| `chat_messages` | `auth_users` | `pinned_by`, `sender_id` |
| `company_doc_nodes` | `company_doc_nodes` | `parent_id`, `root_id` |
| `customer_team_members` | `auth_users` | `auth_user_id`, `created_by` |
| `customers` | `auth_users` | `assigned_sales_id`, `created_by` |
| `customers` | `organizations` | `organization_id`, `self_of_organization_id` |
| `goods_issues` | `auth_users` | `created_by`, `decided_by` |
| `goods_receipts` | `auth_users` | `created_by`, `decided_by` |
| `issue_reports` | `auth_users` | `reporter_id`, `reviewed_by` |
| `lock_requests` | `auth_users` | `approved_by`, `requester_id` |
| `manualhub_documents` | `manualhub_documents` | `parent_id`, `root_id` |
| `product_item_activation_requests` | `auth_users` | `reviewed_by`, `sales_user_id` |
| `product_item_return_requests` | `auth_users` | `requested_by`, `reviewed_by` |
| `product_ownership_transfer_requests` | `auth_users` | `requested_by`, `reviewed_by` |
| `product_ownership_transfer_requests` | `customers` | `from_customer_id`, `to_customer_id` |
| `product_user_access` | `auth_users` | `auth_user_id`, `invited_by` |
| `purchase_requisitions` | `auth_users` | `approved_by`, `requested_by` |
| `rbac_audit_logs` | `auth_users` | `performed_by`, `target_user_id` |
| `stock_movements` | `warehouses` | `related_warehouse_id`, `warehouse_id` |
| `support_appointments` | `auth_users` | `customer_user_id`, `support_user_id` |
| `support_assignments` | `auth_users` | `assigned_by`, `assigned_to` |
| `support_cancel_requests` | `auth_users` | `requested_by`, `reviewed_by` |
| `support_waiting_message_helpers` | `auth_users` | `added_by`, `user_id` |
| `user_permissions` | `auth_users` | `granted_by`, `user_id` |
| `work_orders` | `auth_users` | `assigned_to`, `created_by` |

## Phụ lục C. Cột UUID không có trong `relations` (43 cột)

### C.1. Có vẻ là khoá ngoại thật (32 cột): cần xác nhận bảng đích và thêm vào `relations`

| Bảng | Cột | Bảng đích chúng tôi đoán |
|---|---|---|
| `bom_components` | `component_id` | `materials`? |
| `company_doc_nodes` | `document_group_id` | ? |
| `finished_goods_receipt_items` | `product_item_id` | `product_items` |
| `goods_returns` | `goods_receipt_id` | `goods_receipts` |
| `manualhub_activities` | `actor_id` | `auth_users` |
| `manualhub_documents` | `author_id`, `submitted_by_id` | `auth_users` |
| `manualhub_documents` | `document_group_id` | ? |
| `manufacturing_work_orders` | `product_item_id` | `product_items` |
| `material_consumptions` | `serial_lot_id` | `material_serial_lots` |
| `material_serial_lot_consumptions` | `serial_lot_id` | `material_serial_lots` |
| `material_serial_lot_consumptions` | `output_id` | ? |
| `po_goods_receipts` | `goods_receipt_id` | `goods_receipts` |
| `product_item_recall_requests` | `customer_id` | `customers` |
| `product_item_recall_requests` | `requested_by`, `confirmed_by`, `cancelled_by` | `auth_users` |
| `project_asset_components` | `product_item_id` | `product_items` |
| `projects` | `companydoc_node_id` | `company_doc_nodes` |
| `roles_owner_scope_rollback` | `role_id`, `organization_id` | `roles`, `organizations` |
| `support_attachments` | `file_id` | `files` |
| `support_cases` | `document_id` | ? |
| `support_messages` | `recalled_by` | `auth_users` |
| `support_waiting_message_events` | `actor_id` | `auth_users` |
| `support_waiting_message_replies` | `author_id`, `recalled_by` | `auth_users` |
| `support_waiting_messages` | `created_by`, `handled_by`, `assigned_to`, `assigned_by` | `auth_users` |
| `support_waiting_messages` | `customer_id` | `customers` |

### C.2. Tham chiếu đa hình (11 cột): cần biết cột loại và bảng ứng với từng giá trị loại

| Bảng | Cột | Cột loại chúng tôi đoán |
|---|---|---|
| `activities` | `activityable_id` | `activityable_type` |
| `auth_users` | `ref_id` | ? |
| `customer_logs` | `target_id` | `target_type` |
| `file_links` | `entity_id` | `entity_type` |
| `goods_issues` | `source_id` | ? |
| `purchase_requisitions` | `source_id` | ? |
| `qc_records` | `ref_id` | ? |
| `request_comments` | `request_id` | ? |
| `stock_movements` | `source_id` | ? |
| `support_waiting_message_events` | `target_id` | ? |
| `tasks` | `source_id` | ? |

Việc chia hai nhóm là phỏng đoán theo tên cột. Cột nào chúng tôi xếp sai nhóm, nhờ CRM chỉ ra.

## Phụ lục D. Bảng có xoá mềm (15 bảng, cho câu hỏi Q1)

`campaigns`, `customers` (thêm `merged_into_id`), `files`, `leads`, `product_agents`, `product_items`, `product_ownerships`, `product_user_access`, `products`, `purchase_requisitions`, `sales_users`, `students`, `support_cases`, `work_order_comments`, `work_orders`.

## Phụ lục E. Cột kiểu đặc biệt (cho mục 3.5)

| Bảng | Cột (kiểu) |
|---|---|
| `company_doc_nodes` | `connection_types` (ARRAY) |
| `manualhub_documents` | `connection_types` (ARRAY), `content` (jsonb) |
| `roles` | `data_scope` (USER-DEFINED) |
| `customer_logs` | `changes` (jsonb) |
| `leads` | `services` (jsonb) |
| `manualhub_document_versions` | `content` (jsonb) |
| `notifications` | `params`, `data` (jsonb) |
| `product_item_logs` | `metadata` (jsonb) |
| `product_item_return_requests` | `item_ids` (jsonb) |
| `products` | `specifications` (jsonb) |
| `rbac_audit_logs` | `metadata` (jsonb) |
| `service_logs` | `parts_replaced`, `event_metadata` (jsonb) |
