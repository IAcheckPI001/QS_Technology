# Hướng dẫn cho AI: đọc dữ liệu QS-CRM (chỉ đọc)

Tài liệu này dùng làm **ngữ cảnh / system prompt** cho AI agent. Nó giúp AI biết: dữ liệu nằm ở bảng nào, các bảng nối với nhau ra sao, và với một câu hỏi thì gọi **API GET nào, truyền tham số gì, theo thứ tự nào**.

- Cách xác thực và tool wrapper: xem `docs/ai-tools.md` (`GET /ai/tools`, `POST /ai/tools/{name}`).
- Base URL: `/api/v1`. Mọi request đều mang JWT của **người đang hỏi**, nên kết quả đã được lọc theo quyền và data scope của người đó.
- **Chỉ dùng GET.** Không bao giờ gọi POST/PUT/PATCH/DELETE vào API nghiệp vụ.
- Cột **Tool** = đã có tool AI tương ứng. Ô trống = route có sẵn nhưng chưa bọc thành tool.

---

## Mục lục

- [1. Quy tắc cho AI](#1-quy-tắc-cho-ai)
- [2. Cấu trúc database](#2-cấu-trúc-database)
  - [2.1 Sơ đồ quan hệ](#21-sơ-đồ-quan-hệ)
  - [2.2 Các điểm then chốt](#22-các-điểm-then-chốt)
  - [2.3 Giá trị enum](#23-giá-trị-enum)
- [3. Chi tiết từng API GET](#3-chi-tiết-từng-api-get)
  - [3.1 Khách hàng (CRM)](#31-khách-hàng-crm) — 24 API
  - [3.2 Nhân viên, tổ chức, sản phẩm và máy](#32-nhân-viên-tổ-chức-sản-phẩm-và-máy) — 31 API
  - [3.3 Hỗ trợ 1:1 và hộp thư chờ](#33-hỗ-trợ-11-và-hộp-thư-chờ) — 30 API
  - [3.4 Kỹ thuật, tài liệu và AI tools](#34-kỹ-thuật-tài-liệu-và-ai-tools) — 23 API
- [4. Từ câu hỏi đến API](#4-từ-câu-hỏi-đến-api)
- [5. Ví dụ chuỗi gọi đầy đủ](#5-ví-dụ-chuỗi-gọi-đầy-đủ)

**Tổng: 108 API GET.**

---

## 1. Quy tắc cho AI

1. **Không đoán id.** Mọi `*_id` phải lấy từ kết quả của một lần gọi trước đó. Ví dụ: tên khách → `GET /customers?keyword=` → `id`.
2. **Tìm 1 khách:** ưu tiên SĐT, sau đó là tên. Nếu `total > 1` thì liệt kê ra (tên, công ty, mã) và hỏi lại người dùng.
3. **Câu hỏi "bao nhiêu":** gọi với `limit=1` rồi đọc `total`.
4. **Ngày tháng:** dùng `YYYY-MM-DD`. Riêng lịch hẹn dùng RFC3339.
5. **Trạng thái nhiều giá trị:** ngăn cách bằng dấu phẩy (`status=new,pending`), với các API có ghi chú hỗ trợ.
6. **Gặp `403` hoặc `404`:** báo người dùng là "không có quyền xem / không tìm thấy trong phạm vi của bạn". Không thử đường vòng.
7. **Tên người:** ưu tiên các trường `*_name` mà API đã trả sẵn (`assignee_name`, `sales_name`, `assigned_to_name`, `actor_name`). Chỉ khi chỉ có id mới tra `GET /users`.
8. **Phân biệt "sản phẩm":** `products` là *loại/model máy*, còn `product_items` là *từng máy có serial* mà khách sở hữu.
9. **Phân biệt "người phụ trách":**
   - Sale phụ trách khách: `customers.assigned_sales_id`.
   - Người hỗ trợ kỹ thuật: `support_assignments.assigned_to`.
   - Kỹ thuật viên: `service_logs.technician_id`.

---

## 2. Cấu trúc database

### 2.1 Sơ đồ quan hệ
```
organizations (cây: parent_id, path, agent_type)        ← QS + chi nhánh + đại lý
   │ organization_id
   ▼
customers ──assigned_sales_id──► auth_users ──► user_profiles (first_name, last_name)
   │  status_id ──► customer_statuses ──status_group_id──► customer_status_groups
   │  ◄── activities (activityable_type='customer', activityable_id, sales_id)  lịch sử chăm sóc
   │  ◄── customer_logs                                                         log thay đổi
   │  ◄── customer_customer_groups ──► customer_groups
   │  ◄── customer_business_fields ──► business_fields
   │
   │ customer_id (chủ hiện tại)     ◄── product_ownerships (owner_customer_id, is_current)  lịch sử chủ
   ▼
product_items (code = serial, status) ──product_id──► products (code, name, category, warranty_months)
   │
   ├── product_agents (agent_organization_id, agent_role)        đại lý quản lý / hỗ trợ máy
   ├── product_user_access                                         tài khoản portal được xem máy
   ├── product_item_logs                                           lịch sử vòng đời máy
   ├── support_entitlements (included_minutes, used_minutes)       quỹ Thời Gian Hỗ Trợ, 1 dòng / máy
   │      └── support_entitlement_transactions
   │
   ├── support_cases  ← "PHIẾU HỖ TRỢ 1:1" (case_number, status, priority, category, subject)
   │      ├── support_assignments  (assigned_to, support_organization_id, is_current, accepted_at)
   │      ├── support_case_events  (event_type, actor_id, old/new_value)
   │      ├── support_messages     (sender_id, type, body)
   │      ├── support_appointments (support_user_id, customer_user_id, start_at_utc, status)
   │      ├── support_time_entries (duration_minutes)
   │      ├── support_ratings      (score, resolution, comment)
   │      └── support_cancel_requests
   │
   ├── support_waiting_messages  ← "HỘP THƯ CHỜ" (customer_id, assigned_to, handled_by, status)
   │      └── *_replies, *_events, *_helpers
   ├── service_logs  (technician_id, service_type, action_taken, work_order_id)
   ├── issue_reports (reporter_id, category, severity, status, converted_case_id → support_cases)
   ├── lock_requests
   └── product_item_activation_requests / _recall_requests / _return_requests,
       product_ownership_transfer_requests

leads ──source_campaign_id──► campaigns ◄── campaign_registrations
students, contact_messages, manualhub_documents, company_doc_nodes   (không gắn với khách)
```

### 2.2 Các điểm then chốt
- **Khách không nối thẳng tới phiếu hỗ trợ.** Đường đi là `customers.id → product_items.customer_id → support_cases.product_item_id`. Kết quả của `/support/cases` đã có sẵn `customer_id` và `customer_name`.
- **Mọi id người dùng** (`assigned_to`, `sales_id`, `created_by`, `technician_id`, `support_user_id`…) đều là `auth_users.id`.
- **Tài khoản portal của khách:** `auth_users.ref_id` = `customers.id`.
- **Xoá mềm:** các bảng có `deleted_at`. API đã tự loại bản ghi đã xoá.

### 2.3 Giá trị enum
| Trường | Giá trị |
|---|---|
| `customers.customer_type` | `lead` (tiềm năng), `student` (học viên), `official` (chính thức), `lost` |
| `product_items.status` | `stock`, `delivered`, `active`, `maintenance`, `out_of_order`, `decommissioned`, `recalled`, `refurbished` |
| `support_cases.status` | `new`, `pending`, `in_progress`, `resolved`, `closed`, `reopened`, `cancelled`, `rejected` |
| `support_cases.priority` | `low`, `normal`, `high`, `critical` |
| `support_cases.category` | `installation`, `configuration`, `alarm`, `parameter`, `firmware`, `hardware`, `documentation`, `training`, `service`, `other` |
| `support_appointments.status` | `requested`, `confirmed`, `cancelled`, `completed`, `no_show` |
| `support_waiting_messages.status` | `waiting`, `handled` |
| `support_case_events.event_type` | `status_changed`, `assigned`, `reassigned`, `unassigned`, `escalated`, `reopened`, `handed_over` |
| `service_logs.service_type` | `installation`, `maintenance`, `repair`, `inspection`, `note`, `event` |
| `issue_reports.status` / `.severity` | `open`, `reviewed`, `converted` / `normal`, `urgent` |

---


## 3. Chi tiết từng API GET

Phần này liệt kê **đầy đủ** mọi route GET chỉ-đọc, lấy trực tiếp từ `router.go`/`handler.go`/`repository.go`/`dto.go` (không phải suy đoán). Route tải file/ảnh nhị phân được bỏ qua. `(bị ẩn với AI)` nghĩa là `internal/platform/aitools/tools.go` xoá trường đó khỏi kết quả trước khi đưa cho AI.

### 3.1 Khách hàng (CRM)

**Quy ước chung cho cả nhóm**
- Prefix `/api/v1`. Mọi route đều đi qua `Authenticate`. Thiếu token hoặc token sai trả **401**.
- Có hai middleware phân quyền:
  - `Authorize(perm)`: user thiếu quyền thì trả **403** `{"error":"permission denied: <perm>"}`.
  - Nếu đủ quyền, middleware nạp vào context: `DataScope` (`SELF` / `ORGANIZATION` / `ORGANIZATION_AND_CHILDREN` / `ALL`), danh sách tổ chức được truy cập (`AccessibleOrgs`) và danh sách quyền của user.
- Response thành công trả JSON trần, **không** bọc trong `data`. Lỗi có dạng `{"error": "...", "code": "..."}`.
- `limit`/`offset` là số nguyên. Nếu giá trị không parse được thì dùng mặc định.
- Trường đánh dấu **(bị ẩn với AI)** sẽ bị wrapper `/ai/tools` cắt khỏi response (`hiddenFields` trong `internal/platform/aitools/tools.go`). Khi gọi API trực tiếp thì vẫn nhận được các trường này.

---

#### `GET /customers`
**Chức năng:** Liệt kê, tìm kiếm hoặc đếm khách hàng còn sống (`customers.deleted_at IS NULL`).
- Đọc bảng `customers`. Khi dùng bộ lọc thì join thêm `customer_customer_groups`, `customer_business_fields`, `customer_views`, `customer_statuses`, `contact_messages`, `auth_users`.
- Luôn loại bản ghi đại diện của đại lý (`self_of_organization_id IS NULL`).
- Sắp xếp mới nhất trước theo `GREATEST(created_at, assigned_at, last_inbound_at)`, nên khách vừa được giao hoặc vừa liên hệ lại sẽ nổi lên đầu.

**Quyền:** `customer.read` (`Authorize`).

**Phạm vi dữ liệu (logic trong handler):**
- `ALL`: không giới hạn tổ chức. Chỉ áp `organization_id` nếu người gọi tự truyền.
- `ORGANIZATION` / `ORGANIZATION_AND_CHILDREN`:
  - Không truyền `organization_id`: chỉ lấy khách thuộc các tổ chức được truy cập.
  - Truyền `organization_id` ngoài phạm vi: trả **400** `organization not accessible`.
  - Không có tổ chức nào được truy cập: trả 0 dòng.
- `SELF`: luôn ép `assigned_sales_id = user hiện tại`. Truyền `assigned_sales_id` của người khác thì trả **400** `cannot filter by other users with SELF scope`.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa / giá trị hợp lệ |
|---|---|---|---|---|---|
| `keyword` | query | string | không | — | Tìm `LIKE %kw%`, không phân biệt hoa thường và dấu (`unaccent(LOWER())`), trên `full_name`, `email`, `phone`, `company_name`. Nếu keyword chỉ gồm chữ số và các ký tự `space + - . ( )`, đồng thời có ≥ 9 chữ số, thì so thêm **9 số cuối** của `phone` (`0909123456` ≡ `+84 909 123 456`). **Không** tìm theo `code`. |
| `customer_type` | query | string | không | — | So khớp đúng: `lead` \| `student` \| `official` \| `lost` \| `spam`. **Bỏ trống thì tự ẩn `spam`**, và ẩn luôn `lost` trừ khi `stage=lost`. |
| `stage` | query | string | không | — | `unconverted` (lead + student), `converted` (official và trạng thái không thuộc nhóm `lost`), `lost` (trạng thái thuộc nhóm `lost` hoặc chưa có `status_group_id`, hoặc `customer_type=lost`). |
| `status_id` | query | uuid | không | — | `customers.status_id = ?`. Lấy id từ `GET /customer-statuses`. |
| `status_group_id` | query | uuid | không | — | Trạng thái của khách thuộc nhóm này **và** `customer_statuses.group` = `lost` hoặc bằng `customer_type` của khách. |
| `organization_id` | query | uuid | không | — | Lọc theo tổ chức (có kiểm tra scope như mô tả ở trên). |
| `agent_organization_id` | query | uuid | không | — | `customers.organization_id = ?`. Áp dụng độc lập với scope, dùng để xem khách của một đại lý. |
| `assigned_sales_id` | query | uuid | không | — | Khách được giao cho sale này. Với scope `SELF` thì chỉ được truyền chính mình. |
| `created_by_id` | query | uuid | không | — | `customers.created_by = ?` |
| `customer_group_id` | query | uuid | không | — | Join `customer_customer_groups`. |
| `business_field_id` | query | uuid | không | — | Join `customer_business_fields`. |
| `source_campaign_id` | query | uuid | không | — | Khách đến từ chiến dịch này. |
| `created_at_from` / `created_at_to` | query | `YYYY-MM-DD` hoặc timestamp | không | — | `created_at >= from`, `created_at <= to`. Lưu ý: `to=2026-10-31` nghĩa là **00:00 ngày 31**. Muốn lấy hết ngày 31 thì truyền `2026-11-01`. |
| `has_assigned_sales` | query | `true` | không | — | `true` = chỉ khách giao cho **chính người gọi**. `false` không có tác dụng. |
| `has_portal_access` | query | `true`/`false` | không | — | Có hoặc không có tài khoản portal đang hoạt động (`auth_users.ref_id = customers.id AND is_active`). |
| `is_new` | query | `true` | không | — | Khách người gọi **chưa mở xem** (không có dòng trong `customer_views`). Với scope tổ chức mà không có `customer.read_all` thì chỉ tính khách giao cho mình. |
| `self_arrived` | query | `true` | không | — | Khách tự tìm đến: `source` ∈ {`Website/Account`, `Website/Contact`}, hoặc có `source_campaign_id`, hoặc là `student`, hoặc vừa được giao cho người gọi. Không có `customer.read_all` thì chỉ lấy khách đã giao cho mình. |
| `exclude_pending_contact` | query | `true` | không | — | Bỏ các khách còn tin liên hệ chưa đọc. |
| `exclude_assigned_to_others` | query | `true` | không | — | Chỉ lấy khách chưa giao cho ai, hoặc giao cho chính mình (cần kèm `is_new` / `has_assigned_sales` để có user hiện tại). |
| `deleted` | query | `true` | không | — | Xem tab "Đã xóa" (`deleted_at IS NOT NULL`, sắp theo `deleted_at` giảm dần). **Chỉ có tác dụng khi user có quyền xoá khách.** |
| `limit` | query | int | không | 50 | **Tối đa 200** (repository tự cắt). |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Customer], "total": int, "limit": int, "offset": int }`. `total` là số dòng khớp bộ lọc, không phụ thuộc `limit`.

| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | `customers.id` |
| `organization_id` | uuid? | chi nhánh / đại lý sở hữu khách (`customers.organization_id`) |
| `code` | string | mã khách (`customers.code`) |
| `full_name` | string | `customers.full_name` |
| `email` | string | **(bị ẩn với AI)** |
| `phone` | string | **(bị ẩn với AI)** |
| `company_name` | string | `customers.company_name` |
| `source` | string | nguồn: `Website/Account`, `Website/Contact`, `Nhập tay`, … |
| `status_id` | uuid? | trạng thái, tra tên bằng `/customer-statuses` |
| `assigned_sales_id` | uuid? | sale phụ trách (`auth_users.id`) |
| `created_by` | uuid? | người tạo |
| `main_phone`, `main_email`, `website`, `address` | string | **(bị ẩn với AI)** |
| `gender` | string | `customers.gender` |
| `region` | string | mặc định `VN` |
| `last_contact_at` | time? | lần liên hệ gần nhất |
| `is_new` | bool? | người gọi chưa mở xem khách này |
| `new_interaction` | bool | có tương tác mới (`customer_new_interactions`) |
| `has_unread_contact` | bool | còn tin liên hệ chưa đọc |
| `group_ids` | uuid[] | **(bị ẩn với AI)** nhóm khách |
| `business_field_ids` | uuid[] | **(bị ẩn với AI)** lĩnh vực |
| `customer_type` | string | `lead` / `student` / `official` / `lost` / `spam` |
| `source_campaign_id` | uuid? | chiến dịch nguồn |
| `notes` | string | **(bị ẩn với AI)** |
| `created_at`, `updated_at`, `deleted_at` | time | |

Lưu ý: response của danh sách **không** có `organization_name` và `created_by_name`. Hai trường này chỉ có ở `GET /customers/{id}`.

**Lỗi:**
- 400 `BAD_REQUEST`: tổ chức ngoài scope, hoặc lọc sale khác khi scope là `SELF`.
- 401, 403 (thiếu `customer.read`), 500.

**Ví dụ:**
```
GET /api/v1/customers?keyword=0909123456&limit=5
→ {"items":[{"id":"1a5f…","code":"KH0012","full_name":"Nguyễn Văn An","company_name":"Cty An Phát",
   "customer_type":"official","status_id":"9c…","assigned_sales_id":"77…","created_at":"2026-09-02T…"}],
   "total":1,"limit":5,"offset":0}
```

**AI dùng khi:** "Tìm khách Nguyễn Văn An", "Tháng 10 có bao nhiêu khách mới?" (`created_at_from`/`to` + `limit=1`), "Khách của sale Minh có những ai?" (`assigned_sales_id`).

---

#### `GET /customers/{id}`
**Chức năng:** Chi tiết một khách hàng (`customers`), kèm `created_by_name` lấy từ `user_profiles` (hoặc `auth_users.username` nếu không có profile).

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:**
- Scope `ORGANIZATION*`, khách thuộc tổ chức của mình: trả đầy đủ.
- Khách thuộc tổ chức khác, nhưng tổ chức của mình là đại lý của một máy khách đang sở hữu (`product_ownerships` ⋈ `product_agents`): chỉ trả `{id, full_name, other_organization: true, organization_name}`.
- Ngoài hai trường hợp trên: **404**.
- Scope `ALL` và `SELF` **không bị chặn** ở route này. Với `SELF`, user xem được khách không giao cho mình nếu biết id.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | `customers.id` |
| `include_deleted` | query | `true` | không | — | Mở cả khách đã xoá mềm (chỉ đọc). |

**Kết quả:** một object Customer với các trường như ở `GET /customers`, cộng thêm:
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `created_by_name` | string | họ tên người tạo |
| `other_organization` | bool | `true` khi chỉ được xem bản rút gọn (khách thuộc tổ chức khác) |
| `organization_name` | string | chỉ có khi `other_organization=true` |

**Lỗi:** 404 `NOT_FOUND` (`customer not found`, gồm cả trường hợp ngoài phạm vi), 401, 403, 500.

**Ví dụ:**
```
GET /api/v1/customers/1a5fa1a5-5052-4bd5-b227-b08782e2a74f
→ {"id":"1a5f…","code":"KH0012","full_name":"Nguyễn Văn An","customer_type":"official",
   "assigned_sales_id":"77…","created_by_name":"Trần Minh","last_contact_at":"2026-10-30T…"}
```

**AI dùng khi:** "Thông tin khách An?", "Ai tạo khách này?", "Lần cuối liên hệ khách An là khi nào?"

---

#### `GET /customers/{customer_id}/activities`
**Chức năng:** Lịch sử chăm sóc (gọi điện, gặp, nhắn…) của khách, đọc từ bảng `activities` với `activityable_type='customer'`. Kèm `sales_name` và ảnh đính kèm (`files`). Sắp `created_at DESC`.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** trước khi đọc, handler gọi `CustomerInScope`, dùng cùng quy tắc `orgInScope` như `GET /customers/{id}`. Khách ngoài tổ chức của người gọi (scope `ORGANIZATION*`) trả **404**. Scope `SELF`/`ALL` không bị chặn.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `customer_id` | path | uuid | có | — | id khách |
| `limit` | query | int | không | 50 | tối đa 200 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Activity], "limit", "offset" }`. **Không có `total`.**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `activities.id` |
| `activityable_type` | string | luôn là `customer` |
| `activityable_id` | uuid | id khách |
| `sales_id` | uuid | người ghi nhận |
| `sales_name` | string | tên người ghi nhận |
| `action` | string | loại hoạt động (chuỗi tự do do FE gửi, bắt buộc có) |
| `content` | string | nội dung |
| `contact_at` | time? | thời điểm liên hệ thực tế |
| `created_at` | time | |
| `images` | `[{id, image_url, display_order, created_at}]` | **(bị ẩn với AI)** |

**Lỗi:** 404 (khách ngoài phạm vi), 401, 403, 500.

**Ví dụ:**
```
GET /api/v1/customers/1a5f…/activities?limit=3
→ {"items":[{"id":"…","action":"call","content":"Báo giá máy CNC 3020","contact_at":"2026-10-30T09:00:00Z",
   "sales_id":"77…","sales_name":"Trần Minh","created_at":"…"}],"limit":3,"offset":0}
```

**AI dùng khi:** "Lần cuối chăm sóc khách An nói gì?", "Sale nào đã gọi cho khách An?"

---

#### `GET /activities/{id}`
**Chức năng:** Một hoạt động chăm sóc (`activities`), kèm `sales_name` và ảnh.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** **không kiểm tra scope.** Ai có `customer.read` và biết id đều đọc được.

**Tham số:** `id` (path, uuid, bắt buộc).

**Kết quả:** một object Activity (các trường giống bảng ở trên).

**Lỗi:** 404 (`activity not found`), 401, 403, 500.

**Ví dụ:** `GET /api/v1/activities/5b2…` → `{"id":"5b2…","action":"meeting","content":"…","sales_name":"Trần Minh",…}`

**AI dùng khi:** cần chi tiết một hoạt động đã có id từ danh sách. Ít khi phải dùng.

---

#### `GET /customers/{id}/logs`
**Chức năng:** Nhật ký thay đổi của khách (`customer_logs`): ai làm gì, đổi trường nào từ giá trị cũ sang mới. Sắp `created_at DESC`.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** **không kiểm tra scope** trong handler.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | id khách |
| `limit` | query | int | không | 50 | tối đa 200 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "logs": [Log], "limit", "offset" }`. Lưu ý mảng nằm ở key **`logs`**, không phải `items`, và không có `total`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `actor_id` | uuid | người thực hiện |
| `actor_name` | string | tên người thực hiện |
| `actor_customer_id` | uuid? | có giá trị khi người thực hiện là chính khách (qua portal) |
| `action` | string | `customer_create`, `customer_update`, `customer_delete`, `status_change`, `assign_sales`, `grant_portal`, `revoke_portal`, `reset_portal_password`, `note_add`, `note_update`, `note_delete`, `product_add`, `product_activate`, `product_transfer`, `product_recall`, `product_refurbish`, `customer_merge`, `customer_restore` |
| `target_type` | string | loại đối tượng bị tác động |
| `target_id` | uuid? | id đối tượng |
| `changes` | `[{field, old, new}]` | các trường thay đổi |
| `created_at` | time | |

**Lỗi:** 400 (thiếu id), 500 `failed to list logs: …`, 401, 403.

**Ví dụ:**
```
GET /api/v1/customers/1a5f…/logs?limit=5
→ {"logs":[{"action":"assign_sales","actor_name":"Admin","changes":[{"field":"assigned_sales_id","old":null,"new":"77…"}],
   "created_at":"…"}],"limit":5,"offset":0}
```

**AI dùng khi:** "Khách An được giao cho sale khi nào, ai giao?", "Ai đổi trạng thái khách An?"

---

#### `GET /customers/{id}/contact-history`
**Chức năng:** Các lần khách chủ động liên hệ:
- `form`: gửi form liên hệ trên website (`contact_messages`).
- `campaign`: đăng ký qua chiến dịch (`campaign_registrations` ⋈ `campaigns`).

Sắp mới nhất trước. Một lần đăng ký chiến dịch cũng sinh ra một tin liên hệ cách đó dưới 5 giây; hai bản ghi này được gộp lại và chỉ hiện dạng `campaign`.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** scope khác `ALL` thì khách phải thuộc tổ chức được truy cập. Khách đã xoá hoặc ngoài phạm vi trả **danh sách rỗng**, không báo lỗi.

**Tham số:** `id` (path, uuid, bắt buộc). Không phân trang.

**Kết quả:** `{ "items": [ {kind, campaign_name, campaign_id, note, created_at} ] }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `kind` | string | `form` \| `campaign` |
| `campaign_name` | string | tên chiến dịch (rỗng nếu là form) |
| `campaign_id` | string | id chiến dịch (rỗng nếu là form) |
| `note` | string | nội dung tin nhắn (form) hoặc ghi chú đăng ký (campaign) |
| `created_at` | time | |

**Lỗi:** 401, 403, 500.

**Ví dụ:**
```
GET /api/v1/customers/1a5f…/contact-history
→ {"items":[{"kind":"campaign","campaign_name":"Khoá CNC T10","campaign_id":"c1…","note":"","created_at":"…"},
   {"kind":"form","campaign_name":"","campaign_id":"","note":"Cần báo giá máy laser","created_at":"…"}]}
```

**AI dùng khi:** "Khách An đã để lại lời nhắn gì trên web?", "Khách An đăng ký qua chiến dịch nào?"

---

#### `GET /customers/{id}/product-access`
**Chức năng:** Tổng hợp mọi tài khoản được cấp quyền xem/vận hành các máy của khách (`product_user_access`). Không gồm dòng chủ sở hữu (owner). Chỉ lấy tài khoản còn hoạt động và máy chưa xoá.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** `orgInScope`. Khách ngoài tổ chức (scope `ORGANIZATION*`) trả **404**.

**Tham số:** `id` (path, uuid, bắt buộc).

**Kết quả:** `{ "items": [Access] }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `product_user_access.id` |
| `product_item_id` | uuid | máy |
| `product_item_code` | string | serial máy |
| `auth_user_id` | uuid | tài khoản được cấp quyền |
| `access_role` | string | `technician` \| `operator` (hoặc role id tuỳ chỉnh) |
| `invited_by` | uuid? | người cấp quyền |
| `created_at` | time | |

**Lỗi:** 400 (tính năng chưa được wiring), 404, 401, 403, 500.

**Ví dụ:** `GET /api/v1/customers/1a5f…/product-access` → `{"items":[{"product_item_code":"QS-001","auth_user_id":"…","access_role":"technician",…}]}`

**AI dùng khi:** "Ai bên khách An được vận hành máy QS-001?"

---

#### `GET /customers/{id}/supplemental-products`
**Chức năng:** Danh sách **tất cả máy (`product_items`) đang gắn với khách** (`customer_id = id`, tối đa 1000), kèm tên sản phẩm. Đây là màn "Bổ sung sản phẩm cho KH".

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** cho qua khi thoả **một** trong các điều kiện:
- khách được giao cho chính người gọi;
- scope là `ALL`;
- `customers.organization_id` nằm trong danh sách tổ chức được truy cập.

Ngoài ra trả **403**. Khách không có tổ chức (khi scope khác `ALL`) cũng trả 403.

**Tham số:** `id` (path, uuid, bắt buộc).

**Kết quả:** `{ "items": [Item] }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `product_items.id` |
| `code` | string | serial |
| `customer_id` | uuid | |
| `product_id` | uuid? | loại máy |
| `product_name` | string | `products.name` |
| `model_name` | string | hiện đang trùng với `code` |
| `warranty_expiry` | time? | hạn bảo hành |
| `status` | string | trạng thái máy (`stock`, `delivered`, `active`…) |
| `activated_by` | uuid? | người kích hoạt |
| `activated_at` | time? | |
| `created_at` | time | |

**Lỗi:** 400 (thiếu id), 403, 404 (khách không tồn tại), 401, 500.

**Ví dụ:** `GET /api/v1/customers/1a5f…/supplemental-products` → `{"items":[{"id":"p1…","code":"QS-001","product_name":"CNC 3020","status":"active","warranty_expiry":"2027-09-01T…"}]}`

**AI dùng khi:** "Khách An có những máy nào, còn bảo hành không?" Có thể dùng thay cho `GET /product-items?customer_id=`.

---

#### `GET /customers/{id}/portal`
**Chức năng:** Cho biết khách đã có tài khoản portal hay chưa (`auth_users.ref_id = customer`).

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** **không kiểm tra scope.**

**Tham số:** `id` (path, uuid, bắt buộc).

**Kết quả:** `{ "has_access": bool, "email": string, "user_id": uuid }`. Trường `email` **(bị ẩn với AI)**.

**Lỗi:** 400 (thiếu id), 401, 403, 500.

**Ví dụ:** `GET /api/v1/customers/1a5f…/portal` → `{"has_access":true,"email":"an@…","user_id":"u9…"}`

**AI dùng khi:** "Khách An đã có tài khoản portal chưa?"

---

#### `GET /customers/tracking-stats`
**Chức năng:** Hai con số cho badge theo dõi trong **một** tổ chức:
- `total_assigned_count`: số khách trong tổ chức được giao cho chính người gọi.
- `new_count`: số khách trong tổ chức mà người gọi chưa mở xem. Với scope `SELF` thì chỉ đếm khách giao cho mình.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** scope `ORGANIZATION*` thì `organization_id` phải thuộc danh sách tổ chức được truy cập, nếu không trả **400**.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `organization_id` | query | uuid | **có** | — | tổ chức cần đếm |

**Kết quả:** `{ "new_count": int, "total_assigned_count": int }`

**Lỗi:** 400 (thiếu `organization_id` hoặc tổ chức ngoài phạm vi), 401, 403, 500.

**Ví dụ:** `GET /api/v1/customers/tracking-stats?organization_id=o1…` → `{"new_count":4,"total_assigned_count":37}`

**AI dùng khi:** "Tôi đang phụ trách bao nhiêu khách ở chi nhánh X?", "Có bao nhiêu khách mới tôi chưa xem?"

---

#### `GET /customer-statuses`
**Chức năng:** Danh mục trạng thái khách (`customer_statuses`), sắp theo `name ASC`. Dùng để đổi `status_id` thành tên trạng thái.

**Quyền:** `customer.read` (áp cho cả group route).

**Phạm vi dữ liệu:** không có (đây là cấu hình dùng chung).

**Tham số:** `limit` (mặc định 50, tối đa 200), `offset`.

**Kết quả:** `{ "items": [Status], "limit", "offset" }`. Không có `total`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `name` | string | mã trạng thái, ví dụ `NEW`, `HOT`, `APPROACHING`, `CLOSED`, `REGISTERED`, `DEPOSITED`, `WAITING_FOR_DELIVERY` |
| `description` | string | |
| `label_vi` / `label_en` | string | tên hiển thị |
| `group` | string | `lead` \| `student` \| `official` \| `lost` \| `spam`: loại khách mà trạng thái này áp dụng |
| `status_group_id` | uuid | nhóm trạng thái (tab) |
| `created_at`, `updated_at` | time | |

**Lỗi:** 401, 403, 500.

**Ví dụ:** `GET /api/v1/customer-statuses?limit=200` → `{"items":[{"id":"9c…","name":"HOT","label_vi":"Nóng","group":"lead","status_group_id":"g1…"}],…}`

**AI dùng khi:** "Khách An đang ở trạng thái gì?" (tra `status_id`), "Có bao nhiêu khách đang Nóng?" (tìm id rồi gọi `/customers?status_id=…&limit=1`).

#### `GET /customer-statuses/{id}`
**Chức năng:** Một trạng thái. **Quyền:** `customer.read`. **Tham số:** `id` (path). **Kết quả:** object Status. **Lỗi:** 404, 401, 403. **AI dùng khi:** chỉ cần tra đúng một `status_id`.

---

#### `GET /customer-status-groups`
**Chức năng:** Các nhóm trạng thái (tab phễu), đọc từ `customer_status_groups`, sắp theo `sort_order, name`.

**Quyền:** `customer.read`.

**Phạm vi dữ liệu:** không có.

**Tham số:** `limit` (mặc định 50), `offset`.

**Kết quả:** `{ "items": [Group], "limit", "offset" }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `name` | string | `UNCONVERTED`, `CONVERTED`, `STUDENT`, `LOST`, `SPAM` |
| `label_vi` / `label_en` | string | |
| `stage` | string | `lead` \| `student` \| `official` \| `lost` \| `spam` |
| `sort_order` | int | |
| `created_at`, `updated_at` | time | |

**Lỗi:** 401, 403, 500.

**Ví dụ:** `GET /api/v1/customer-status-groups` → `{"items":[{"id":"g1…","name":"UNCONVERTED","label_vi":"Chưa chốt","stage":"lead","sort_order":1}],…}`

**AI dùng khi:** "Có bao nhiêu khách đã chốt?" (lấy `id` của nhóm rồi gọi `/customers?status_group_id=…&limit=1`).

#### `GET /customer-status-groups/{id}`
**Chức năng:** Một nhóm trạng thái. **Quyền:** `customer.read`. **Tham số:** `id` (path). **Kết quả:** object Group. **Lỗi:** 404, 401, 403.

---

#### `GET /leads`
**Chức năng:** Danh sách khách tiềm năng. Thực chất đây là `customers` có `customer_type='lead'`, đọc qua `customer.Service`. Sắp xếp giống `/customers`.

**Quyền:** `lead.read`.

**Phạm vi dữ liệu:** **không áp data scope.** Lớp lead gọi `ListByOrganization("")` mà không truyền danh sách tổ chức, nên trả lead của **mọi tổ chức**.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `search` | query | string | không | — | Giống `keyword` của `/customers`: tên, email, SĐT (có so 9 số cuối), công ty; không dấu. |
| `limit` | query | int | không | 50 | tối đa 200 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Lead], "total", "limit", "offset" }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `customers.id` |
| `name` | string | `full_name` |
| `phone`, `email` | string | **(bị ẩn với AI)** |
| `business_field` | string | lĩnh vực |
| `notes` | string | **(bị ẩn với AI)** |
| `services` | string[] | dịch vụ quan tâm |
| `created_at`, `updated_at` | time | |

**Lỗi:** 400, 401, 403, 500.

**Ví dụ:** `GET /api/v1/leads?search=an&limit=10` → `{"items":[{"id":"…","name":"Lê An","services":["CNC"],"created_at":"…"}],"total":3,…}`

**AI dùng khi:** "Có bao nhiêu khách tiềm năng?", "Tìm lead tên An". Nếu cần áp phạm vi dữ liệu, nên dùng `/customers?customer_type=lead` thay thế.

#### `GET /leads/{id}`
**Chức năng:** Một lead. Trả **404** nếu khách không phải `customer_type='lead'`.

**Quyền:** `lead.read`. **Phạm vi:** không kiểm tra.

**Tham số:** `id` (path).

**Kết quả:** object Lead (trường như trên).

**Lỗi:** 404, 401, 403, 500.

---

#### `GET /contact-messages`
**Chức năng:** Hộp tin liên hệ từ form website (`contact_messages` ⋈ `customers`). Mỗi khách **chỉ một dòng**, là tin mới nhất. Sắp `created_at DESC`.
- Luôn bỏ khách đã xoá.
- Khi không lọc theo `customer_id`: bỏ khách `spam`. Với admin (có `lead.read_all`), chỉ hiện khách chưa giao cho ai hoặc giao cho chính mình.

**Quyền:** `lead.read`.

**Phạm vi dữ liệu:**
- Scope khác `ALL`: chỉ khách thuộc các tổ chức được truy cập.
- Không có quyền `lead.read_all` (sale): chỉ khách được giao cho mình.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `search` | query | string | không | — | `ILIKE` không dấu trên `contact_messages.name` và `message`; `ILIKE` thường trên `phone` |
| `customer_id` | query | uuid | không | — | chỉ tin của một khách |
| `unread` | query | `true`/`false` | không | — | `true` = chưa đọc, `false` = đã đọc. Đã đọc nghĩa là người gọi đã mở khách sau thời điểm tin đến, hoặc tin đã được xử lý (`read_at`), hoặc khách đã giao cho sale khác. |
| `limit` | query | int | không | 50 | tối đa 200 (vượt quá thì về 50) |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Msg], "total", "limit", "offset" }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `contact_messages.id` |
| `customer_id` | uuid | |
| `customer_code` | string | |
| `customer_name` | string | |
| `name` | string | tên người gửi điền trong form |
| `phone`, `email` | string | **(bị ẩn với AI)** |
| `business_field` | string | |
| `services` | string | |
| `message` | string | nội dung tin |
| `created_at` | time | |
| `read` | bool | đã đọc (theo người gọi) |

**Lỗi:** 401, 403, 500.

**Ví dụ:** `GET /api/v1/contact-messages?unread=true&limit=1` → `{"items":[…],"total":5,"limit":1,"offset":0}`

**AI dùng khi:** "Có bao nhiêu tin liên hệ chưa đọc?", "Khách An nhắn gì qua form?"

---

#### `GET /students`
**Chức năng:** Danh sách học viên, tức `customers` có `customer_type='student'`, đọc qua `customer.Service`.

**Quyền:** `student.read`.

**Phạm vi dữ liệu:** **không áp data scope** (giống `/leads`).

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `search` | query | string | không | — | giống `keyword` của `/customers` |
| `status` | query | string | không | — | `registered` (vừa đăng ký), `deposited` (đã cọc), `enrolled` (đã nhập học), `cancelled` (đã huỷ). Được map sang `customer_statuses.name` `REGISTERED` / `DEPOSITED` / `ENROLLED` / `CANCELLED`. Giá trị khác trả **400** `unknown status`. |
| `limit` | query | int | không | 50 | tối đa 200 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Student], "total", "limit", "offset" }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `customers.id` |
| `full_name` | string | |
| `phone`, `email` | string | **(bị ẩn với AI)** |
| `business_field` | string | |
| `deposit_agreed` | bool | đã đồng ý đặt cọc |
| `status` | string | `registered` / `deposited` / `enrolled` / `cancelled` |
| `notes` | string | **(bị ẩn với AI)** |
| `created_at`, `updated_at` | time | |

**Lỗi:** 400, 401, 403, 500.

**Ví dụ:** `GET /api/v1/students?status=deposited&limit=1` → `{"items":[…],"total":12,"limit":1,"offset":0}`

**AI dùng khi:** "Bao nhiêu học viên đã đặt cọc?", "Học viên An đang ở trạng thái nào?"

#### `GET /students/{id}`
**Chức năng:** Một học viên. **Quyền:** `student.read`. **Phạm vi:** không kiểm tra. **Tham số:** `id` (path). **Kết quả:** object Student. **Lỗi:** 404, 401, 403, 500.

---

#### `GET /campaigns`
**Chức năng:** Danh sách chiến dịch (`campaigns`, chưa xoá), sắp `created_at DESC`.

**Quyền:** `campaign.read`.

**Phạm vi dữ liệu:** không có (thấy mọi chiến dịch).

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `active` \| `ended` |
| `product_id` | query | uuid | không | — | chiến dịch của một sản phẩm |
| `limit` | query | int | không | 50 | (không thấy giới hạn tối đa trong code) |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ "items": [Campaign], "total", "limit", "offset" }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `name` | string | |
| `slug` | string | đường dẫn công khai `/public/campaigns/{slug}` |
| `product_id` | uuid | |
| `business_field_id` | uuid | |
| `organization_id` | uuid | |
| `assigned_person_id` | uuid | người phụ trách |
| `funnel_type` | string | `sales` \| `course` |
| `channel_type` | string | kênh |
| `status` | string | `active` \| `ended` |
| `sla_hours` | int? | |
| `note` | string | |
| `created_by` | uuid | |
| `start_at`, `end_at` | time? | |
| `created_at`, `updated_at` | time | |

**Lỗi:** 400, 401, 403, 500.

**Ví dụ:** `GET /api/v1/campaigns?status=active` → `{"items":[{"id":"c1…","name":"Khoá CNC T10","funnel_type":"course","status":"active",…}],"total":2,…}`

**AI dùng khi:** "Đang chạy những chiến dịch nào?"

#### `GET /campaigns/{id}`
**Chức năng:** Một chiến dịch. **Quyền:** `campaign.read`. **Tham số:** `id` (path). **Kết quả:** object Campaign. **Lỗi:** 404 `NOT_FOUND`, 401, 403, 500.

---

#### `GET /campaigns/{id}/stats`
**Chức năng:** Số lượt truy cập link (`campaign_visits`) và lượt đăng ký (`campaign_registrations`), tính tổng và theo ngày. Một khách đăng ký lặp lại được tính nhiều lần.

**Quyền:** `campaign.read`.

**Tham số:** `id` (path, bắt buộc).

**Kết quả:**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `total_visits` | int | tổng lượt truy cập |
| `total_registrations` | int | tổng lượt đăng ký |
| `conversion_rate` | float | đăng ký / truy cập (0 nếu chưa có lượt truy cập) |
| `series` | `[{date: "YYYY-MM-DD", visits, registrations}]` | theo ngày, tăng dần |

**Lỗi:** 404 (chiến dịch không tồn tại), 401, 403, 500.

**Ví dụ:** `GET /api/v1/campaigns/c1…/stats` → `{"total_visits":420,"total_registrations":31,"conversion_rate":0.0738,"series":[{"date":"2026-10-01","visits":40,"registrations":3}]}`

**AI dùng khi:** "Chiến dịch X hiệu quả thế nào?", "Tỷ lệ chuyển đổi của chiến dịch X?"

#### `GET /campaigns/{id}/registrants`
**Chức năng:** Các khách (còn sống) đã đăng ký qua chiến dịch, mỗi khách một dòng, kèm thời điểm đăng ký **lần đầu**. Tối đa 500 dòng, mới nhất trước.

**Quyền:** `campaign.read`. **Phạm vi:** không kiểm tra.

**Tham số:** `id` (path).

**Kết quả:** `{ "items": [ {id, code, full_name, phone, email, registered_at} ] }`. Hai trường `phone` và `email` **(bị ẩn với AI)**.

**Lỗi:** 404, 401, 403, 500.

**AI dùng khi:** "Những ai đã đăng ký chiến dịch X?"

#### `GET /campaign-qs-users`
**Chức năng:** Danh sách tài khoản đang hoạt động thuộc tổ chức QS (không phải đại lý, không có role `customer`). Dùng làm danh sách chọn người phụ trách chiến dịch.

**Quyền:** `campaign.read`.

**Tham số:** không có.

**Kết quả:** `{ "items": [ {id, full_name} ] }`, sắp theo tên.

**Lỗi:** 401, 403, 500.

**AI dùng khi:** đổi `assigned_person_id` của chiến dịch thành tên người, khi user không có quyền `user.read`.

---

#### Lưu ý bảo mật và hành vi (rút ra từ code)
- `GET /customers/{id}`, `/customers/{id}/activities` và `/customers/{id}/product-access` chỉ chặn theo tổ chức với scope `ORGANIZATION*`. Scope `SELF` **không** bị giới hạn về khách được giao khi mở theo id.
- `GET /customers/{id}/logs`, `/customers/{id}/portal` và `/activities/{id}` **không kiểm tra scope**.
- `GET /leads` và `GET /students` **không áp data scope**: trả dữ liệu của mọi tổ chức.
- Các danh sách `/customers`, `/leads`, `/students`, `/customer-statuses` bị cắt ở **200 dòng/lần**. Muốn lấy nhiều hơn thì phân trang bằng `offset`.
- `/customers/{id}/activities`, `/customers/{id}/logs`, `/customer-statuses` và `/customer-status-groups` **không trả `total`**.

### 3.2 Nhân viên, tổ chức, sản phẩm và máy

> Quy ước chung cho cả phần B:
> - Mọi route nằm dưới `/api/v1`, cần `Authorization: Bearer <JWT>`. Middleware `Authorize(...)` vừa kiểm tra quyền vừa nạp **data scope** (`SELF` / `ORGANIZATION` / `ORGANIZATION_AND_CHILDREN` / `ALL`) và danh sách tổ chức truy cập được (`AccessibleOrgs`) vào context.
> - **"Agent-only"** = người dùng chỉ có role `agent_*` (nhân viên đại lý). Nhiều handler lọc riêng cho nhóm này qua bảng `product_agents`. Nhân viên QS (`admin`, `qs_support_engineer`) không bị lọc theo kiểu đó.
> - Trường đánh dấu **(bị ẩn với AI)** sẽ bị tool wrapper `internal/platform/aitools` xoá trước khi gửi cho model (`hiddenFields`). Việc ẩn này áp dụng ở **mọi cấp lồng nhau** theo **tên trường**.
> - Lỗi có body chung là `{"error": "...", "code": "..."}`.

---

#### `GET /users`
**Chức năng:** Danh bạ **nhân viên** (không gồm tài khoản khách hàng/portal), có phân trang. Đọc từ `auth_users` JOIN `user_profiles`, kèm roles/permissions (`user_roles`, `roles`) và tổ chức (`user_organizations`) của từng người.
**Quyền:** `user.read` + `ApplyScope`. **Phạm vi dữ liệu:**
- Chỉ trả về tài khoản `is_active = true`, không phải tài khoản gắn khách (`ref_id`), và không có role `customer`.
- Scope `SELF`: chỉ thấy chính mình.
- Scope `ORGANIZATION` / `ORGANIZATION_AND_CHILDREN`: chỉ thấy user thuộc `AccessibleOrgs` (qua `user_organizations`). Nếu không có tổ chức nào thì danh sách rỗng.
- Scope `ALL`: thấy toàn bộ.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa / giá trị hợp lệ |
|---|---|---|---|---|---|
| `keyword` | query | string | không | — | `LIKE %kw%`, không phân biệt hoa thường hay dấu (`unaccent`), trên email, SĐT, họ tên (`last_name + ' ' + first_name`), username |
| `role_code` | query | string | không | — | Khớp **chính xác** `roles.code`, ví dụ `sales`, `admin`, `accountant`, `agent_admin`, `qs_support_engineer`, `production`, `factory`, `MANAGER`, `WRITER`, `R&D`, `APPLICATION` |
| `permission_code` | query | string | không | — | Chỉ lấy user có quyền này qua role, ví dụ `support_case.handle` |
| `organization_id` | query | uuid | không | — | User thuộc tổ chức này (`user_organizations.organization_id =`) |
| `account_category` | query | string | không | — | `agent` = có role `agent_*`; `qs` = có role, không phải agent, không phải customer; `owner` = có role `customer` (thực tế đã bị điều kiện nền loại ra) |
| `created_at_from` / `created_at_to` | query | date/timestamp | không | — | `auth_users.created_at >=` / `<=`, giá trị truyền thẳng vào SQL |
| `visible_org_ids` | query | csv uuid | không | — | Nếu có mặt: giữ user **không** mang role `agent_*`, cộng với user agent thuộc các org trong danh sách. Truyền rỗng nghĩa là chỉ giữ người QS |
| `limit` | query | int | không | 50 | Nhánh có scope bị giới hạn tối đa 200 |
| `offset` | query | int | không | 0 | |

Sắp xếp theo `au.created_at DESC`.
**Kết quả:** `{items: UserResponse[], limit, offset, total}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | `auth_users.id` |
| `email` | string | `auth_users.email` (bị ẩn với AI) |
| `phone` | string | `auth_users.phone` (bị ẩn với AI) |
| `first_name`, `last_name` | string | `user_profiles` |
| `full_name` | string | `last_name + ' ' + first_name` |
| `avatar_url` | string | `user_profiles.avatar_url` (bị ẩn với AI) |
| `region` | string | `auth_users.region` (mặc định `VN`) |
| `organization_id` | uuid? | tổ chức đầu tiên trong `user_organizations` |
| `roles[]` | `{id, name, code}` | `roles` |
| `permissions[]` | `{id, code, description}` | quyền thực tế (bị ẩn với AI) |
| `email_notifications` | `{activation_request, service_request}` | `auth_users.email_notify_*` (bị ẩn với AI) |
| `created_at` | timestamp | `auth_users.created_at` |

**Lỗi:** 400 `BAD_REQUEST`/`INVALID_INPUT`, 401 (thiếu hoặc sai token), 403 (thiếu `user.read`), 500 `INTERNAL_ERROR`.
**Ví dụ:** `GET /api/v1/users?role_code=sales&keyword=minh&limit=5`
```json
{"items":[{"id":"9b1…","full_name":"Trần Minh","first_name":"Minh","last_name":"Trần","region":"VN","organization_id":"a1…","roles":[{"id":"r1","name":"Sales","code":"sales"}],"created_at":"2026-05-02T08:00:00Z"}],"limit":5,"offset":0,"total":1}
```
**AI dùng khi:** "Danh sách sale?", "Id của nhân viên tên Minh?", "Ai có quyền xử lý phiếu hỗ trợ?" (`permission_code=support_case.handle`).

---

#### `GET /users/{id}`
**Chức năng:** Chi tiết 1 nhân viên. Dùng chủ yếu để đổi một `*_id` (ví dụ `assigned_to`, `created_by`) ra tên người. Đọc `auth_users` + `user_profiles` + roles/permissions + `user_organizations`.
**Quyền:** `user.read`, **hoặc** bất kỳ người nào có role `agent_*` (`AuthorizeAnyOrAgent`). **Phạm vi dữ liệu:** handler **không** lọc theo scope. Repo chỉ tìm user `is_active` và không gắn khách (`ref_id IS NULL`); ngoài điều kiện đó trả về 404.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | `auth_users.id` |

**Kết quả:** 1 `UserResponse`, cùng các trường như `GET /users`.
**Lỗi:** 404 `NOT_FOUND` "user not found", 400 `INVALID_INPUT`, 403, 500.
**Ví dụ:** `GET /api/v1/users/9b1…` → `{"id":"9b1…","full_name":"Trần Minh","roles":[…],"created_at":"…"}`
**AI dùng khi:** "Người có id X là ai?", "Nhân viên được giao phiếu này tên gì, role gì?"

---

#### `GET /users/me/colleagues`
**Chức năng:** Danh sách đồng nghiệp **cùng tổ chức** với người đang đăng nhập (trừ chính họ). Đây là danh bạ của chat nội bộ. Đọc `auth_users`, `user_profiles`, `user_organizations`.
**Quyền:** chỉ cần đăng nhập. **Phạm vi dữ liệu:** chỉ những user active (không gắn khách) có chung ít nhất 1 tổ chức với người gọi.
**Tham số:** không có. Không phân trang.
**Kết quả:** mảng thuần `[{id, full_name, email}]`, sắp theo `full_name, email`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `auth_users.id` |
| `full_name` | string | họ + tên (`user_profiles`) |
| `email` | string | `auth_users.email` (bị ẩn với AI) |

**Lỗi:** 401, 500.
**Ví dụ:** `GET /api/v1/users/me/colleagues` → `[{"id":"…","full_name":"Lê C"}]`
**AI dùng khi:** "Đồng nghiệp cùng chi nhánh với tôi là ai?" Route này hữu ích khi người hỏi không có quyền `user.read`.

---

#### `GET /users/{id}/profile`
**Chức năng:** Hồ sơ (họ, tên, avatar, vùng) của 1 user, đọc từ `user_profiles` và lấy `region` từ `auth_users`.
**Quyền:** `user.read`. **Phạm vi dữ liệu:** không lọc theo scope.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | `auth_users.id` |

**Kết quả:** `ProfileResponse`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `user_profiles.id` |
| `user_id` | uuid | `user_profiles.user_id` |
| `first_name`, `last_name` | string | `user_profiles` |
| `avatar_url` | string | (bị ẩn với AI) |
| `region` | string | `auth_users.region` |
| `created_at`, `updated_at` | timestamp | `user_profiles` |

**Lỗi:** 404 khi user chưa có profile, 400, 403, 500.
**Ví dụ:** `GET /api/v1/users/9b1…/profile` → `{"id":"p1","user_id":"9b1…","first_name":"Minh","last_name":"Trần","region":"VN",…}`
**AI dùng khi:** chỉ cần tên của một user id. Route `GET /users/{id}` đã trả đủ thông tin này nên thường không cần gọi.

---

#### `GET /profile`
**Chức năng:** Hồ sơ của **chính người đang hỏi**. Nếu chưa có thì tự tạo một profile rỗng (`GetOrCreateByUserID`).
**Quyền:** chỉ cần đăng nhập. **Phạm vi dữ liệu:** chính mình.
**Tham số:** không có.
**Kết quả:** `ProfileResponse`, cùng các trường như route trên.
**Lỗi:** 400 "user not authenticated", 500.
**Ví dụ:** `GET /api/v1/profile` → `{"user_id":"…","first_name":"An","last_name":"Nguyễn","region":"VN"}`
**AI dùng khi:** "Tôi là ai?", hoặc khi cần tên người hỏi để xưng hô.

---

#### `GET /organizations`
**Chức năng:** Danh sách tổ chức trong bảng `organizations`, gồm QS, chi nhánh và đại lý (Agent). Các tổ chức xếp thành cây qua `parent_id` và `path`.
**Quyền:** `organization.read`, **hoặc** bất kỳ user có role `agent_*` (`AuthorizeAnyOrAgent`). **Phạm vi dữ liệu:**
- SQL không lọc theo scope.
- Nếu người gọi **không phải** nhân viên QS (`admin` / `qs_support_engineer`), handler lọc trong bộ nhớ và chỉ giữ những tổ chức mà người đó là thành viên.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `parent_id` | query | uuid | không | — | Chỉ lấy tổ chức con trực tiếp của org này |
| `status` | query | string | không | — | Khớp chính xác `organizations.status`. Dữ liệu hiện có chỉ thấy giá trị `active` |
| `limit` | query | int | không | 50 | |
| `offset` | query | int | không | 0 | |

Sắp xếp theo `path, created_at DESC`.
**Kết quả:** `{items, limit, offset}`. **Không có `total`.**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `organizations.id` |
| `code` | string | mã tổ chức |
| `name` | string | tên |
| `parent_id` | uuid? | tổ chức cha |
| `path` | string | đường dẫn trong cây |
| `level` | int | độ sâu trong cây |
| `status` | string | ví dụ `active` |
| `agent_type` | string | `managing` \| `support` \| rỗng (rỗng = không phải đại lý) |
| `created_at`, `updated_at` | timestamp | |

**Lỗi:** 400, 403, 500.
**Ví dụ:** `GET /api/v1/organizations?limit=100`
```json
{"items":[{"id":"o1","code":"QS","name":"QS Việt Nam","path":"qs","level":0,"status":"active","created_at":"…","updated_at":"…"},{"id":"o2","code":"DL-HCM","name":"Đại lý HCM","parent_id":"o1","path":"qs.dlhcm","level":1,"status":"active","agent_type":"support",…}],"limit":100,"offset":0}
```
**AI dùng khi:** "Có những đại lý nào?", "Đổi `organization_id` / `support_organization_id` ra tên", "Chi nhánh X có những đơn vị con nào?"

---

#### `GET /organizations/{id}`
**Chức năng:** Chi tiết 1 tổ chức (`organizations`).
**Quyền:** route không gắn middleware quyền; handler tự kiểm tra. Người gọi phải có `organization.read`, **hoặc** là thành viên của chính tổ chức đó, **hoặc** là nhân viên QS. **Phạm vi dữ liệu:** như điều kiện vừa nêu.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** 1 object, cùng các trường như item của `GET /organizations`.
**Lỗi:** 403 `FORBIDDEN` "permission denied: organization.read", 404 "organization not found", 400, 500.
**Ví dụ:** `GET /api/v1/organizations/o2` → `{"id":"o2","name":"Đại lý HCM","agent_type":"support",…}`
**AI dùng khi:** cần tên hoặc loại của một tổ chức theo id. Ví dụ "Phiếu này do đại lý nào xử lý?" khi chỉ có `assignee_org_id`.

---

#### `GET /organizations/{id}/representative`
**Chức năng:** Trả về **khách hàng đại diện** của một đại lý (quy tắc nghiệp vụ 44). Đây là khách đứng tên cho Agent, tức `customers.self_of_organization_id = id`.
**Quyền:** `organization.read`. **Phạm vi dữ liệu:** không lọc thêm.
**Tham số:** `id` (path, uuid tổ chức, bắt buộc).
**Kết quả:** `{"representative": null}` nếu chưa có đại diện, ngược lại là `{"representative": {customer_id, full_name, phone}}`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `representative.customer_id` | uuid | `customers.id` |
| `representative.full_name` | string | `customers.full_name` |
| `representative.phone` | string | (bị ẩn với AI) |

**Lỗi:** 403, 500.
**Ví dụ:** `GET /api/v1/organizations/o2/representative` → `{"representative":{"customer_id":"c9","full_name":"Công ty TNHH ABC"}}`
**AI dùng khi:** "Ai là đại diện của đại lý HCM?"

---

#### `GET /organizations/agent-stats`
**Chức năng:** Thống kê cho **mọi** tổ chức cùng lúc: tổng số máy tổ chức đang làm **Managing Agent** và số máy trong đó đang `active`. Truy vấn SQL thô trên `organizations` LEFT JOIN `product_agents` (`agent_role='managing_agent'`, chưa xoá) và `product_items`.
**Quyền:** `organization.read`. **Phạm vi dữ liệu:** **không lọc**, trả về tất cả tổ chức.
**Tham số:** không có. Không phân trang.
**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `organization_id` | uuid | `organizations.id` |
| `created_at` | string ISO | ngày tạo tổ chức |
| `created_by_name` | string | họ tên người tạo (`user_profiles` của `organizations.created_by`) |
| `distributed` | int | số máy (distinct) mà org đang quản lý |
| `active` | int | số máy trong đó có `product_items.status='active'` |

**Lỗi:** 500 "failed to load stats", 503 "unavailable".
**Ví dụ:** `GET /api/v1/organizations/agent-stats` → `{"items":[{"organization_id":"o2","created_at":"2026-01-10T00:00:00Z","created_by_name":"Nguyễn Admin","distributed":42,"active":30}]}`
**AI dùng khi:** "Đại lý nào đang quản lý nhiều máy nhất?", "Tỷ lệ máy đã kích hoạt theo từng đại lý?"

---

#### `GET /organizations/{id}/agent-stats`
**Chức năng:** Thống kê của **một** đại lý, gồm tổng số máy, số máy active, và số liệu theo từng tháng trong **6 tháng gần nhất** (số máy được giao, số máy được kích hoạt).
**Quyền:** `organization.read` + `RequireOrgParamInScope` (`{id}` phải nằm trong các tổ chức người gọi truy cập được). **Phạm vi dữ liệu:** do middleware vừa nêu bảo đảm.
**Tham số:** `id` (path, uuid tổ chức, bắt buộc).
**Kết quả:**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `created_at` | string | ngày tạo tổ chức |
| `created_by_name` | string | người tạo |
| `status` | string | `organizations.status` |
| `distributed` | int | số máy đang quản lý (Managing Agent) |
| `active` | int | số máy trong đó đang active |
| `monthly[]` | `{month:"YYYY-MM", distributed, activated}` | `distributed` = số grant tạo trong tháng (`product_agents.created_at`); `activated` = số máy active có `activated_at` trong tháng |

**Lỗi:** 404 "organization not found", 403 (ngoài scope), 500, 503.
**Ví dụ:** `GET /api/v1/organizations/o2/agent-stats` → `{"created_at":"…","created_by_name":"…","status":"active","distributed":42,"active":30,"monthly":[{"month":"2026-06","distributed":5,"activated":3},…]}`
**AI dùng khi:** "Đại lý HCM tháng này kích hoạt được bao nhiêu máy?", "Xu hướng 6 tháng của đại lý X?"

---

#### `GET /roles`
**Chức năng:** Danh sách vai trò (role) trong bảng `roles`, kèm data scope và tổ chức sở hữu (đối với role riêng của từng đại lý).
**Quyền:** `auth.manage_roles`, **hoặc** user có role `agent_*`. **Phạm vi dữ liệu:** người gọi là Agent chỉ thấy role `agent_admin` dùng chung và các role của đại lý mình. Nếu Agent không thuộc tổ chức nào thì nhận danh sách rỗng.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `keyword` | query | string | không | — | `LIKE`, không dấu, trên `roles.code` hoặc `roles.name` |
| `shared_only` | query | `true` | không | — | Chỉ lấy role dùng chung (`organization_id IS NULL`) |
| `organization_id` | query | uuid | không | — | Lấy các role của một đại lý. Với người gọi là Agent, giá trị này bị ghi đè bằng tổ chức của họ |
| `created_at_from` / `created_at_to` | query | date | không | — | lọc theo ngày tạo |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{roles: [...], limit, offset, total}`. Lưu ý mảng nằm ở key **`roles`**, không phải `items`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `roles.id` |
| `code` | string | ví dụ `sales`, `agent_admin`. Role riêng của từng máy có dạng `<uuid>-operator` / `<uuid>-technician` |
| `name` | string | tên hiển thị |
| `data_scope` | string | `SELF` \| `ORGANIZATION` \| `ORGANIZATION_AND_CHILDREN` \| `ALL` |
| `organization_id` | uuid? | đại lý sở hữu role |
| `organization_name` | string | tên đại lý sở hữu |

**Lỗi:** 400, 403, 500.
**Ví dụ:** `GET /api/v1/roles?shared_only=true` → `{"roles":[{"id":"r1","code":"sales","name":"Sales","data_scope":"SELF"}],"limit":50,"offset":0,"total":12}`
**AI dùng khi:** "Hệ thống có những vai trò nào?", "Role sales được xem dữ liệu ở phạm vi nào?"

---

#### `GET /products`
**Chức năng:** Danh mục **loại máy / model** trong bảng `products`. Đây không phải từng máy cụ thể. Chỉ lấy dòng có `deleted_at IS NULL`.
**Quyền:** `product.read`. **Phạm vi dữ liệu:** không lọc, mọi người có quyền đều thấy toàn bộ danh mục.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `search` | query | string | không | — | `name` ILIKE (không dấu) **hoặc** `code` ILIKE `%search%` |
| `limit` / `offset` | query | int | không | 50 / 0 | |

Sắp xếp theo `created_at DESC`.
**Kết quả:** `{items, limit, offset, total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `products.id` |
| `code` | string | mã sản phẩm |
| `name` | string | tên |
| `category` | string | nhóm sản phẩm |
| `warranty_months` | int | số tháng bảo hành mặc định |
| `specifications` | object | thông số kỹ thuật dạng JSON (bị ẩn với AI) |
| `image_url` | string | ảnh đại diện (bị ẩn với AI) |
| `created_at`, `updated_at`, `deleted_at` | timestamp | |

**Lỗi:** 400, 403, 500.
**Ví dụ:** `GET /api/v1/products?search=cnc` → `{"items":[{"id":"p1","code":"CNC3020","name":"Máy CNC 3020","category":"cnc","warranty_months":12,…}],"limit":50,"offset":0,"total":1}`
**AI dùng khi:** "Có bao nhiêu loại sản phẩm?" (`limit=1`, đọc `total`), "Máy CNC 3020 bảo hành mấy tháng?", tìm `product_id` để lọc `/product-items`.

---

#### `GET /products/{id}`
**Chức năng:** Chi tiết 1 loại máy (`products`).
**Quyền:** `product.read`. **Phạm vi dữ liệu:** không lọc.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** 1 object, cùng các trường như item của `GET /products`.
**Lỗi:** 400 "id is required", 404, 500.
**Ví dụ:** `GET /api/v1/products/p1` → `{"id":"p1","code":"CNC3020","name":"Máy CNC 3020","warranty_months":12,…}`
**AI dùng khi:** đổi `product_id` của một máy ra tên model.

---

#### `GET /products/{id}/support-limit`
**Chức năng:** Hạn mức hỗ trợ cấu hình cho **loại máy** (`product_support_limits`), gồm số phút hỗ trợ, số tin nhắn và số email tối đa. Nếu không có cấu hình thì nghĩa là không giới hạn ("no cap").
**Quyền:** `product.read`. **Phạm vi dữ liệu:** không lọc.
**Tham số:** `id` (path, uuid **product**, bắt buộc).
**Kết quả:**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `product_id` | uuid | |
| `max_support_minutes` | int | số phút hỗ trợ tối đa |
| `max_messages` | int | số tin nhắn tối đa |
| `max_emails` | int | số email tối đa |

**Lỗi:** **404 `NOT_FOUND` khi loại máy chưa cấu hình hạn mức** (hiểu là không giới hạn), 400, 500.
**Ví dụ:** `GET /api/v1/products/p1/support-limit` → `{"product_id":"p1","max_support_minutes":600,"max_messages":100,"max_emails":50}`
**AI dùng khi:** "Model X được hỗ trợ tối đa bao nhiêu giờ?" Nếu cần số giờ **còn lại** của một máy cụ thể thì dùng entitlement ở phần hỗ trợ.

---

#### `GET /product-items`
**Chức năng:** Danh sách **từng máy cụ thể** (có serial/mã) trong bảng `product_items` (`deleted_at IS NULL`). Mỗi dòng được bổ sung tên chủ máy và đại lý quản lý.
**Quyền:** `product_item.read`. **Phạm vi dữ liệu:** với scope `ORGANIZATION` / `ORGANIZATION_AND_CHILDREN` **và** người gọi là Agent-only, chỉ thấy máy mà tổ chức mình là Managing hoặc Support Agent (`product_agents.agent_organization_id ∈ AccessibleOrgs`). Nhân viên QS thấy tất cả.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa / giá trị hợp lệ |
|---|---|---|---|---|---|
| `customer_id` | query | uuid | không | — | Máy mà khách này đang sở hữu (`product_items.customer_id =`) |
| `product_id` | query | uuid | không | — | Máy thuộc model này |
| `status` | query | csv | không | — | Một hoặc nhiều giá trị, ngăn cách bởi dấu phẩy: `stock`, `delivered`, `active`, `maintenance`, `out_of_order`, `decommissioned`, `recalled`, `refurbished`. Giá trị sai bị **bỏ qua** (không báo lỗi) |
| `keyword` | query | string | không | — | Tách theo khoảng trắng. **Mỗi từ** phải khớp (AND) với `code` ILIKE **hoặc** chủ máy có `full_name` (không dấu) / `phone` / `company_name` (không dấu) chứa từ đó. Vì vậy "an nguyen" vẫn tìm được "Nguyễn Văn An" |
| `owner_type` | query | enum | không | — | `customer` = khách thường đang sở hữu; `agent` = máy chưa có khách nhưng có Managing Agent, hoặc chủ là khách đại diện của Agent; `qs` = chưa có khách và không có Managing Agent (máy ở kho QS) |
| `held_by_org` | query | uuid | không | — | Nếu org là đại lý (có `agent_type`): máy mà đại lý giữ grant. Nếu org không phải đại lý: máy **không có** grant nào (tức QS giữ) |
| `created_at_from` | query | `YYYY-MM-DD` | không | — | `created_at >=` ngày này. Sai định dạng thì bị bỏ qua |
| `created_at_to` | query | `YYYY-MM-DD` | không | — | Tính trọn ngày này (`created_at <` ngày + 1) |
| `limit` / `offset` | query | int | không | 50 / 0 | |

Sắp xếp: hoạt động mới nhất trước, tức `GREATEST(created_at, updated_at, thời điểm grant agent mới nhất) DESC`.
**Kết quả:** `{items, limit, offset, total}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | `product_items.id` |
| `code` | string | mã / serial máy |
| `product_id` | uuid? | → `products` |
| `customer_id` | uuid? | chủ hiện tại (`product_items.customer_id`) |
| `owner_customer_id` | uuid | chủ theo ownership. Chỉ có ở danh sách |
| `owner_name` | string | tên khách sở hữu. Nếu không có khách thì là tên đại lý quản lý. Chỉ có ở danh sách |
| `owner_is_agent` | bool | chủ là khách đại diện của một Agent |
| `managing_agent_org_id` | uuid | đại lý quản lý |
| `managing_agent_name` | string | tên đại lý quản lý |
| `status` | string | trạng thái máy (xem enum ở trên) |
| `manufacturing_date`, `installation_date` | date? | ngày sản xuất / lắp đặt |
| `warranty_expiry` | date? | ngày hết bảo hành |
| `activated_at` | timestamp? | ngày kích hoạt |
| `activated_by` | uuid? | user kích hoạt → `GET /users/{id}` |
| `recalled_at`, `refurbished_at` | timestamp? | ngày thu hồi / tân trang |
| `activation_notes`, `recall_notes`, `refurbish_notes`, `device_input` | string | (bị ẩn với AI) |
| `created_at`, `updated_at`, `deleted_at` | timestamp | |

**Lỗi:** 400, 403, 500.
**Ví dụ:** `GET /api/v1/product-items?customer_id=c1&status=active,maintenance`
```json
{"items":[{"id":"pi1","code":"QS-2026-0001","product_id":"p1","customer_id":"c1","owner_customer_id":"c1","owner_name":"Nguyễn Văn An","managing_agent_name":"Đại lý HCM","status":"active","activated_at":"2026-03-01T00:00:00Z","warranty_expiry":"2027-03-01T00:00:00Z",…}],"limit":50,"offset":0,"total":1}
```
**AI dùng khi:** "Khách A có những máy nào?", "Có bao nhiêu máy đang hoạt động?" (`status=active&limit=1`), "Máy mã QS-2026-0001 của ai?" (`keyword=QS-2026-0001`), "Kho QS còn bao nhiêu máy?" (`owner_type=qs&status=stock`).

---

#### `GET /product-items/{id}`
**Chức năng:** Chi tiết 1 máy (`product_items`).
**Quyền:** `product_item.read`. **Phạm vi dữ liệu:** người gọi là Agent-only (scope `ORGANIZATION*`) mà máy không thuộc đại lý của mình thì nhận **404** (cố ý trả 404 để không lộ máy tồn tại).
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** 1 `ProductItemResponse`. **Khác với danh sách:** **không** có `owner_name`, `owner_customer_id`, `managing_agent_*`, `owner_is_agent`.
**Lỗi:** 404 "product item not found", 400 "id is required", 500.
**Ví dụ:** `GET /api/v1/product-items/pi1` → `{"id":"pi1","code":"QS-2026-0001","product_id":"p1","customer_id":"c1","status":"active",…}`
**AI dùng khi:** đã có id máy và cần trạng thái hoặc ngày bảo hành. Nếu cần tên chủ máy thì dùng `GET /product-items?keyword=<code>`.

---

#### `GET /product-items/{id}/agents`
**Chức năng:** **Toàn bộ lịch sử** các đại lý từng được gán cho máy (bảng `product_agents`, gồm cả grant đã gỡ). Mỗi dòng có vai trò Managing hoặc Support.
**Quyền:** `product_item.read`. **Phạm vi dữ liệu:** handler **không** kiểm tra máy có thuộc scope của người gọi hay không (theo code hiện tại).
**Tham số:** `id` (path, uuid product_item, bắt buộc).
**Kết quả:** `{items: [...]}`, sắp `created_at DESC`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `product_agents.id` |
| `product_item_id` | uuid | |
| `agent_organization_id` | uuid | đại lý |
| `agent_organization_name` | string | tên đại lý |
| `agent_role` | string | `managing_agent` (đại lý quản lý) \| `support_agent` (đại lý hỗ trợ) |
| `created_by` | uuid? | người gán |
| `created_at` | timestamp | thời điểm gán |
| `is_active` | bool | `false` = grant đã bị gỡ (`deleted_at` có giá trị) |

**Lỗi:** 400, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/pi1/agents` → `{"items":[{"agent_organization_name":"Đại lý HCM","agent_role":"managing_agent","is_active":true,"created_at":"2026-02-01T…"}]}`
**AI dùng khi:** "Máy này do đại lý nào quản lý / hỗ trợ?", "Máy đã qua tay những đại lý nào?"

---

#### `GET /product-items/{id}/ownership-history`
**Chức năng:** Lịch sử chủ sở hữu của máy, đọc từ bảng `product_ownerships` (`deleted_at IS NULL`).
**Quyền:** `product_item.read`. **Phạm vi dữ liệu:** handler không kiểm tra scope theo máy.
**Tham số:** `id` (path, uuid product_item, bắt buộc).
**Kết quả:** `{items: [...]}`, sắp `created_at DESC`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `product_ownerships.id` |
| `product_item_id` | uuid | |
| `owner_customer_id` | uuid | khách sở hữu → `GET /customers/{id}` để lấy tên |
| `is_current` | bool | `true` = chủ hiện tại |
| `transferred_from_ownership_id` | uuid? | dòng ownership trước đó (chuyển nhượng từ ai) |
| `created_by` | uuid? | người thực hiện |
| `created_at` | timestamp | thời điểm bắt đầu sở hữu |

**Lỗi:** 400, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/pi1/ownership-history` → `{"items":[{"owner_customer_id":"c2","is_current":true,"transferred_from_ownership_id":"ow1","created_at":"2026-09-01T…"},{"id":"ow1","owner_customer_id":"c1","is_current":false,…}]}`
**AI dùng khi:** "Máy này trước đây của ai?", "Máy được chuyển nhượng khi nào?"

---

#### `GET /product-items/{id}/access`
**Chức năng:** Danh sách tài khoản portal được quyền xem / thao tác máy (`product_user_access`, `deleted_at IS NULL`).
**Quyền:** `product_item.read`. **Phạm vi dữ liệu:** handler không kiểm tra scope theo máy.
**Tham số:** `id` (path, uuid product_item, bắt buộc).
**Kết quả:** `{items: [...]}`, sắp `created_at DESC`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `product_item_id` | uuid | |
| `auth_user_id` | uuid | tài khoản được cấp quyền |
| `access_role` | string | `owner` \| `technician` \| `operator` |
| `invited_by` | uuid? | người mời |
| `created_at` | timestamp | |

**Lỗi:** 400, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/pi1/access` → `{"items":[{"auth_user_id":"u7","access_role":"technician","invited_by":"u1","created_at":"…"}]}`
**AI dùng khi:** "Những ai đang được truy cập máy này trên portal?"

---

#### `GET /product-items/{id}/logs`
**Chức năng:** Nhật ký **vòng đời máy** (`product_item_logs`): tạo, kích hoạt, giao, thu hồi, chuyển chủ, gán đại lý…
**Quyền:** `product_item.read_logs`. **Phạm vi dữ liệu:** người gọi là Agent-only chỉ thấy log **từ thời điểm** đại lý của mình được gán vào máy. Nếu đại lý chưa từng được gán thì danh sách rỗng. Khi đó `total` = số dòng còn lại sau khi lọc.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | product_item |
| `limit` | query | int | không | 100 | tối đa 200 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{items: [...], total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `event_type` | string | `created`, `activated`, `reactivated`, `recalled`, `refurbished`, `keygen`, `work_order_linked`, `status_changed`, `ownership_transferred`, `delivered`, `agent_assigned`, `agent_returned`, `warranty_changed`, `deleted` |
| `source` | string | `direct`, `bulk`, `approval_request`, `customer_portal`, `system`, `work_order` |
| `actor` | `{id, name, role}` | người thực hiện. `role` ∈ `admin`, `sales`, `accountant`, `system`, `customer` |
| `customer` | `{id, name}` | khách liên quan |
| `transfer_from`, `transfer_to` | `{id, name}` | dùng cho sự kiện chuyển chủ |
| `metadata` | object | chi tiết thêm tuỳ theo sự kiện |
| `occurred_at` | timestamp | thời điểm xảy ra |

**Lỗi:** 400 "product item id is required", 500.
**Ví dụ:** `GET /api/v1/product-items/pi1/logs?limit=10` → `{"items":[{"event_type":"activated","source":"approval_request","actor":{"id":"u3","name":"Kế toán B","role":"accountant"},"customer":{"id":"c1","name":"Nguyễn Văn An"},"metadata":{},"occurred_at":"2026-03-01T…"}],"total":5}`
**AI dùng khi:** "Máy này được kích hoạt khi nào, bởi ai?", "Lịch sử của máy QS-0001?"

---

#### `GET /product-items/{id}/lock-requests`
**Chức năng:** Các **yêu cầu mở khoá máy** (`lock_requests`) của một máy. Mỗi yêu cầu là xin mã unlock.
**Quyền:** `product_item.read` **hoặc** `product_item.activate`. **Phạm vi dữ liệu:**
- Chỉ hiện yêu cầu tạo **từ khi chủ hiện tại nhận máy**. Yêu cầu của chủ cũ bị ẩn với tất cả mọi người.
- `unlock_key` chỉ hiện với chủ máy, nhân viên (staff), hoặc chính người tạo yêu cầu. Người khác nhận `null`.
- Handler lấy cố định 100 dòng đầu.
**Tham số:** `id` (path, uuid product_item, bắt buộc). Không phân trang.
**Kết quả:** `{items, limit:100, offset:0, total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `product_item_id` | uuid | |
| `requester_id` | uuid | người yêu cầu |
| `requester_name` | string | tên người yêu cầu |
| `status` | string | `pending` (chờ chủ máy), `pending_admin` (chủ máy đã đồng ý nhưng chuyển admin tạo key), `approved`, `rejected` |
| `reason` | string | lý do |
| `device_input` | string | (bị ẩn với AI) |
| `approved_by` | uuid? | người duyệt |
| `unlock_key` | string? | **mã mở khoá. KHÔNG nằm trong `hiddenFields` nên AI sẽ thấy nếu người hỏi có quyền xem** |
| `reject_reason` | string | lý do từ chối |
| `created_at`, `resolved_at` | timestamp | |

**Lỗi:** 401 `UNAUTHENTICATED`, 400 `INVALID_INPUT`, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/pi1/lock-requests` → `{"items":[{"id":"l1","requester_name":"Kỹ thuật D","status":"approved","created_at":"…","resolved_at":"…"}],"limit":100,"offset":0,"total":1}`
**AI dùng khi:** "Máy này có ai xin mở khoá không?", "Yêu cầu mở khoá gần nhất đã được duyệt chưa?"

---

#### `GET /organizations/{id}/product-agents`
**Chức năng:** Các máy mà một đại lý **đang** được gán (grant còn hiệu lực), kèm mã máy, tên model và trạng thái máy.
**Quyền:** `product_item.read` + `RequireOrgParamInScope`. **Phạm vi dữ liệu:** `{id}` phải nằm trong các tổ chức người gọi truy cập được.
**Tham số:** `id` (path, uuid tổ chức, bắt buộc). Không phân trang.
**Kết quả:** `{items: [...]}`, sắp theo `product_items.code`.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `product_item_id`, `agent_organization_id`, `agent_organization_name`, `agent_role`, `created_by`, `created_at`, `is_active` | | như `/product-items/{id}/agents` |
| `product_item_code` | string | mã máy |
| `product_name` | string | tên model |
| `product_status` | string | trạng thái máy |

**Lỗi:** 403 (ngoài scope), 500.
**Ví dụ:** `GET /api/v1/organizations/o2/product-agents` → `{"items":[{"product_item_id":"pi1","product_item_code":"QS-2026-0001","product_name":"Máy CNC 3020","product_status":"active","agent_role":"managing_agent","is_active":true,…}]}`
**AI dùng khi:** "Đại lý HCM đang quản lý những máy nào?"

---

#### `GET /lock-requests`
**Chức năng:** Hàng đợi yêu cầu mở khoá **cần admin xử lý**, gồm các yêu cầu đang `pending_admin` và các yêu cầu đã được **staff** (không phải chủ máy là khách) duyệt hoặc từ chối. Kèm mã máy và khách. Tối đa 100 dòng.
**Quyền:** `product_item.approve_activation` + `ApplyScope`. **Phạm vi dữ liệu:** từng dòng được kiểm tra máy có nằm trong scope của người gọi không (Agent chỉ thấy máy của đại lý mình). Dòng ngoài scope bị bỏ qua.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `pending` (được hiểu là `pending_admin`), `pending_admin`, `approved`, `rejected` |

**Kết quả:** `{items: [...], total}`. Mỗi item gồm toàn bộ trường của lock request (như route trên) cộng thêm:
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `product_item_code` | string | mã máy |
| `requester_customer_id` | uuid | khách của người yêu cầu (`auth_users.ref_id`) |
| `customer_id`, `customer_name` | | chủ máy hiện tại |

**Lỗi:** 403, 500.
**Ví dụ:** `GET /api/v1/lock-requests?status=pending` → `{"items":[{"id":"l2","product_item_code":"QS-0005","customer_name":"Cty ABC","status":"pending_admin",…}],"total":1}`
**AI dùng khi:** "Có bao nhiêu yêu cầu mở khoá đang chờ admin?"

---

#### `GET /lock-requests/{id}`
**Chức năng:** Chi tiết 1 yêu cầu mở khoá.
**Quyền:** `product_item.read` **hoặc** `product_item.activate`. **Phạm vi dữ liệu:** `unlock_key` được che như ở `/product-items/{id}/lock-requests`. Handler **không** gọi kiểm tra scope máy (theo code hiện tại).
**Tham số:** `id` (path, uuid lock request, bắt buộc).
**Kết quả:** 1 object lock request (các trường như trên).
**Lỗi:** 404, 401, 500.
**Ví dụ:** `GET /api/v1/lock-requests/l1` → `{"id":"l1","status":"approved","requester_name":"Kỹ thuật D",…}`
**AI dùng khi:** đã có id yêu cầu và cần xem trạng thái hoặc người duyệt.

---

#### `GET /product-items/activation-requests`
**Chức năng:** Danh sách **yêu cầu kích hoạt máy** (`product_item_activation_requests`). Sale hoặc đại lý gửi danh sách mã máy cho một khách, và kế toán hoặc admin duyệt.
**Quyền:** chỉ có `ApplyScope` ở router. Handler bắt buộc người gọi có `product_item.approve_activation` **hoặc** `product_item.request_activation`, nếu không thì 403. **Phạm vi dữ liệu:**
- Người gọi là Agent: chỉ thấy yêu cầu của đại lý mình.
- Không phải Agent và không có quyền duyệt: chỉ thấy yêu cầu **mình gửi** (`sales_user_id`).
- Nhân viên QS có quyền duyệt: thấy tất cả, **trừ** yêu cầu thuộc đại lý (`ExcludeOrgOwned`, vì đại lý tự duyệt).
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `pending` \| `approved` \| `rejected` |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{items, total, limit, offset}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `request_type` | string | `activation` \| `supplemental_product` |
| `sales_user_id`, `sales_user_name` | | người gửi |
| `customer_id`, `customer_name` | | khách sẽ nhận máy |
| `organization_id` | uuid? | đại lý gửi (nếu có) |
| `inputs` | string[] | danh sách mã / chuỗi máy cần kích hoạt |
| `input_states[]` | `{input, code, found, status, customer_id, customer_name}` | **chỉ có khi `pending`**: tình trạng hiện tại của từng máy, dùng để cảnh báo máy đã thuộc khách khác |
| `warranty_expiry` | date? | hạn bảo hành đề nghị |
| `status` | string | `pending` \| `approved` \| `rejected` |
| `result` | `{total, success, failed, rows}` | kết quả kích hoạt hàng loạt sau khi duyệt |
| `reject_reason` | string | |
| `submitted_at` | timestamp | |
| `reviewed_by`, `reviewed_by_name`, `reviewed_at` | | người duyệt |

**Lỗi:** 400 `BAD_REQUEST`, 403 `FORBIDDEN` / `OUT_OF_AGENT_SCOPE` / `CUSTOMER_OTHER_ORG`, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/activation-requests?status=pending` → `{"items":[{"id":"a1","request_type":"activation","sales_user_name":"Trần Minh","customer_name":"Nguyễn Văn An","inputs":["QS-0001"],"status":"pending","submitted_at":"…"}],"total":1,"limit":50,"offset":0}`
**AI dùng khi:** "Có bao nhiêu yêu cầu kích hoạt đang chờ duyệt?", "Yêu cầu kích hoạt máy cho khách A đã được duyệt chưa, ai duyệt?"

---

#### `GET /product-items/activation-requests/{id}`
**Chức năng:** Chi tiết 1 yêu cầu kích hoạt.
**Quyền:** giống route danh sách (approve **hoặc** request). **Phạm vi dữ liệu:** Agent chỉ xem được yêu cầu của đại lý mình (nếu không thì 403 `OUT_OF_AGENT_SCOPE`). Người không phải Agent và không có quyền duyệt chỉ xem được yêu cầu của chính mình (nếu không thì 403).
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** 1 object, cùng các trường như item ở trên.
**Lỗi:** 400, 403, 404, 500.
**Ví dụ:** `GET /api/v1/product-items/activation-requests/a1` → `{"id":"a1","status":"approved","reviewed_by_name":"Kế toán B","result":{"total":1,"success":1,"failed":0,"rows":[…]},…}`
**AI dùng khi:** xem chi tiết hoặc kết quả của một yêu cầu kích hoạt cụ thể.

---

#### `GET /product-items/return-requests`
**Chức năng:** Danh sách **yêu cầu trả máy về QS** của đại lý (`product_item_return_requests`). Mỗi yêu cầu có thể gồm nhiều máy.
**Quyền:** chỉ có `ApplyScope`, router không đòi permission. **Phạm vi dữ liệu:**
- Nếu context có `AccessibleOrgs`: lọc yêu cầu thuộc các tổ chức đó.
- Nếu không có, và người gọi không có `product_item.approve_return`: chỉ thấy yêu cầu do mình tạo.
- Người duyệt có scope `ALL` (không có `AccessibleOrgs`) thấy tất cả.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `pending` \| `approved` \| `rejected` |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{items, total, limit, offset}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `requested_by`, `requested_by_name` | | người tạo yêu cầu |
| `organization_id`, `organization_name` | | đại lý trả máy |
| `items[]` | `{id, code}` | các máy trả về |
| `notes` | string | ghi chú (bị ẩn với AI) |
| `status` | string | `pending` \| `approved` \| `rejected` |
| `reject_reason` | string | |
| `reviewed_by`, `reviewed_by_name`, `reviewed_at` | | người duyệt |
| `created_at` | string | |

**Lỗi:** 401, 403, 500.
**Ví dụ:** `GET /api/v1/product-items/return-requests?status=pending` → `{"items":[{"id":"rr1","organization_name":"Đại lý HCM","items":[{"id":"pi9","code":"QS-0009"}],"status":"pending","created_at":"…"}],"total":1,"limit":50,"offset":0}`
**AI dùng khi:** "Đại lý nào đang xin trả máy?", "Yêu cầu trả máy QS-0009 đã được duyệt chưa?"

---

#### `GET /product-items/recall-requests`
**Chức năng:** Danh sách **yêu cầu thu hồi máy** từ khách (`product_item_recall_requests`).
**Quyền:** chỉ có `ApplyScope`. Router không đòi permission và handler cũng **không** kiểm tra quyền hay lọc scope (theo code hiện tại). Mọi user đã đăng nhập đều đọc được toàn bộ danh sách.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `pending` \| `confirmed` \| `cancelled` |
| `product_item_id` | query | uuid | không | — | yêu cầu của một máy |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{items, total, limit, offset}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `product_item_id`, `product_item_code` | | máy |
| `customer_id`, `customer_name` | | khách đang giữ máy |
| `requested_by` | uuid | người tạo yêu cầu |
| `return_to_qs` | bool | máy về kho QS (`true`) hay ở lại đại lý |
| `notes` | string | (bị ẩn với AI) |
| `status` | string | `pending` \| `confirmed` \| `cancelled` |
| `confirmed_at`, `cancelled_at`, `created_at` | timestamp | |

**Lỗi:** 500.
**Ví dụ:** `GET /api/v1/product-items/recall-requests?product_item_id=pi1` → `{"items":[{"product_item_code":"QS-0001","customer_name":"Nguyễn Văn An","status":"confirmed","return_to_qs":true,…}],"total":1,"limit":50,"offset":0}`
**AI dùng khi:** "Máy X có đang bị thu hồi không?", "Danh sách thu hồi đang chờ xác nhận?"

---

#### `GET /product-items/transfer-requests`
**Chức năng:** Danh sách **yêu cầu chuyển chủ sở hữu máy** từ khách này sang khách khác (`product_ownership_transfer_requests`), kèm file minh chứng.
**Quyền:** `product_item.request_transfer` **hoặc** `product_item.approve_transfer`. **Phạm vi dữ liệu:** người không có `approve_transfer` chỉ thấy yêu cầu do mình gửi. Người duyệt thấy tất cả.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | — | `pending` \| `approved` \| `rejected` |
| `product_item_id` | query | uuid | không | — | yêu cầu của một máy |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{items, total, limit, offset}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `product_item_id`, `product_item_code`, `product_name` | | máy |
| `from_customer_id`, `from_customer_name` | | chủ cũ |
| `to_customer_id`, `to_customer_name` | | chủ mới |
| `reason` | string | lý do chuyển |
| `status` | string | `pending` \| `approved` \| `rejected` |
| `reject_reason` | string | |
| `requested_by`, `requested_by_name` | | người gửi |
| `reviewed_by`, `reviewed_by_name`, `reviewed_at` | | người duyệt |
| `created_at` | string | |
| `evidence[]` | attachment | file minh chứng (tên, id…). Tải file qua route evidence, phần này không mô tả route đó |

**Lỗi:** 401, 403, 500.
**Ví dụ:** `GET /api/v1/product-items/transfer-requests?status=pending` → `{"items":[{"product_item_code":"QS-0001","from_customer_name":"Nguyễn Văn An","to_customer_name":"Cty XYZ","status":"pending","requested_by_name":"Trần Minh",…}],"total":1,"limit":50,"offset":0}`
**AI dùng khi:** "Máy QS-0001 có đang chờ chuyển chủ không?", "Ai đã duyệt chuyển nhượng máy X?"

---

#### `GET /request-comments/{kind}/{id}`
**Chức năng:** Luồng **ghi chú / trao đổi** gắn vào một yêu cầu (kích hoạt, trả máy, mở khoá, chuyển chủ). Mỗi ghi chú có thể kèm file.
**Quyền:** `ApplyScope`. Handler tự kiểm tra người gọi là **người tạo yêu cầu**, **hoặc** có quyền duyệt của loại yêu cầu đó. Nếu yêu cầu thuộc một đại lý và người gọi bị giới hạn theo tổ chức, người gọi phải thuộc đại lý đó. **Phạm vi dữ liệu:** như điều kiện vừa nêu.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `kind` | path | enum | có | — | `activation` (gồm cả yêu cầu `supplemental_product`) \| `return` \| `lock` \| `transfer` |
| `id` | path | uuid | có | — | id của yêu cầu tương ứng |

**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `author_id`, `author_name` | | người viết |
| `body` | string | nội dung (cắt ở 800 ký tự khi đi qua AI) |
| `created_at` | string | |
| `attachments[]` | attachment | file đính kèm |

**Lỗi:** 404 `NOT_FOUND` (sai `kind` hoặc không có yêu cầu), 403 `FORBIDDEN`, 401, 500.
**Ví dụ:** `GET /api/v1/request-comments/activation/a1` → `{"items":[{"author_name":"Kế toán B","body":"Thiếu hoá đơn, bổ sung giúp","created_at":"…","attachments":[]}]}`
**AI dùng khi:** "Vì sao yêu cầu kích hoạt a1 bị từ chối / đang treo, hai bên đã trao đổi gì?"

---

#### `GET /keygen/history`
**Chức năng:** Lịch sử **sinh mã** (`keygen_history`), gồm mã nhà máy, mã kích hoạt và mã khoá máy. Có đầu vào, đầu ra, người sinh và máy liên quan.
**Quyền:** `keygen.read_history` + `ApplyScope`. **Phạm vi dữ liệu** (theo bộ quyền keygen của người gọi):
- Có đủ `keygen.factory` + `keygen.active` + `keygen.machine_lock` (admin): xem tất cả, được lọc `key_type`.
- Chỉ có `keygen.active`: xem mã `active` của tổ chức mình.
- Chỉ có `keygen.machine_lock`: xem mã `machine_lock` do chính mình sinh.
- Không thuộc các trường hợp trên nhưng có truyền `product_item_id`: xem lịch sử của máy đó (được lọc thêm `key_type`).
- Còn lại: chỉ xem mã do chính mình sinh.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `product_item_id` | query | uuid | không | — | mã đã sinh cho một máy |
| `key_type` | query | enum | không | — | `factory` \| `active` \| `machine_lock`. Chỉ có tác dụng với admin hoặc khi có `product_item_id` |
| `date_from` / `date_to` | query | **RFC3339** | không | — | ví dụ `2026-10-01T00:00:00Z`. Sai định dạng thì bị bỏ qua |
| `limit` / `offset` | query | int | không | 50 / 0 | |

**Kết quả:** `{items, total, limit, offset}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `key_type` | string | `factory` \| `active` \| `machine_lock` |
| `input_data` | object | tham số đầu vào khi sinh mã |
| `output_data` | object | mã sinh ra. Khoá con tên `password` bị ẩn với AI, nhưng các khoá khác (ví dụ `week`, `days_30`, `infinity` của machine_lock) **không** bị ẩn |
| `generated_by`, `generated_by_name` | | người sinh mã |
| `organization_id` | uuid? | |
| `product_item_id`, `product_item_code` | | máy liên quan |
| `created_at` | timestamp | |

**Lỗi:** 400 (thiếu đăng nhập hoặc tham số sai), 403, 500.
**Ví dụ:** `GET /api/v1/keygen/history?product_item_id=pi1&limit=5` → `{"items":[{"key_type":"active","generated_by_name":"Kế toán B","product_item_code":"QS-0001","created_at":"…"}],"total":2,"limit":5,"offset":0}`
**AI dùng khi:** "Máy QS-0001 đã được sinh mã kích hoạt mấy lần, ai sinh?" **Lưu ý bảo mật:** mã khoá / mở máy có thể lọt tới AI qua `output_data` và `unlock_key`. Nên bổ sung các trường này vào `hiddenFields` trước khi bọc thành tool.

### 3.3 Hỗ trợ 1:1 và hộp thư chờ

Phần này dựa trên code trong `internal/service/support/*`, `internal/platform/setting/setting.go` và `internal/adapters/http/router.go`.

#### Quy ước chung cho cả nhóm
- **Kiểu trả về:** các API **không** bọc kết quả trong `{data: ...}`. Danh sách có 3 dạng tuỳ API:
  - `{items, limit, offset, total}`
  - `{items, total}`
  - chỉ có `{items}`
  
  Bản ghi đơn lẻ được trả về trực tiếp.
- **Lỗi:** body có dạng `{"error": "...", "code": "..."}`. Riêng nhóm waiting-messages chỉ có `{"error"}`, trừ một số trường hợp có thêm `code`.
- **`limit` / `offset`:** nếu không truyền hoặc truyền giá trị không phải số thì dùng mặc định. Nhóm support/cases **không giới hạn tối đa**. Nhóm waiting-messages có giới hạn riêng, ghi ở từng API.
- **`ScopeGuard`** (gắn trên mọi route `/support/cases/{id}/...`):
  - Tài khoản thuộc tổ chức Agent chỉ đi qua được nếu phiếu nằm trong phạm vi của họ:
    - **agent_admin:** phiếu đang được giao cho tổ chức mình, hoặc phiếu của khách thuộc tổ chức mình mà chưa ai nhận, hoặc phiếu do nhân viên tổ chức mình tạo.
    - **nhân viên Agent thường:** phiếu do mình tạo, hoặc phiếu đang được giao đích danh cho mình.
  - Không đạt thì trả `403 FORBIDDEN`. Tài khoản không thuộc Agent (QS) không bị chặn ở bước này.
- **Kiểm tra quyền trên máy** (`AuthorizeCase` theo `product_item_id` của phiếu):
  - Nhân viên luôn đạt.
  - Khách (portal) phải là chủ máy hoặc được cấp quyền trên máy.
  - Khách được cấp quyền nhưng role trên máy không có quyền cần thiết → `403 PRODUCT_PERMISSION_DENIED`. Không chạm được tới máy → `403 FORBIDDEN`.
- **"Nhân viên"** trong nhóm hỗ trợ = tài khoản có quyền `support_case.read_internal` (với tin nhắn) hoặc `waiting_message.handle` (với hộp thư chờ).
- **Trường bị ẩn với AI** (`hiddenFields`) có trong nhóm này: `phone`, `avatar_url`. Các trường như `creator_phone` hay `creator_avatar_url` **không** nằm trong danh sách ẩn, vì danh sách chỉ so khớp đúng tên trường.

---

#### `GET /support/cases`
**Chức năng:** Liệt kê phiếu hỗ trợ 1:1 (bảng `support_cases`). Tên khách, tên người phụ trách và tên máy được tính sẵn trong cùng câu SQL. Sắp xếp theo `created_at` giảm dần. Tự loại phiếu đã xoá mềm và phiếu có chủ máy hiện tại là khách đã bị xoá.

**Quyền:** `support_case.read`.

**Phạm vi dữ liệu:** tính trong handler theo data scope.
| Data scope / loại tài khoản | Thấy phiếu nào |
|---|---|
| `SELF` (khách portal) | Phiếu trên mọi máy mình là chủ hoặc được cấp quyền. Với máy được cấp quyền sau này, chỉ thấy phiếu tạo từ lúc được cấp trở đi (phiếu tự mình tạo thì luôn thấy). Ẩn phiếu khách đã tự ẩn. Máy mà role của khách không có `support_case.read` thì ẩn toàn bộ phiếu. Máy không có `support_case.view_all` thì chỉ thấy phiếu mình tạo hoặc đang được giao cho mình. |
| `ORGANIZATION(_AND_CHILDREN)` + tài khoản Agent | agent_admin thấy toàn bộ hàng đợi của tổ chức (điều kiện như mô tả ở `ScopeGuard`). Nhân viên Agent thường chỉ thấy phiếu mình tạo hoặc đang được giao đích danh cho mình. |
| Nhân viên QS không có scope `ALL` | **Chỉ thấy phiếu mình tạo hoặc đang được giao đích danh cho mình** (`created_by = me OR support_assignments.is_current AND assigned_to = me`). |
| `ALL` (admin) | Thấy tất cả, **nhưng mặc định ẩn các phiếu đang được giao cho một tổ chức Agent**. Muốn xem các phiếu này thì truyền `handler=agent`. |

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa / giá trị hợp lệ |
|---|---|---|---|---|---|
| `product_item_id` | query | uuid | không | — | So khớp đúng `support_cases.product_item_id`. **Không có tham số `customer_id`.** Muốn lấy phiếu của một khách thì lặp qua từng máy của khách. |
| `status` | query | string | không | — | Một giá trị hoặc nhiều giá trị ngăn cách bằng dấu phẩy: `new`, `pending`, `in_progress`, `resolved`, `closed`, `reopened`, `cancelled`, `rejected` |
| `category` | query | string | không | — | Một giá trị: `installation`, `configuration`, `alarm`, `parameter`, `firmware`, `hardware`, `documentation`, `training`, `service`, `other` |
| `priority` | query | string | không | — | `low`, `normal`, `high`, `critical` |
| `keyword` | query | string | không | — | So khớp ILIKE với `case_number`, **hoặc** với `subject` (bỏ dấu), **hoặc** với tên tổ chức của khách (`customer_organization_id` → `organizations.name`, bỏ dấu). **Không** tìm được theo tên khách cá nhân. |
| `handler` | query | string | không | — | `agent` = phiếu đang được giao cho một tổ chức Agent. `qs` = phiếu không được giao cho Agent. |
| `assigned_to_me` | query | bool | không | — | `true` = chỉ lấy phiếu đang được giao cho người gọi (`is_current`). Dùng kèm `not_started=true` (phiên chưa bắt đầu, phiếu chưa kết thúc) hoặc `unaccepted=true` (chưa bấm nhận, hoặc đã tới giờ hẹn đã xác nhận mà chưa bắt đầu). |
| `awaiting_pick` | query | bool | không | — | Phiếu đã giao cho tổ chức Agent nhưng chưa có người cụ thể, status là `new`, `pending` hoặc `reopened`, phiên chưa bắt đầu. |
| `awaiting_reply` | query | bool | không | — | Phiếu có lịch hẹn `requested`/`confirmed`, chưa có người cụ thể nhận, phiên chưa bắt đầu, chưa kết thúc. |
| `delete_pending` | query | bool | không | — | Phiếu đang có yêu cầu xoá chờ duyệt. |
| `limit` | query | int | không | 50 | |
| `offset` | query | int | không | 0 | |

Ba cờ `awaiting_pick`, `awaiting_reply`, `delete_pending` được ghép bằng **OR**, không phải AND.

**Kết quả:** `{items: [Case], limit, offset, total}`. Các trường của một Case:
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | `support_cases.id` |
| `case_number` | string | Số phiếu hiển thị (`support_cases.case_number`) |
| `product_item_id` | uuid/"" | Máy của phiếu. Rỗng nếu là phiếu Agent gửi QS, không gắn máy. |
| `machine_of_qs` | bool | Chỉ có ở `GET /{id}`, với người xem là Agent: máy do QS quản lý, tổ chức của Agent không giữ quyền trên máy. |
| `machine_agent_name` | string | Chỉ có ở `GET /{id}`, với nhân viên QS: tên đại lý đang quản lý máy. |
| `customer_organization_id` | uuid | Tổ chức (đại lý) của khách (`support_cases.customer_organization_id`) |
| `created_by` | uuid | Người tạo phiếu (`auth_users.id`) |
| `category`, `priority`, `status` | string | Xem enum ở bảng tham số |
| `support_mode` | string | `video_call` (đặt lịch gọi 1:1) hoặc `chat` |
| `customer_name` | string | Tên **chủ máy hiện tại** (`product_ownerships.is_current` → `customers`, ưu tiên họ tên trong `user_profiles` của tài khoản portal). Nếu phiếu không gắn máy thì là tên tổ chức của người tạo. |
| `customer_id` | uuid | `customers.id` của chủ máy hiện tại |
| `assignee_name` | string | **Tên người đang phụ trách** (bản ghi `support_assignments` có `is_current`; họ + tên, nếu không có thì dùng username) |
| `assignee_org_name` | string | Tên tổ chức Agent đang giữ phiếu |
| `creator_name` | string | Tên người tạo (từ `user_profiles`) |
| `product_name` | string | Tên loại máy (`products.name`) |
| `chat_at` | time | Giờ bắt đầu của lịch hẹn mới nhất chưa bị huỷ |
| `has_open_appointment` | bool | Có lịch hẹn `requested`/`confirmed` |
| `subject`, `description` | string | Tiêu đề, mô tả |
| `reject_reason` | string | Lý do từ chối (khi status = `rejected`) |
| `assigned` | bool | Đã được giao (cho người hoặc tổ chức) |
| `named_assignee` | bool | Đã có người cụ thể nhận phiếu |
| `delete_pending` | bool | Đang chờ duyệt xoá |
| `first_response_at`, `resolved_at`, `closed_at` | time | Mốc phản hồi đầu tiên, giải quyết, đóng phiếu |
| `document_id`, `document_version` | string | Tài liệu manualhub được đính kèm |
| `work_order_id` | uuid | Phiếu công việc tự tạo, chỉ có khi category = `service` |
| `period_started_at` | time | Bắt đầu chu kỳ hiện tại (đặt lại mỗi lần mở lại phiếu) |
| `session_started_at`, `session_ended_at` | time | Phiên hỗ trợ bắt đầu khi nhân viên trả lời công khai hoặc gọi lần đầu. Thời gian hỗ trợ bị trừ tính từ mốc này. |
| `created_at`, `updated_at` | time | |

**Lỗi:** `401 UNAUTHENTICATED`, `500 INTERNAL_ERROR`.

**Ví dụ:**
```
GET /api/v1/support/cases?product_item_id=6b1f...&status=new,in_progress&limit=5
{"items":[{"id":"9c2e...","case_number":"SC-2026-0123","status":"in_progress","priority":"normal",
 "customer_name":"Nguyễn Văn A","customer_id":"1a5f...","assignee_name":"Trần B","product_name":"CNC 3020",
 "subject":"Máy báo lỗi trục Z","created_at":"2026-10-05T02:10:00Z", "...": "..."}],"limit":5,"offset":0,"total":1}
```

**AI dùng khi:** "Khách A có phiếu hỗ trợ nào?" (đi qua từng máy), "Đang có bao nhiêu phiếu chờ?" (`status=new,pending&limit=1` → `total`), "Tôi đang xử lý những phiếu nào?" (`assigned_to_me=true`).

---

#### `GET /support/cases/{id}`
**Chức năng:** Lấy chi tiết một phiếu (bảng `support_cases`, cùng các trường tính sẵn như ở API danh sách).

**Quyền:** `support_case.read`.

**Phạm vi dữ liệu:**
- Áp dụng kiểm tra phạm vi Agent và kiểm tra quyền trên máy như ở phần quy ước chung.
- Khách không có `support_case.view_all` trên máy thì chỉ xem được phiếu mình tạo hoặc đang được giao cho mình.
- **Lưu ý:** nhân viên QS không có scope `ALL` vẫn mở được **bất kỳ** phiếu nào bằng id. Giới hạn "chỉ phiếu được giao" chỉ áp dụng ở API danh sách.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | `support_cases.id` |

**Kết quả:** một Case (cùng bảng trường như trên), có thêm `machine_of_qs` / `machine_agent_name` khi áp dụng.

**Lỗi:** `404 NOT_FOUND`, `403 FORBIDDEN`, `403 PRODUCT_PERMISSION_DENIED`, `401`.

**Ví dụ:** `GET /api/v1/support/cases/9c2e...` → `{"id":"9c2e...","case_number":"SC-2026-0123","status":"in_progress","assignee_name":"Trần B",...}`

**AI dùng khi:** "Phiếu SC-2026-0123 đang ở trạng thái nào, ai đang giữ?" (lấy id bằng `GET /support/cases?keyword=SC-2026-0123` trước).

---

#### `GET /support/cases/{id}/messages`
**Chức năng:** Lấy cuộc trò chuyện của phiếu (bảng `support_messages`). Sắp xếp `created_at` tăng dần (cũ trước), kèm tên người gửi.

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Phạm vi dữ liệu:** quy tắc người phụ trách (theo code của `conversation.authorizeStaffAssignee`).
- **Nhân viên** (có `support_case.read_internal`, và không phải người tạo phiếu) **phải là người đang phụ trách** phiếu. Thành viên tổ chức được giao cũng tính, nếu phiếu chưa có người cụ thể nhận.
- Ngoại lệ: tài khoản scope `ALL`, hoặc agent_admin của tổ chức đang xử lý phiếu, thì được bỏ qua kiểm tra trên. **Nhưng** nếu phiếu đang do **một người cụ thể khác** giữ, vẫn bị `403 FORBIDDEN` ("only the assigned agent may access this conversation").

  → Trong thực tế, người hỏi thường không đọc được tin nhắn của phiếu người khác đang giữ.
- **Không phải nhân viên** (khách) thì không thấy tin `internal_note`. Lưu ý: tin bị lọc **sau** khi phân trang, nên `total` vẫn tính cả tin nội bộ.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | id phiếu |
| `limit` | query | int | không | 50 | |
| `offset` | query | int | không | 0 | Thứ tự cũ → mới, nên muốn lấy tin mới nhất thì `offset = total - limit` |

**Kết quả:** `{items: [Message], limit, offset, total}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id`, `case_id` | uuid | `support_messages.id`, `case_id` |
| `sender_id` | uuid | Người gửi (`support_messages.sender_id`). Rỗng với tin hệ thống. |
| `sender_name` | string | Tên người gửi (đã tính sẵn) |
| `type` | string | `portal` (chat), `email`, `system`, `internal_note` (chỉ nhân viên thấy) |
| `body` | string | Nội dung |
| `translated_body`, `translated_lang`, `translated_source`, `translated_at` | | Bản dịch, nếu có |
| `reply_to_id` | uuid | Tin được trích dẫn |
| `recalled_at` | time | Thời điểm tin bị thu hồi |
| `created_at` | time | |

**Lỗi:** `404 NOT_FOUND` (không có phiếu), `403 FORBIDDEN`, `403 PRODUCT_PERMISSION_DENIED`, `401`.

**Ví dụ:** `GET /api/v1/support/cases/9c2e.../messages?limit=5` → `{"items":[{"sender_name":"Nguyễn Văn A","type":"portal","body":"Máy vẫn báo lỗi","created_at":"..."}],"limit":5,"offset":0,"total":12}`

**AI dùng khi:** "Khách A vừa nhắn gì trong phiếu?", "Tóm tắt cuộc trao đổi của phiếu SC-...".

---

#### `GET /support/cases/{id}/attachments`
**Chức năng:** Liệt kê mọi tệp đính kèm của phiếu (bảng `support_attachments`, tên tệp lấy từ `files`). Gồm cả tệp ở mô tả phiếu và tệp trong từng tin nhắn.

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy + quy tắc người phụ trách (giống `/messages`).

**Tham số:** chỉ có `id` (path). Không phân trang.

**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | id bản ghi `support_attachments` |
| `case_id` | uuid | |
| `message_id` | uuid | Rỗng = tệp ở mô tả phiếu |
| `file_id` | uuid | `files.id` |
| `uploaded_by` | uuid | Người tải lên |
| `created_at` | time | |
| `file_name`, `media_type`, `mime_type`, `size_bytes` | | Thông tin tệp |
| `url`, `preview_url` | string | Đường dẫn tải về (route nhị phân, AI không đọc được nội dung) |

**Lỗi:** như `/messages`.

**Ví dụ:** `GET /api/v1/support/cases/9c2e.../attachments` → `{"items":[{"file_name":"loi.jpg","media_type":"image","size_bytes":20481,...}]}`

**AI dùng khi:** "Khách có gửi ảnh lỗi không?"

---

#### `GET /support/cases/{id}/assignments`
**Chức năng:** **Lịch sử giao phiếu**: ai đã và đang phụ trách (bảng `support_assignments`, tên lấy từ `user_profiles`). Sắp xếp `created_at` giảm dần (mới nhất trước). Đây là API chính để trả lời câu "ai hỗ trợ".

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Phạm vi dữ liệu:** không có quy tắc người phụ trách, nên nhân viên xem được dù không phải người đang giữ phiếu.

**Tham số:** `id` (path, bắt buộc). Không phân trang.

**Kết quả:** `{items: [Assignment]}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | `support_assignments.id` |
| `case_id` | uuid | |
| `assigned_to` | uuid | Nhân viên được giao. Rỗng nếu chỉ giao cho tổ chức. |
| `assigned_to_name` | string | Họ tên nhân viên được giao |
| `support_organization_id` | uuid | Tổ chức Agent được giao |
| `is_current` | bool | `true` = người/tổ chức **đang** giữ phiếu |
| `assigned_by` | uuid | Người thực hiện việc giao (chỉ có id, tra tên bằng `/users/{id}`) |
| `created_at` | time | Thời điểm giao |
| `accepted_at` | time | Thời điểm người được giao bấm nhận |

**Lỗi:** `404 NOT_FOUND`, `403`, `401`.

**Ví dụ:**
```
GET /api/v1/support/cases/9c2e.../assignments
{"items":[{"assigned_to_name":"Trần B","is_current":true,"created_at":"2026-10-05T01:00:00Z","accepted_at":"2026-10-05T01:05:00Z"},
          {"assigned_to_name":"Lê C","is_current":false,"created_at":"2026-10-01T03:00:00Z"}]}
```

**AI dùng khi:** "Khách A được ai hỗ trợ?", "Phiếu này đã qua tay những ai?"

---

#### `GET /support/cases/{id}/events`
**Chức năng:** Dòng thời gian của phiếu: đổi trạng thái, giao, giao lại, chuyển cấp… (bảng `support_case_events`). Tên người thực hiện và người/tổ chức đích đã được tính sẵn. Sắp xếp `created_at` tăng dần.

**Quyền / Phạm vi:** như `/assignments`.

**Tham số:** `id` (path). Không phân trang.

**Kết quả:** `{items: [Event]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `case_id` | uuid | |
| `event_type` | string | `status_changed`, `assigned`, `reassigned`, `unassigned`, `escalated`, `reopened`, `handed_over` |
| `old_value`, `new_value` | string | Giá trị trước/sau (ví dụ status cũ/mới, id người được giao) |
| `actor_id` | uuid | Người thực hiện |
| `actor_name` | string | Tên người thực hiện |
| `target_name` | string | Tên người hoặc tổ chức đích (người được giao) |
| `created_at` | time | |

**Lỗi:** `404`, `403`, `401`.

**Ví dụ:** `{"items":[{"event_type":"assigned","actor_name":"Admin QS","target_name":"Lê C","created_at":"..."},{"event_type":"status_changed","old_value":"new","new_value":"in_progress",...}]}`

**AI dùng khi:** "Phiếu này được chuyển cho ai, lúc nào?", "Ai đóng phiếu?"

---

#### `GET /support/cases/{id}/appointments`
**Chức năng:** Lịch hẹn gọi video 1:1 của phiếu (bảng `support_appointments`). Sắp xếp `start_at_utc` giảm dần.

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | id phiếu |
| `limit` | query | int | không | 50 | |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{items: [Appointment], limit, offset, total}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id`, `case_id`, `product_item_id` | uuid | |
| `customer_user_id` | uuid | Tài khoản portal của khách đặt lịch |
| `customer_name` | string | Chỉ được điền ở `/appointments/pending` |
| `support_user_id` | uuid | **Nhân viên phụ trách cuộc gọi** (chỉ có id, tra tên bằng `/users/{id}`) |
| `support_organization_id` | uuid | Tổ chức Agent phụ trách |
| `start_at_utc`, `end_at_utc` | time | Khung giờ, theo UTC |
| `customer_timezone` | string | Múi giờ của khách |
| `status` | string | `requested` (chờ duyệt), `confirmed`, `cancelled`, `completed`, `no_show` |
| `meeting_url` | string | Link họp |
| `created_at`, `updated_at` | time | |

**Lỗi:** `404 NOT_FOUND` ("case not found"), `403 FORBIDDEN` / `PRODUCT_PERMISSION_DENIED`, `401`.

**Ví dụ:** `{"items":[{"support_user_id":"u-77..","start_at_utc":"2026-10-06T02:00:00Z","end_at_utc":"2026-10-06T03:00:00Z","status":"completed"}],"limit":50,"offset":0,"total":1}`

**AI dùng khi:** "Khi nào gọi hỗ trợ cho khách A, ai gọi?", "Lịch hẹn tiếp theo của phiếu này?"

---

#### `GET /support/cases/{id}/appointments/remaining-balance`
**Chức năng:** Số phút Thời Gian Hỗ Trợ còn lại của máy gắn với phiếu, đọc từ `support_entitlements`.
- Máy chưa có quỹ (chưa kích hoạt) → `0`.
- Phiếu không gắn máy → `-1` (không giới hạn).

**Quyền:** như `/appointments`.

**Tham số:** `id` (path).

**Kết quả:** `{"remaining_minutes": int}`

**Lỗi:** `404`, `403`, `401`.

**Ví dụ:** `GET .../remaining-balance` → `{"remaining_minutes":240}`

**AI dùng khi:** "Phiếu này còn bao nhiêu phút hỗ trợ?"

---

#### `GET /support/cases/{id}/time`
**Chức năng:** Các lần ghi nhận thời gian hỗ trợ của phiếu (bảng `support_time_entries`). Sắp xếp `occurred_at` giảm dần.

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Tham số:** `id` (path); `limit` (mặc định 50); `offset` (mặc định 0).

**Kết quả:** `{items: [TimeEntry], limit, offset, total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `case_id` | uuid | |
| `appointment_id` | uuid | Lịch hẹn liên quan |
| `source` | string | `one_to_one`, `portal_message`, `email`, `remote_support`, `internal` |
| `duration_minutes` | int | Số phút. Là giá trị đặc biệt khi bộ đếm đang chạy. |
| `running` | bool | `true` = bộ đếm đang chạy, khi đó `duration_minutes` chưa có ý nghĩa |
| `occurred_at` | time | Thời điểm diễn ra |
| `created_by` | uuid | Người ghi nhận |
| `created_at` | time | |

**Lỗi:** `404`, `403`, `401`.

**Ví dụ:** `{"items":[{"source":"one_to_one","duration_minutes":45,"running":false,"occurred_at":"..."}],"limit":50,"offset":0,"total":1}`

**AI dùng khi:** "Phiếu này đã hỗ trợ bao lâu?"

---

#### `GET /support/cases/{id}/rating`
**Chức năng:** Đánh giá **mới nhất** của khách cho phiếu (bảng `support_ratings`).

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Tham số:** `id` (path).

**Kết quả:** một Rating. **Nếu chưa có đánh giá thì trả 200 với body rỗng.**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `case_id` | uuid | |
| `score` | int | 1–5. Từ 2 trở xuống được coi là đánh giá thấp. |
| `comment` | string | Nhận xét |
| `created_by` | uuid | Người đánh giá |
| `created_at` | time | |

Cột `resolution` và `product_item_id` có trong bảng nhưng **không** được trả về.

**Lỗi:** `404`, `403`, `401`.

**Ví dụ:** `{"id":"r1..","case_id":"9c2e..","score":5,"comment":"Hỗ trợ nhanh","created_at":"..."}`

**AI dùng khi:** "Khách A đánh giá phiếu thế nào?"

#### `GET /support/cases/{id}/ratings`
**Chức năng:** Toàn bộ các lần đánh giá của phiếu, mới nhất trước. Mỗi chu kỳ mở lại phiếu có một đánh giá.

**Quyền / tham số:** như `/rating`.

**Kết quả:** **mảng JSON trần** `[Rating, ...]`, không bọc trong `items`.

**AI dùng khi:** "Các lần đánh giá trước của phiếu này?"

---

#### `GET /support/cases/{id}/cancel-requests`
**Chức năng:** Các yêu cầu huỷ hoặc xoá phiếu (bảng `support_cancel_requests`), kèm tên người yêu cầu.

**Quyền:** `support_case.read` + `ScopeGuard` + kiểm tra quyền trên máy.

**Tham số:** `id` (path). Không phân trang.

**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `case_id` | uuid | |
| `kind` | string | `cancel` hoặc `delete` |
| `requested_by` | uuid | Người yêu cầu |
| `requested_by_name` | string | Tên người yêu cầu |
| `reason` | string | Lý do |
| `status` | string | `pending`, `approved`, `rejected` |
| `reviewed_by` | uuid | Người duyệt |
| `reviewed_at` | time | Thời điểm duyệt |
| `created_at`, `updated_at` | time | |

**Lỗi:** `404`, `403`, `401`.

**Ví dụ:** `{"items":[{"kind":"cancel","requested_by_name":"Nguyễn Văn A","reason":"Đã tự sửa được","status":"pending"}]}`

**AI dùng khi:** "Phiếu này có ai xin huỷ không?"

---

#### `GET /support/appointments/{id}`
**Chức năng:** Lấy một lịch hẹn theo **id lịch hẹn** (bảng `support_appointments`).

**Quyền:** `support_case.read`. Route không gắn `ScopeGuard`, **nhưng handler tự kiểm tra** `CaseInAgentScope` trên phiếu của lịch hẹn và kiểm tra quyền trên máy. Như vậy phạm vi tương đương các route có `ScopeGuard`. (Ghi chú trong CLAUDE.md nói route này không được bảo vệ là đã cũ so với code hiện tại.)

**Tham số:** `id` (path, id lịch hẹn).

**Kết quả:** một Appointment (các trường như ở `/support/cases/{id}/appointments`).

**Lỗi:** `404 NOT_FOUND` (không có lịch hẹn hoặc phiếu), `403`, `401`.

**AI dùng khi:** ít dùng. Thường đã có dữ liệu từ `/support/cases/{id}/appointments`.

---

#### `GET /support/appointments/pending`
**Chức năng:** Hàng đợi lịch hẹn **chờ duyệt** (`status = requested`) của các phiếu chưa đóng, trên mọi phiếu. Mặc định bỏ các phiếu đang được giao cho tổ chức Agent. Có điền `customer_name`.

**Quyền:** `support_case.assign`.

**Phạm vi dữ liệu:**
- Tài khoản Agent không phải agent_admin → danh sách rỗng.
- agent_admin → lấy tối đa 500 lịch hẹn rồi lọc theo phạm vi tổ chức. Khi đó **bỏ qua** `limit`/`offset`, và `total` = số dòng sau khi lọc.

**Tham số:** `limit` (mặc định **100**), `offset` (mặc định 0).

**Kết quả:** `{items: [Appointment + customer_name], limit, offset, total}`

**Lỗi:** `401`, `500`.

**Ví dụ:** `GET /api/v1/support/appointments/pending?limit=10` → `{"items":[{"customer_name":"Nguyễn Văn A","status":"requested","start_at_utc":"..."}],"limit":10,"offset":0,"total":3}`

**AI dùng khi:** "Có bao nhiêu lịch hẹn đang chờ duyệt?"

---

#### `GET /support/appointments/availability`
**Chức năng:** Kiểm tra một nhân viên có **rảnh** trong khoảng thời gian cho trước không. Chỉ xét trùng với các lịch hẹn `requested`/`confirmed` của nhân viên đó.

**Quyền:** `support_case.read`. Không lọc theo phạm vi.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `support_user_id` | query | uuid | có | — | Nhân viên cần kiểm tra |
| `start_at` | query | RFC3339 | có | — | Ví dụ `2026-11-05T09:00:00+07:00` |
| `end_at` | query | RFC3339 | có | — | |

**Kết quả:** `{"available": bool}`

**Lỗi:** `400 INVALID_INPUT` (thiếu tham số hoặc sai định dạng thời gian), `401`.

**AI dùng khi:** "Anh B chiều mai 2–3h có rảnh không?"

---

#### `GET /support/appointments/customer-conflict`
**Chức năng:** Kiểm tra **chính người gọi** (khách) đã có lịch hẹn `requested`/`confirmed` trùng khung giờ trên một phiếu chưa kết thúc hay chưa. Dùng cho form tạo phiếu.

**Quyền:** `support_case.create`.

**Tham số:** `start_at`, `end_at` (query, RFC3339, bắt buộc).

**Kết quả:** `{"conflict": bool}`

**Lỗi:** `400 INVALID_INPUT`, `401`.

**AI dùng khi:** hầu như không dùng, vì chỉ có ý nghĩa với tài khoản khách.

---

#### `GET /products/{productId}/support-entitlement`
**Chức năng:** Quỹ Thời Gian Hỗ Trợ và quỹ tin nhắn của **một máy** (bảng `support_entitlements`, mỗi máy một dòng). **`{productId}` là `product_items.id`**, không phải id của loại máy.

**Quyền:** `support_case.read` + `ApplyScope`.

**Phạm vi dữ liệu:** chỉ data scope `SELF` (khách) bị kiểm tra quyền trên máy. Các scope khác **không** bị lọc theo tổ chức.

**Tham số:** `productId` (path, id của product_item).

**Kết quả:**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `support_entitlements.id` |
| `product_item_id` | uuid | |
| `included_minutes` | int | Tổng số phút được cấp |
| `used_minutes` | int | Số phút đã dùng |
| `remaining_minutes` | int | Số phút còn lại (tính từ hai cột trên) |
| `included_messages` | int | Số tin nhắn được cấp |
| `used_messages` | int | Số tin đã dùng |
| `remaining_messages` | int | Số tin còn lại |
| `created_at`, `updated_at` | time | |

**Lỗi:** `404 NOT_FOUND` (máy chưa có quỹ, thường là chưa kích hoạt), `403 FORBIDDEN`, `401`.

**Ví dụ:** `GET /api/v1/products/6b1f.../support-entitlement` → `{"included_minutes":600,"used_minutes":120,"remaining_minutes":480,"included_messages":50,"used_messages":3,"remaining_messages":47,...}`

**AI dùng khi:** "Máy của khách A còn bao nhiêu giờ hỗ trợ?"

---

#### `GET /support/products/{productId}/entitlement/transactions`
**Chức năng:** Lịch sử cộng/trừ quỹ hỗ trợ của máy (bảng `support_entitlement_transactions`). Sắp xếp `created_at` giảm dần. `{productId}` là `product_items.id`.

**Quyền / Phạm vi:** như `/support-entitlement`.

**Tham số:** `productId` (path); `limit` (mặc định 50); `offset` (mặc định 0).

**Kết quả:** `{items: [...], limit, offset, total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id`, `entitlement_id` | uuid | |
| `case_id` | uuid | Phiếu gây ra giao dịch, nếu có |
| `time_entry_id` | uuid | Lần ghi nhận thời gian liên quan |
| `type` | string | `initial_grant` (cấp ban đầu), `consume` (trừ khi đóng phiếu), `refund`, `adjustment` (điều chỉnh tay) |
| `kind` | string | `minutes` hoặc `messages` |
| `delta_minutes`, `balance_after_minutes` | int | Số phút thay đổi, số dư sau giao dịch |
| `delta_messages`, `balance_after_messages` | int | Số tin thay đổi, số dư sau giao dịch |
| `description` | string | Ghi chú |
| `created_by` | uuid | Người thực hiện |
| `created_at` | time | |

**Lỗi:** `404 NOT_FOUND`, `403`, `401`.

**AI dùng khi:** "Vì sao giờ hỗ trợ của máy X bị trừ?", "Ai đã cộng thêm giờ cho máy X?"

---

#### `GET /support/waiting-messages`
**Chức năng:** Danh sách luồng "Hộp thư chờ" (bảng `support_waiting_messages`, nối thêm `user_profiles`, `auth_users`, `product_items`, `products`, `customers`). Sắp xếp `created_at` giảm dần.

**Quyền:** `waiting_message.read`.

**Phạm vi dữ liệu:**
- **Khách** (không có `waiting_message.handle`): chỉ thấy luồng của chính mình, trừ luồng đã tự xoá.
- **Nhân viên:**
  - Scope khác `ALL` → chỉ thấy luồng của khách thuộc các tổ chức mình được truy cập và **chưa được chuyển lên QS**.
  - Scope `ALL` → ẩn các luồng của khách thuộc tổ chức Agent mà chưa được chuyển lên QS.
  - Người **không** có `waiting_message.assign` → chỉ thấy luồng **được giao cho mình** hoặc luồng mình được mời vào hỗ trợ (helper).
  - Ẩn các luồng phía nhân viên đã xoá.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | query | string | không | (tất cả) | `waiting` (chờ xử lý) hoặc `handled` (đã xử lý) |
| `created_by` | query | uuid | không | — | Chỉ có tác dụng với nhân viên: lọc theo `support_waiting_messages.customer_id`. Đây là **`auth_users.id` của tài khoản khách**, **không phải** `customers.id`. |
| `limit` | query | int | không | 20 | Từ 1 đến 100. Ngoài khoảng này thì dùng 20. |
| `offset` | query | int | không | 0 | |

**Không có tham số tìm kiếm theo từ khoá.** (`q` chỉ có ở `/recipients`.)

**Kết quả:** `{items: [WaitingMessage], total}`
| Trường | Kiểu | Ý nghĩa (nguồn) |
|---|---|---|
| `id` | uuid | |
| `product_item_id` | uuid | Máy liên quan |
| `created_by` | uuid | Người viết tin đầu tiên |
| `customer_id` | uuid | **Tài khoản portal (`auth_users.id`)** của khách sở hữu luồng |
| `author_name` | string | Người viết tin đầu tiên |
| `initiated_by_staff` | bool | `true` nếu nhân viên mở luồng |
| `creator_name` | string | Tên khách |
| `creator_avatar_url`, `creator_phone` | string | Ảnh đại diện, SĐT của khách. **Lưu ý: không bị ẩn với AI** vì tên trường khác `phone`/`avatar_url`. |
| `product_code`, `product_name` | string | Serial máy, tên loại máy |
| `title`, `content` | string | Tiêu đề, nội dung tin đầu tiên |
| `status` | string | `waiting` hoặc `handled` |
| `handled_by`, `handled_at` | uuid, time | **Người xử lý xong** và thời điểm |
| `assigned_to` | uuid | Người được giao |
| `assignee_name` | string | **Tên người được giao** |
| `escalated_at`, `escalated_from` | time, string | Thời điểm và tổ chức Agent chuyển luồng lên QS |
| `helpers` | `[{user_id, name, avatar_url (bị ẩn với AI)}]` | Nhân viên được mời vào hỗ trợ cùng. Chỉ có ở `GET /{id}`. |
| `staff_unread`, `staff_new`, `assigned_unseen` | bool | Trạng thái đã đọc, tính theo nhân viên đang xem |
| `machine_of_qs`, `machine_agent_name` | | Máy do QS quản lý, hoặc tên đại lý quản lý máy |
| `customer_unread` | bool | Khách chưa đọc câu trả lời |
| `awaiting_reply` | bool | Khách là người nói sau cùng, đang chờ trả lời |
| `created_at` | time | |

**Lỗi:** `403` (chưa xác thực), `500`. Body có dạng `{"error": "..."}`.

**Ví dụ:** `GET /api/v1/support/waiting-messages?status=waiting&limit=10` → `{"items":[{"creator_name":"Nguyễn Văn A","product_code":"QS-001","title":"Hỏi cách hiệu chỉnh","status":"waiting","assignee_name":"Trần B"}],"total":4}`

**AI dùng khi:** "Hộp thư chờ còn bao nhiêu tin chưa xử lý?" (`status=waiting&limit=1` → `total`), "Ai đang xử lý tin của khách A?" (lấy id tài khoản qua `/senders` rồi dùng `created_by=`).

---

#### `GET /support/waiting-messages/count`
**Chức năng:** Số đếm trên badge: số **tin nhắn** (không phải số luồng) của khách còn chờ trả lời, cộng thêm các luồng người gọi đã đánh dấu chưa đọc.

**Quyền:** `waiting_message.handle`.

**Phạm vi dữ liệu:** như phạm vi của nhân viên ở `/support/waiting-messages`.

**Tham số:** không có.

**Kết quả:** `{"count": int}`

**AI dùng khi:** "Tôi còn bao nhiêu tin chờ phải xử lý?"

#### `GET /support/waiting-messages/unread`
**Chức năng:** Danh sách các tin mà `/count` đếm (dùng cho chuông thông báo "cần xử lý").

**Quyền:** `waiting_message.handle`.

**Phạm vi:** như `/count`.

**Tham số:** `limit` (mặc định 5, từ 1 đến 20).

**Kết quả:** `{items: [WaitingMessage], total}`

**AI dùng khi:** "Những tin nào đang chờ tôi?"

---

#### `GET /support/waiting-messages/senders`
**Chức năng:** Bảng tổng hợp theo **người gửi**: mỗi khách đã nhắn bao nhiêu tin, còn chờ bao nhiêu, chưa đọc bao nhiêu. Sắp xếp theo chưa đọc, rồi đang chờ, rồi tin gần nhất.

**Quyền:** `waiting_message.handle`. Người không phải nhân viên → `403`.

**Phạm vi:** như phạm vi của nhân viên ở `/support/waiting-messages`.

**Tham số:** `only_waiting=true` (chỉ lấy người còn tin chờ); `limit` (mặc định 20, từ 1 đến 100); `offset`.

**Kết quả:** `{items: [...], total}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `user_id` | uuid | `auth_users.id` của khách. **Dùng giá trị này cho `created_by` ở `/support/waiting-messages`.** |
| `name` | string | Tên khách |
| `phone` | string | (bị ẩn với AI) |
| `avatar_url` | string | (bị ẩn với AI) |
| `waiting_count` | int | Số luồng đang chờ |
| `unread_count` | int | Số luồng chưa đọc |
| `total_count` | int | Tổng số luồng |
| `last_message_at` | time | Thời điểm tin gần nhất |

**AI dùng khi:** "Khách nào đang chờ trả lời nhiều nhất?", hoặc để tìm `user_id` của khách A trong hộp thư chờ.

---

#### `GET /support/waiting-messages/recipients`
**Chức năng:** Danh sách tài khoản khách (role `customer`, đang hoạt động) mà nhân viên có thể nhắn tới, trong phạm vi tổ chức của mình.

**Quyền:** `waiting_message.handle`.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `q` | query | string | không | — | ILIKE theo tên, SĐT hoặc email |
| `limit` | query | int | không | 20 | Từ 1 đến 500 |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{items: [{user_id, name, phone (bị ẩn với AI), avatar_url (bị ẩn với AI)}], total}`

**AI dùng khi:** để tìm `auth_users.id` của khách theo tên hoặc SĐT, rồi dùng cho `created_by` ở `/support/waiting-messages`.

---

#### `GET /support/waiting-messages/{id}`
**Chức năng:** Chi tiết một luồng, có thêm danh sách `helpers`.

> ⚠ **Có tác dụng phụ:** API này **đánh dấu luồng là đã xem** cho người gọi (`MarkSeen`). Vì vậy AI gọi API này sẽ làm mất trạng thái "chưa đọc" của người dùng. Nên ưu tiên dùng `/support/waiting-messages` để đọc.

**Quyền:** `waiting_message.read`.

**Phạm vi dữ liệu:** người gọi phải là khách sở hữu luồng, **hoặc** là nhân viên thoả cả ba điều kiện:
- có `waiting_message.handle`;
- luồng nằm trong phạm vi tổ chức của mình (khi scope khác `ALL`);
- luồng được giao cho mình, hoặc mình là helper, hoặc mình có `waiting_message.assign`.

Luồng đã bị phía người gọi xoá → `404`.

**Tham số:** `id` (path).

**Kết quả:** một WaitingMessage (các trường như ở API danh sách, có thêm `helpers`).

**Lỗi:** `404`, `403`.

#### `GET /support/waiting-messages/{id}/history`
**Chức năng:** Lịch sử xử lý của luồng (bảng `support_waiting_message_events`): ai tạo, giao cho ai, ai xử lý, chuyển cấp, thêm/bớt người hỗ trợ.

**Quyền / Phạm vi:** như `/{id}`, nhưng **không** đánh dấu đã xem.

**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `type` | string | `created`, `created_by_staff`, `assigned`, `session_started`, `handled`, `reopened`, `escalated`, `helper_added`, `helper_removed` |
| `actor_id`, `actor_name` | | Người thực hiện |
| `target_id`, `target_name` | | Người đích (người được giao, người hỗ trợ được thêm/bớt) |
| `created_at` | time | |

**AI dùng khi:** "Tin của khách A được giao cho ai, ai xử lý xong?"

#### `GET /support/waiting-messages/{id}/replies`
**Chức năng:** Các câu trả lời trong luồng (bảng `support_waiting_message_replies`) cùng tệp đính kèm. Câu trả lời đã thu hồi có `content` rỗng.

**Quyền / Phạm vi:** như `/{id}`, không đánh dấu đã xem.

**Kết quả:** `{items: [...]}`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | |
| `author_id`, `author_name` | | Người trả lời |
| `author_avatar_url` | string | Ảnh đại diện |
| `content` | string | Nội dung |
| `created_at` | time | |
| `files` | `[{id, media_type, file_name, mime_type, size_bytes, display_order, visibility, url, preview_url}]` | Tệp đính kèm |
| `reply_to_id` | uuid | Câu được trích dẫn |
| `recalled_at` | time | Thời điểm thu hồi |

**AI dùng khi:** "Nhân viên đã trả lời khách A những gì?"

#### `GET /support/waiting-messages/{id}/files`
**Chức năng:** Tệp đính kèm của tin đầu tiên trong luồng.

**Quyền / Phạm vi:** như `/{id}`.

**Kết quả:** `{items: [{id, media_type, file_name, mime_type, size_bytes, display_order, visibility, url, preview_url}]}`

---

#### `GET /settings/support-quota`
**Chức năng:** Cho biết cơ chế trừ Thời Gian Hỗ Trợ có đang **bật** không (cấu hình hệ thống trong `app_settings`).

**Quyền:** `support_case.entitlement_adjust`.

**Tham số:** không có.

**Kết quả:** `{"enabled": bool}`

#### `GET /settings/waiting-message-quota`
**Chức năng:** Cho biết giới hạn số tin nhắn của hộp thư chờ có đang bật không.

**Quyền:** `support_case.entitlement_adjust`.

**Kết quả:** `{"enabled": bool}`

#### `GET /settings/appointment-reminder`
**Chức năng:** Số phút nhắc trước giờ hẹn gọi 1:1 (từ 1 đến 1440).

**Quyền:** `support_case.entitlement_adjust`.

**Kết quả:** `{"minutes": int}`

**AI dùng khi (cả ba API settings):** "Hệ thống có đang trừ giờ hỗ trợ không?", "Nhắc lịch hẹn trước bao nhiêu phút?"

---

#### Chuỗi gọi mẫu: "Khách A được hỗ trợ bởi ai?"
1. `GET /customers?keyword=A` → lấy `customer_id`.
2. `GET /product-items?customer_id=…` → lấy danh sách máy.
3. Với từng máy: `GET /support/cases?product_item_id=…` → `assignee_name` cho biết người đang phụ trách.

   Lưu ý: nhân viên QS không có scope `ALL` chỉ thấy phiếu được giao cho mình, nên danh sách có thể thiếu.
4. Với từng phiếu: `GET /support/cases/{id}/assignments` → toàn bộ người đã và đang phụ trách, kèm `accepted_at`.
5. Bổ sung:
   - `GET /support/cases/{id}/appointments` → `support_user_id` là người gọi video.
   - Hộp thư chờ: `GET /support/waiting-messages/recipients?q=<tên/SĐT>` → `user_id` → `GET /support/waiting-messages?created_by=<user_id>` → `assignee_name` / `handled_by`.

### 3.4 Kỹ thuật, tài liệu và AI tools

Quy ước chung cho cả nhóm:
- Base URL: `/api/v1`. Mọi route cần `Authorization: Bearer <JWT>` (middleware `Authenticate`).
- Lỗi luôn có dạng `{ "error": "...", "code": "..." }`. Nếu thiếu token hoặc token sai thì trả **401**; thiếu permission thì trả **403** (do middleware `Authorize` chặn).
- **Chưa có AI tool nào** bọc các API trong nhóm D.1–D.3. AI chỉ gọi được chúng nếu có thêm tool trong `internal/platform/aitools/tools.go`. Khi bọc, các trường có tên nằm trong `hiddenFields` sẽ bị bỏ, và chuỗi dài hơn 800 ký tự sẽ bị cắt. Hiện **không có trường nào** của nhóm D trùng tên với `hiddenFields`. Riêng `internal_notes` và `customer_notes` của service log **không** bị ẩn, nên cần cân nhắc thêm vào `hiddenFields` trước khi bọc.

---


#### D.1 Nhật ký dịch vụ (service logs)

#### `GET /service-logs`
**Chức năng:** Liệt kê nhật ký dịch vụ của máy (`service_logs`): lắp đặt, bảo trì, sửa chữa, kiểm tra, ghi chú, và các sự kiện hệ thống tự ghi khi phiếu công việc thay đổi. Sắp xếp `service_date DESC`.
**Quyền:** `service_log.read`.
**Phạm vi dữ liệu:** **Không lọc theo scope.** Ai có quyền `service_log.read` đều thấy mọi bản ghi khớp bộ lọc.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `product_item_id` | query | uuid | không | — | Lọc theo máy |
| `work_order_id` | query | uuid | không | — | Lọc theo phiếu công việc |
| `technician_id` | query | uuid | không | — | Lọc theo kỹ thuật viên |
| `service_type` | query | string | không | — | `installation` \| `maintenance` \| `repair` \| `inspection` \| `note` \| `event` |
| `limit` | query | int | không | 50 | Không có giới hạn trên |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ items: ServiceLog[], limit, offset, total }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `service_logs.id` |
| `product_item_id` | uuid | Máy |
| `work_order_id` | uuid? | Phiếu công việc liên quan |
| `service_date` | datetime | Ngày thực hiện |
| `service_type` | string | Loại dịch vụ (xem enum ở trên) |
| `issue_description` | string | Mô tả sự cố |
| `action_taken` | string | Việc đã làm |
| `parts_replaced[]` | array | `{part_name, quantity, part_code}`: linh kiện đã thay |
| `technician_id` | uuid? | Kỹ thuật viên |
| `technician_name` | string | Tên kỹ thuật viên (resolve từ `user_profiles`) |
| `customer_notes` | string | Ghi chú gửi khách (**không** bị ẩn với AI) |
| `internal_notes` | string | Ghi chú nội bộ (**không** bị ẩn với AI, nên ẩn) |
| `source_comment_id` | uuid? | Có giá trị khi bản ghi được sao từ một bình luận của phiếu công việc |
| `event_type` | string? | Sự kiện hệ thống: `created`, `assigned`, `unassigned`, `reassigned`, `started`, `completed`, `reopened`, `cancelled`, `attachment_added`, `attachment_removed` |
| `event_metadata` | object? | Dữ liệu đi kèm sự kiện (ví dụ người cũ → người mới) |
| `created_at` / `updated_at` | datetime | |

**Lỗi:** 401/403, 500.
**Ví dụ:**
```
GET /api/v1/service-logs?product_item_id=7c1e..&service_type=repair
→ {"items":[{"id":"s1..","service_date":"2026-10-12T00:00:00Z","service_type":"repair","issue_description":"Lỗi trục X","action_taken":"Thay driver","parts_replaced":[{"part_name":"Driver","quantity":1}],"technician_name":"Trần B"}],"limit":50,"offset":0,"total":1}
```
**AI dùng khi:** "Máy QS-001 đã thay linh kiện gì?", "Kỹ thuật viên B tháng này sửa bao nhiêu máy?", "Lần bảo trì gần nhất của máy này là khi nào?"

#### `GET /service-logs/{id}`
**Chức năng:** Lấy chi tiết một bản ghi nhật ký dịch vụ.
**Quyền:** `service_log.read`. **Phạm vi dữ liệu:** không lọc theo scope.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** một object ServiceLog (các trường như trên).
**Lỗi:** 400 `BAD_REQUEST` (thiếu id), 404 `NOT_FOUND` ("service log not found"), 401/403, 500.
**Ví dụ:** `GET /api/v1/service-logs/s1..` → `{"id":"s1..","service_type":"repair",...}`
**AI dùng khi:** cần xem đầy đủ một mục nhật ký đã thấy trong danh sách.

---

#### D.2 Báo lỗi máy (issue reports)

#### `GET /product-items/{id}/issue-reports`
**Chức năng:** Liệt kê các báo lỗi do khách hoặc nhân viên gửi cho một máy (`issue_reports`), sắp xếp `created_at DESC`.
**Quyền:** `issue_report.read`.
**Phạm vi dữ liệu:**
- Route **không** kiểm tra người gọi có liên quan tới máy hay không. Ai có quyền `issue_report.read` và id máy là đọc được.
- Trường `can_review` cho biết người gọi có được "Đã xem" / "Chuyển thành Case" hay không (chủ máy, kỹ thuật viên, hoặc QS).

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | path | uuid | có | — | Id **máy** (`product_items.id`) |

Không nhận `limit`/`offset`: server cố định **100 dòng mới nhất**. `total` vẫn là tổng thật.

**Kết quả:** `{ items: IssueReport[], limit: 100, offset: 0, total }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `issue_reports.id` |
| `product_item_id` | uuid | Máy |
| `reporter_id` / `reporter_name` | uuid / string | Người báo lỗi |
| `category` | string | `alarm` \| `parameter` \| `hardware` \| `other` |
| `severity` | string | `normal` \| `urgent` |
| `alarm_code` | string | Mã báo động của máy (nếu có) |
| `description` | string | Mô tả lỗi |
| `status` | string | `open` (mới) \| `reviewed` (đã xem) \| `converted` (đã chuyển thành phiếu hỗ trợ) |
| `reviewed_by` / `reviewed_at` | uuid? / datetime? | Ai đã xem, lúc nào |
| `converted_case_id` | uuid? | Phiếu hỗ trợ 1:1 được tạo từ báo lỗi (`support_cases.id`) |
| `created_at` / `updated_at` | datetime | |
| `can_review` | bool? | Người gọi có được xử lý báo lỗi không |

**Lỗi:** 401/403, 500.
**Ví dụ:** `GET /api/v1/product-items/7c1e../issue-reports` → `{"items":[{"id":"i1..","reporter_name":"Nguyễn Văn A","category":"alarm","severity":"urgent","alarm_code":"E05","description":"Máy báo lỗi E05","status":"converted","converted_case_id":"S1..","can_review":true}],"limit":100,"offset":0,"total":1}`
**AI dùng khi:** "Máy của khách A báo lỗi gì?", "Lỗi E05 đã được chuyển thành phiếu hỗ trợ chưa?"

#### `GET /my/issue-reports`
**Chức năng:** Liệt kê các báo lỗi do **chính người gọi** gửi, trên mọi máy. Đây là "Lịch sử báo lỗi" trên portal.
**Quyền:** `issue_report.read`. **Phạm vi dữ liệu:** chỉ lấy bản ghi có `reporter_id` = người gọi.
**Tham số:** không có. Server cố định 100 dòng mới nhất.
**Kết quả:** giống route trên, nhưng **không** có `can_review`.
**Lỗi:** 401 `UNAUTHENTICATED`, 403, 500.
**Ví dụ:** `GET /api/v1/my/issue-reports` → `{"items":[...],"limit":100,"offset":0,"total":3}`
**AI dùng khi:** "Tôi đã báo những lỗi nào?"

#### `GET /issue-reports/{id}`
**Chức năng:** Lấy chi tiết một báo lỗi.
**Quyền:** `issue_report.read`. **Phạm vi dữ liệu:** route **không** gọi `CanView`, nên ai có quyền và id là đọc được.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** một object IssueReport (không có `can_review`).
**Lỗi:** 404 `NOT_FOUND`, 401/403, 500.
**Ví dụ:** `GET /api/v1/issue-reports/i1..` → `{"id":"i1..","status":"open",...}`
**AI dùng khi:** xem đầy đủ một báo lỗi đã tìm thấy trong danh sách.

#### `GET /issue-reports/{id}/attachments`
**Chức năng:** Liệt kê ảnh / video / file đính kèm của một báo lỗi.
**Quyền:** `issue_report.read`.
**Phạm vi dữ liệu:** có kiểm tra `CanView`. Chỉ người báo lỗi, người có vai trò trên máy (`product_user_access`), hoặc người có quyền xử lý (chủ máy / kỹ thuật viên / QS) mới xem được. Người khác nhận 404, như thể báo lỗi không tồn tại.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** `{ items: Attachment[] }` với các trường `id, media_type, file_name, mime_type, size_bytes, display_order, visibility, url, preview_url`. Nếu server chưa cấu hình file service thì trả `items: []`.
**Lỗi:** 401, 404 (không tìm thấy hoặc không có quyền xem), 403, 500.
**AI dùng khi:** "Khách có gửi ảnh lỗi không?" (AI chỉ đọc được tên và loại file, không đọc nội dung file).

---

#### D.3 Tài liệu kỹ thuật sản phẩm (ManualHub)

Tài liệu ManualHub luôn gắn với **một loại sản phẩm** (`product_id`). Trạng thái của tài liệu (`status`):

| Giá trị | Ý nghĩa |
|---|---|
| `draft` | Bản nháp |
| `review` | Đang chờ duyệt |
| `released` | Đã phát hành |
| `rejected` | Bị từ chối |
| `hidden` | Đã ẩn |
| `pending_delete` | Đang chờ duyệt xoá |

- Một tài liệu có nhiều phiên bản (lineage). `is_current = true` là bản đang dùng.
- Bản tiếng Việt và tiếng Anh của cùng một tài liệu được ghép cặp qua `document_group_id`.
- Quyền đọc chung cho các route ManualHub: **bất kỳ một** trong các quyền `manual.read`, `companydoc.read`, `companydoc.read.website`, `companydoc.create(.website)`, `companydoc.update(.website)`, `companydoc.delete(.website)` (middleware `AuthorizeAny`).

#### `GET /manualhub/documents`
**Chức năng:** Liệt kê tài liệu kỹ thuật (`manualhub_documents` JOIN `products`), sắp xếp `created_at DESC`. Tài liệu của sản phẩm đã xoá mềm bị loại.
**Quyền:** xem danh sách quyền đọc chung ở trên.
**Phạm vi dữ liệu:**
- Người **không** có `manual.publish` mà lọc theo `status` = `draft`, `review` hoặc `rejected` thì server **ép** chỉ trả tài liệu của chính họ.
- `released`, `hidden` và `pending_delete` thì ai có quyền đọc cũng thấy.
- **Lưu ý:** nếu không truyền `status` thì không có bộ lọc tác giả, nên danh sách gồm cả bản nháp của người khác. Đây là hành vi theo code hiện tại.

**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `keyword` | query | string | không | — | Tìm trong **tiêu đề**, không phân biệt dấu |
| `status` | query | string | không | — | 1 giá trị trong bảng trạng thái ở trên |
| `product_id` | query | uuid | không | — | Lọc theo loại sản phẩm (`products.id`) |
| `parent_id` | query | uuid | không | — | Các phiên bản sinh ra từ một tài liệu |
| `group_id` | query | uuid | không | — | Cặp VI/EN (`document_group_id`) |
| `mine` | query | `true` | không | — | Chỉ tài liệu do mình viết |
| `limit` | query | int | không | **20** | |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ items: Document[], limit, offset, total }`
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `manualhub_documents.id` |
| `parent_id` | uuid? | Phiên bản trước |
| `document_group_id` | uuid? | Ghép cặp VI/EN |
| `product_id` / `product_name` | uuid / string | Loại sản phẩm |
| `title` / `description` | string | Tiêu đề / mô tả |
| `document_type` | string | Loại tài liệu (chữ tự do, ví dụ "Hướng dẫn sử dụng") |
| `connection_types[]` | string[] | Chuẩn kết nối của bộ điều khiển ("EtherCAT", "Pulse train"…) |
| `format` | string | Định dạng nội dung / file |
| `view_pdf_url` | string | Link xem PDF (có ký) |
| `content` | json | Nội dung tài liệu (có thể lớn) |
| `status` | string | Trạng thái |
| `language` | string | Ngôn ngữ (`vi` / `en`) |
| `version` | string | Số phiên bản |
| `author_id` / `author_name` | | Tác giả |
| `is_current` | bool | Bản đang dùng |
| `file_count` | int | Số file đính kèm |
| `submitted_by_id` / `submitted_by_name` / `submitted_at` | | Ai gửi duyệt, lúc nào |
| `released_at` | datetime? | Ngày phát hành |
| `rejection_reason` | string | Lý do bị từ chối |
| `created_at` / `updated_at` | datetime | |

**Lỗi:** 401/403, 500.
**Ví dụ:** `GET /api/v1/manualhub/documents?product_id=p1..&status=released` → `{"items":[{"id":"d1..","product_name":"CNC 3020","title":"Hướng dẫn lắp đặt","language":"vi","version":"1.2","is_current":true,"status":"released"}],"limit":20,"offset":0,"total":1}`
**AI dùng khi:** "Máy CNC 3020 có tài liệu gì?", "Có hướng dẫn tiếng Anh cho model này không?"

#### `GET /manualhub/documents/{id}`
**Chức năng:** Lấy chi tiết một tài liệu.
**Quyền:** quyền đọc chung.
**Phạm vi dữ liệu:** nếu tài liệu đang `draft` thì chỉ tác giả hoặc người có `manual.publish` xem được. Người khác nhận 404.
**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** một object Document (các trường như trên).
**Lỗi:** 404 `NOT_FOUND`, 401/403, 500.
**AI dùng khi:** cần mô tả hoặc nội dung của một tài liệu cụ thể.

#### `GET /manualhub/documents/{id}/versions`
**Chức năng:** Lịch sử các bản lưu của tài liệu trên **toàn bộ lineage** (`manualhub_document_versions`), mới nhất trước.
**Quyền:** quyền đọc chung. **Phạm vi dữ liệu:** route **không** kiểm tra quyền xem bản nháp.
**Tham số:** `id` (path, bắt buộc).
**Kết quả:** mảng `Version[]` (không bọc `items`):
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | Id bản lưu |
| `document_id` | uuid | Tài liệu |
| `version` | string | Số phiên bản |
| `title` | string | Tiêu đề |
| `format` | string | Định dạng |
| `content` | json | Nội dung |
| `file_url` | string | Link file |
| `created_by_name` | string | Người lưu |
| `created_at` | datetime | |

**Lỗi:** 404, 401/403, 500.
**AI dùng khi:** "Tài liệu này đã có bao nhiêu phiên bản? Ai sửa lần cuối?"

#### `GET /manualhub/documents/{id}/versions/{version}`
**Chức năng:** Lấy một phiên bản cụ thể (tìm trên toàn lineage).
**Quyền:** quyền đọc chung.
**Tham số:** `id` (path, uuid), `version` (path, string, ví dụ `1.2`). Cả hai đều bắt buộc.
**Kết quả:** một object Version.
**Lỗi:** 404 `VERSION_NOT_FOUND`, 404 `NOT_FOUND`, 401/403, 500.
**AI dùng khi:** "Bản 1.0 của tài liệu này viết gì?"

#### `GET /manualhub/documents/{id}/activities`
**Chức năng:** Nhật ký duyệt của một tài liệu (`manualhub_activities`), mới nhất trước. Chỉ gồm các hành động `publish`, `reject`, `rollback`, `delete`, `delete-request`, `delete-reject`.
**Quyền:** quyền đọc chung.
**Tham số:** `id` (path, bắt buộc).
**Kết quả:** mảng `Activity[]`:
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | Id hoạt động |
| `document_id` | uuid | Tài liệu |
| `actor_id` / `actor_name` | | Người thực hiện. Tên lấy từ `user_profiles`, nếu không có thì dùng `username` |
| `action` | string | Hành động (xem danh sách ở trên) |
| `content` | string | Nội dung (ví dụ lý do từ chối) |
| `created_at` | datetime | |

Các trường `document_title`, `document_status`, `product_name`, `language` chỉ có giá trị ở route `/manualhub/activities`.
**Lỗi:** 401/403, 500.
**AI dùng khi:** "Ai đã phát hành tài liệu này?", "Vì sao tài liệu bị từ chối?"

#### `GET /manualhub/activities`
**Chức năng:** Nhật ký duyệt của **tất cả** tài liệu, có phân trang.
**Quyền:** một trong `manual.publish`, `companydoc.publish`, `companydoc.publish.website`.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `limit` | query | int | không | 20 | |
| `offset` | query | int | không | 0 | |

**Kết quả:** `{ items: Activity[], limit, offset, total }`. Có thêm `document_title`, `document_status`, `product_name`, `language`.
**AI dùng khi:** "Tuần này có tài liệu nào được phát hành?"

#### `GET /manualhub/products`
**Chức năng:** Danh sách loại sản phẩm (bản rút gọn), dành cho người không có `product.read`.
**Quyền:** quyền đọc chung.
**Tham số:** không có.
**Kết quả:** `{ items: [{id, code, name}], limit, offset: 0, total }` (`limit` = `total` = số dòng).
**AI dùng khi:** cần tra `product_id` để lọc tài liệu mà người dùng không có quyền `product.read`.

#### `GET /manualhub/stats`
**Chức năng:** Số liệu tổng quan của ManualHub.
**Quyền:** quyền đọc chung.
**Phạm vi dữ liệu:** người không có `manual.publish` chỉ được đếm `drafts` và `waitingReview` của **chính mình**. Người có `manual.publish` nhận số liệu toàn hệ thống.
**Tham số:** không có.
**Kết quả:**
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `released` | int | Số tài liệu đang phát hành. Đếm theo nhóm (sản phẩm, loại tài liệu), nên một cặp VI/EN chỉ tính 1 |
| `drafts` | int | Số bản nháp |
| `waitingReview` | int | Số tài liệu đang chờ duyệt |
| `rejected` | int | Số tài liệu bị từ chối |

**AI dùng khi:** "Có bao nhiêu tài liệu đang chờ duyệt?"

---

#### D.4 Tài liệu công ty (Company Docs)

Tài liệu công ty là một **cây thư mục** (`company_doc_nodes`). Mỗi nút có `node_type` = `folder` (thư mục) hoặc `document` (tài liệu). Các thư mục gốc là Website, Phòng Ban, Dự Án…

- **Trạng thái:** `draft`, `review`, `released`, `pending_delete`, `hidden`, `rejected`.
- **Quyền theo thư mục gốc:** người dùng được một hành động trên một thư mục gốc nếu có quyền chung `companydoc.<hành động>` **hoặc** quyền riêng của thư mục đó `companydoc.<hành động>.<slug tên gốc>`. Ví dụ: `companydoc.read.phong_ban`.
- **Quyền vào route:** `AuthorizeAnyPrefix(companydoc.read)`, nghĩa là có bất kỳ quyền nào bắt đầu bằng `companydoc.read` là vào được route.

#### `GET /company-docs/tree`
**Chức năng:** Trả toàn bộ cây tài liệu mà người gọi được xem.
**Quyền:** `companydoc.read*`.
**Phạm vi dữ liệu:**
- Bỏ hẳn các thư mục gốc mà người gọi không có quyền `read`.
- Nút `draft`/`review` (và cả nhánh con của nó) chỉ hiện với người có quyền xử lý.
- Mỗi tài liệu có nhiều phiên bản chỉ hiện **1 dòng**: người đọc thường thấy bản đã phát hành, người đang sửa hoặc duyệt thấy bản đang làm.

**Tham số:** không có.
**Kết quả:** `{ items: Node[] }`. Mỗi Node có `children[]` lồng nhau.
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | uuid | `company_doc_nodes.id` |
| `parent_id` | uuid? | Thư mục cha |
| `node_type` | string | `folder` \| `document` |
| `name` / `description` | string | Tên / mô tả |
| `file_url` | string | Link file gốc |
| `view_pdf_url` / `download_pdf_url` | string | Link PDF (có ký), rỗng với thư mục |
| `manualhub_view_pdf_url` | string | Link PDF nếu nút liên kết sang ManualHub |
| `sort_order` | int | Thứ tự hiển thị |
| `children` | Node[] | Các nút con |
| `status` | string | Trạng thái |
| `rejection_reason` | string | Lý do bị từ chối |
| `created_by_id` / `created_by_name` | | Người tạo |
| `manualhub_product_id`, `manualhub_document_id`, `manualhub_language`, `manualhub_document_type`, `manualhub_version` | | Các trường có giá trị khi nút trỏ sang tài liệu ManualHub |
| `language` | string? | `vi` \| `en` |
| `document_type` | string? | Loại tài liệu |
| `document_group_id` | uuid? | Ghép cặp VI/EN |
| `connection_types[]` | string[] | Chuẩn kết nối |
| `root_id` | uuid? | Gốc lineage phiên bản |
| `is_current` | bool | Bản đang dùng |
| `version` | string | Số phiên bản |
| `created_at` / `updated_at` | datetime | |
| `file_size` | int | Chỉ có ở route public, ở đây luôn trống |

**Lỗi:** 401/403, 500.
**AI dùng khi:** "Phòng Ban Kỹ thuật có tài liệu gì?", "Tìm quy trình bảo hành" (lấy cây rồi tự lọc theo `name`, vì **không có tham số tìm kiếm**).

#### `GET /company-docs/pending`
**Chức năng:** Danh sách phẳng các nút đang chờ quyết định (`review` hoặc `pending_delete`).
**Quyền:** `companydoc.read*`.
**Phạm vi dữ liệu:**
- Nút `review` hiện với người có quyền `publish` trên thư mục gốc, hoặc với chính tác giả.
- Nút `pending_delete` hiện với người có quyền `delete_approve` trên thư mục gốc, hoặc với chính tác giả.
- Không hiện nút thuộc thư mục gốc mà người gọi không được đọc.

**Tham số:** không có.
**Kết quả:** `{ items: Node[] }` (phẳng, không có `children`).
**AI dùng khi:** "Có tài liệu công ty nào đang chờ tôi duyệt?"

#### `GET /company-docs/drafts`
**Chức năng:** Danh sách phẳng các bản nháp (`draft`).
**Quyền:** `companydoc.read*`.
**Phạm vi dữ liệu:** bản nháp hiện với chính tác giả, hoặc với người có quyền `publish` trên thư mục gốc.
**Tham số:** không có.
**Kết quả:** `{ items: Node[] }`.
**AI dùng khi:** "Tôi còn bản nháp nào chưa gửi?"

#### `GET /company-docs/{id}`
**Chức năng:** Lấy chi tiết một nút.
**Quyền:** `companydoc.read*`.
**Phạm vi dữ liệu:**
- Phải có quyền `read` trên thư mục gốc của nút, nếu không thì nhận 404.
- Tài liệu chưa `released` chỉ xem được khi có quyền `update`, `publish` hoặc `delete_approve` trên thư mục gốc, nếu không thì nhận 404.

**Tham số:** `id` (path, uuid, bắt buộc).
**Kết quả:** một Node (không có `children`).
**Lỗi:** 404 `NOT_FOUND`, 401/403, 500.
**AI dùng khi:** xem chi tiết một tài liệu đã thấy trong cây.

#### `GET /company-docs/{id}/versions`
**Chức năng:** Lịch sử các bản lưu (snapshot) khi file của một tài liệu được thay. Mới nhất trước. Trả mảng rỗng nếu file chưa bao giờ bị thay, hoặc nếu nút liên kết sang ManualHub.
**Quyền:** `companydoc.read*` và quyền `read` trên thư mục gốc (nếu không thì nhận 404).
**Tham số:** `id` (path, bắt buộc).
**Kết quả:** mảng `[{id, version (int), name, description, file_url, document_type, language, created_by_name, created_at}]`.
**AI dùng khi:** "File quy trình này đã được thay mấy lần?"

#### `GET /company-docs/{id}/lineage`
**Chức năng:** Mọi phiên bản trong lịch sử sửa của một tài liệu, ở mọi trạng thái (draft, review, released, hidden, rejected). Mới nhất trước.
**Quyền:** `companydoc.read*` và quyền `read` trên thư mục gốc (nếu không thì nhận 404).
**Tham số:** `id` (path, bắt buộc).
**Kết quả:** mảng `Node[]`.
**AI dùng khi:** "Tài liệu này đã qua những bản nào, ai tạo?"

#### `GET /company-docs/{id}/products`
**Chức năng:** Danh sách loại sản phẩm mà một thư mục tài liệu gắn với (`company_doc_node_products`).
**Quyền:** `companydoc.read*`. **Phạm vi dữ liệu:** route **không** kiểm tra quyền theo thư mục gốc.
**Tham số:** `id` (path, id thư mục, bắt buộc).
**Kết quả:** `{ "product_ids": ["uuid", ...] }`. Tra tên bằng `GET /products/{id}` hoặc `GET /manualhub/products`.
**AI dùng khi:** "Thư mục này là tài liệu của máy nào?"

---

#### D.5 AI tools (lớp bọc cho AI)

Mã nguồn ở `internal/platform/aitools/`. Cả hai route đều yêu cầu **đồng thời**:
- Header `X-API-Key`. Key được cấu hình bằng env `AI_TOOLS_API_KEY_INTERNAL` (tier `internal`) và `AI_TOOLS_API_KEY_PUBLIC` (tier `public`). Key được so khớp theo constant-time.
- Header `Authorization: Bearer <JWT của người hỏi>`.

Sau đó request chạy qua middleware `ApplyScope`.

#### `GET /ai/tools`
**Chức năng:** Trả về danh sách tool mà người gọi được dùng, theo định dạng `tools` của OpenAI, nên có thể đưa thẳng vào `chat.completions`.
**Quyền:**
- Chỉ trả những tool mà người gọi có permission tương ứng.
- Với key `public`, chỉ trả các tool có `public: true`. Hiện chưa có tool nào như vậy, nên danh sách rỗng.

**Tham số:** không có (chỉ cần 2 header).
**Kết quả:** `{ "tools": [ { "type": "function", "function": { "name", "description", "parameters" (JSON Schema) } } ] }`

Danh sách tool hiện có:

| Tool | Permission | API gọi bên dưới | Tham số |
|---|---|---|---|
| `search_customers` | customer.read | `GET /customers` | keyword, customer_type, created_at_from, created_at_to, mine, limit |
| `get_customer` | customer.read | `GET /customers/{customer_id}` | customer_id |
| `list_customer_statuses` | customer.read | `GET /customer-statuses` | limit |
| `list_users` | user.read | `GET /users` | keyword, role_code, organization_id, limit |
| `get_customer_activities` | customer.read | `GET /customers/{id}`, sau đó `/customers/{id}/activities` | customer_id, limit |
| `list_products` | product.read | `GET /products` | search, limit |
| `list_product_items` | product_item.read | `GET /product-items` | customer_id, product_id, status, keyword, created_at_from, created_at_to, limit |
| `list_support_cases` | support_case.read | `GET /support/cases` | product_item_id, status, keyword, limit |
| `get_support_messages` | support_case.read | `GET /support/cases/{case_id}/messages` (lấy N tin mới nhất) | case_id, limit |

**Lỗi:**

| Tình huống | HTTP | Body |
|---|---|---|
| Thiếu `X-API-Key` | 401 | `"X-API-Key header is required"` |
| Key sai, hoặc server chưa cấu hình key | 401 | `"invalid API key"` |
| Thiếu hoặc sai JWT | 401 | lỗi từ middleware `Authenticate` |

**Ví dụ:** `GET /api/v1/ai/tools` → `{"tools":[{"type":"function","function":{"name":"search_customers","description":"...","parameters":{"type":"object","properties":{...}}}}]}`
**AI dùng khi:** đầu mỗi phiên hội thoại, để biết người dùng này được dùng những tool nào.

#### `POST /ai/tools/{name}`
**Chức năng:**
- Chạy một tool. Body là object JSON chứa tham số, đúng chuỗi `arguments` mà model sinh ra.
- Server tự gọi GET vào API gốc **ngay trong tiến trình**, dùng nguyên JWT của người gọi, nên request đi qua đủ middleware `Authorize` và scope.
- Kết quả được làm sạch trước khi trả về: bỏ các trường trong `hiddenFields`, bỏ giá trị `null`, cắt chuỗi dài quá 800 ký tự.

**Quyền:** như `GET /ai/tools`. Key `public` gọi tool không có `public: true` sẽ nhận 403.
**Tham số:**
| Tên | Vị trí | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `name` | path | string | có | — | Tên tool (xem bảng trên) |
| body | body | object JSON | không | `{}` | Tham số của tool. Tối đa 64 KB |
| `limit` (trong body) | body | int | không | **tất cả** (gửi 100000 xuống API gốc) | Số dòng trả về. Gửi `1` khi chỉ cần đếm |

- Tham số id (`customer_id`, `case_id`…) bị từ chối nếu chứa `/`, `?`, `#`, `%`, `\`, dấu cách, hoặc dài quá 64 ký tự.

**Kết quả:** `{ "tool": "<name>", "status": <HTTP code của API gốc>, "data": <dữ liệu đã làm sạch> }`

**Lỗi:**

| Tình huống | HTTP | Body |
|---|---|---|
| Thành công | 200 | `{tool, status: 200, data}` |
| API gốc trả 401 hoặc 403 | **200** | `status: 401/403`, `data: {"error":"NGƯỜI DÙNG KHÔNG CÓ QUYỀN xem dữ liệu này","detail":...}` |
| API gốc trả 404 | **200** | `status: 404`, `data: {"error":"không tìm thấy"}` |
| API gốc trả lỗi ≥ 400 khác | **200** | `status: <code>`, `data: {"error":"lỗi <code>","detail":...}` |
| Body không phải object JSON, hoặc id không hợp lệ | 400 | `code: "INVALID_INPUT"` |
| Tên tool không tồn tại | 404 | `code: "NOT_FOUND"` |
| Key `public` gọi tool nội bộ | 403 | `code: "FORBIDDEN"` |
| Handler chưa được gắn router | 503 | `code: "NOT_READY"` |
| Thiếu hoặc sai key / JWT | 401 | xem `GET /ai/tools` |

**Ví dụ:**
```
POST /api/v1/ai/tools/list_support_cases
X-API-Key: <key>   Authorization: Bearer <token>
{"product_item_id":"7c1e..","status":"new,pending","limit":5}
→ {"tool":"list_support_cases","status":200,"data":{"items":[{"case_number":"SC-0123","status":"pending","assignee_name":"Trần B"}],"total":1,"limit":5,"offset":0}}
```
**AI dùng khi:** mỗi lần model trả về `tool_calls`. Agent forward nguyên văn `function.arguments` vào body, rồi đưa `data` lại cho model dưới dạng message `role: "tool"`.

## 4. Từ câu hỏi đến API

| Ý định của câu hỏi | API (theo thứ tự) |
|---|---|
| Tìm khách | `GET /customers?keyword=` |
| Khách đang ở trạng thái nào | `/customers` → `/customer-statuses` (tra `status_id`) |
| Sale nào phụ trách khách | `/customers` → `assigned_sales_id` → `/users` |
| Lần chăm sóc gần nhất | `/customers` → `/customers/{id}/activities?limit=5` |
| Khách mua máy gì | `/customers` → `/product-items?customer_id=` |
| **Ai hỗ trợ khách** | xem 5.1 |
| Khách vừa nhắn gì | `/customers` → `/product-items?customer_id=` → `/support/cases?product_item_id=` → `/support/cases/{id}/messages?limit=5`, cùng với `/support/waiting-messages/recipients?q=<tên>` (lấy `user_id`) → `/support/waiting-messages?created_by=<user_id>` |
| Giờ hỗ trợ còn lại của máy | `/product-items?customer_id=` → `/products/{item_id}/support-entitlement` |
| Phiếu được đánh giá ra sao | … → `/support/cases/{id}/rating` |
| Máy đã sửa những gì | `/product-items` → `/service-logs?product_item_id=` |
| Kỹ thuật viên X đã làm gì | `/users?keyword=X` → `/service-logs?technician_id=` |
| Máy do đại lý nào quản lý | `/product-items/{id}/agents` |
| Máy đã qua tay những chủ nào | `/product-items/{id}/ownership-history` |
| Đếm phiếu đang chờ | `/support/cases?status=new,pending&limit=1` → `total` |
| Phiếu tôi đang xử lý | `/support/cases?assigned_to_me=true` |

---

## 5. Ví dụ chuỗi gọi đầy đủ

### 5.1 "Khách hàng Nguyễn Văn A được hỗ trợ bởi ai?"
```
1. GET /customers?keyword=Nguyễn Văn A&limit=10
   → total=1 → customer_id = C1        (total>1 thì hỏi lại người dùng)

2. GET /product-items?customer_id=C1
   → [{id: P1, code: "QS-001", product_name: "CNC 3020"}, {id: P2, ...}]

3. GET /support/cases?product_item_id=P1          (lặp lại cho P2)
   → [{id: S1, case_number: "SC-0123", status: "in_progress", assignee_name: "Trần B"}]

4. GET /support/cases/S1/assignments
   → [{assigned_to_name: "Lê C", is_current: false, accepted_at: "2026-10-01"},
      {assigned_to_name: "Trần B", is_current: true,  accepted_at: "2026-10-05"}]

5. (thêm, nếu cần)
   GET /support/cases/S1/appointments              → ai gọi video / hẹn với khách
   GET /service-logs?product_item_id=P1            → technician
   GET /support/waiting-messages/recipients?q=Nguyễn Văn A → user_id
   GET /support/waiting-messages?created_by=<user_id>    → ai đã trả lời hộp thư chờ (handled_by)
```
Trả lời mẫu:
> Khách Nguyễn Văn A có 1 phiếu hỗ trợ 1:1 cho máy QS-001:
> - **SC-0123** (đang xử lý): hiện do **Trần B** hỗ trợ, nhận từ 05/10. Trước đó là **Lê C**.

### 5.2 "Tháng 10 có bao nhiêu khách mới và ai chăm nhiều nhất?"
```
GET /customers?created_at_from=2026-10-01&created_at_to=2026-10-31&limit=1   → total
GET /customers?created_at_from=2026-10-01&created_at_to=2026-10-31          → nhóm theo assigned_sales_id
GET /users?role_code=sales                                                  → id → tên
```

