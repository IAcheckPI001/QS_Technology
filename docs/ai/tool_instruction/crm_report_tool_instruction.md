# AI Tools API — hướng dẫn cho AI agent bên ngoài

Backend **không chạy AI**. Nó chỉ cung cấp các *tool* chỉ-đọc để một AI agent bên ngoài (ví dụ LLM chạy local bằng Ollama / LM Studio / vLLM) gọi lấy dữ liệu CRM.

- Code: `internal/platform/aitools/` (`tools.go` = danh sách tool, `handler.go` = 2 route)
- Route mount trong `internal/adapters/http/router.go`, wiring ở `internal/app/container.go` + `internal/app/http.go`

---

## 1. Cách hoạt động & phân quyền

```
Người dùng ──► AI agent (local) ──► LLM
                   │
                   │  Authorization: Bearer <token của người dùng>
                   ▼
   GET  /api/v1/ai/tools              → danh sách tool user được dùng
   POST /api/v1/ai/tools/{name}       → chạy 1 tool
                   │
                   ▼  (gọi nội bộ, cùng token)
   GET /api/v1/customers, /product-items, /support/cases, ...   ← API cũ
```

- Mỗi tool là một lệnh **GET vào API cũ**, chạy trong cùng tiến trình và **dùng nguyên JWT của người gọi**. Request đi qua đủ middleware `Authenticate → Authorize → data scope` giống hệt khi FE gọi.
- **AI không bao giờ chạm vào database** và không tự vượt quyền được. Việc lọc dữ liệu nằm hoàn toàn ở backend.
- Có 2 lớp phân quyền:
  1. **Theo permission**: `GET /ai/tools` chỉ trả về những tool mà user có quyền dùng.
  2. **Theo data scope**: kết quả lọc theo scope của user.

| Tài khoản | Data scope | Thấy khách hàng nào |
|---|---|---|
| Admin | `ALL` | Tất cả |
| Agent / chi nhánh | `ORGANIZATION(_AND_CHILDREN)` | Khách thuộc tổ chức của mình |
| Sale | `SELF` | Khách được giao cho mình |
| Không có `customer.read` | — | Không nhận được tool khách hàng; nếu cố gọi thì `status: 403` |

**Các trường luôn bị ẩn** (không bao giờ gửi tới AI): `phone`, `main_phone`, `email`, `main_email`, `address`, `website`, `notes`, `activation_notes`, `device_input`, `recall_notes`, `refurbish_notes`, `specifications`, `image_url`, các trường token/mật khẩu, `group_ids`, `business_field_ids`. Chuỗi dài quá 800 ký tự sẽ bị cắt.

---

## 2. Endpoint

### 2.1 `GET /api/v1/ai/tools` — lấy danh sách tool

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/ai/tools
```

Kết quả theo đúng định dạng `tools` của OpenAI, nên truyền thẳng vào `chat.completions` được:

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "search_customers",
        "description": "Tìm/đếm khách hàng ...",
        "parameters": { "type": "object", "properties": { "keyword": {"type":"string", "description":"..."} } }
      }
    }
  ]
}
```

### 2.2 `POST /api/v1/ai/tools/{name}` — chạy một tool

- Body: JSON object chứa tham số. Đây chính là chuỗi `arguments` mà model sinh ra, nên forward nguyên văn được. Body rỗng được hiểu là `{}`.

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/ai/tools/search_customers \
  -d '{"keyword":"An","limit":10}'
```

```json
{ "tool": "search_customers", "status": 200, "data": { "items": [ ... ], "total": 3, "limit": 10, "offset": 0 } }
```

- `status`: mã HTTP của API cũ phía sau.
- `data`: dữ liệu (đã ẩn các trường nhạy cảm), hoặc `{ "error": ... }`.

### 2.3 Mã lỗi

| Tình huống | HTTP | Body |
|---|---|---|
| Thành công | 200 | `{tool, status: 200, data}` |
| User không có quyền với dữ liệu | **200** | `{status: 403, data: {error: "NGƯỜI DÙNG KHÔNG CÓ QUYỀN xem dữ liệu này"}}` |
| Không tìm thấy bản ghi | **200** | `{status: 404, data: {error: "không tìm thấy"}}` |
| Lỗi khác từ API cũ | **200** | `{status: 4xx/5xx, data: {error, detail}}` |
| Tên tool không tồn tại | 404 | `{error, code: "NOT_FOUND"}` |
| Body không phải JSON object / id không hợp lệ | 400 | `{error, code: "INVALID_INPUT"}` |
| Thiếu hoặc hết hạn token | 401 | — |

> Lỗi về quyền hoặc không tìm thấy vẫn trả HTTP 200 có chủ đích: agent chỉ cần đưa `data` lại cho model, model đọc `error` và báo lại người dùng.

---

## 3. Danh sách tool

Quy ước chung:
- Mọi tool dạng danh sách đều nhận `limit`. **Bỏ trống thì trả về tất cả**; không có giới hạn tối đa. `data.total` là **tổng số dòng khớp bộ lọc**.
- Danh sách lớn (vài trăm khách) sẽ chiếm nhiều context của LLM local. Nếu model bị tràn context, hãy truyền `limit` hoặc lọc hẹp hơn.
- Muốn **đếm** thì gọi với `"limit": 1` rồi đọc `total`.
- Ngày tháng dùng dạng `YYYY-MM-DD`.

### 3.1 `search_customers` — tìm / đếm khách hàng
| | |
|---|---|
| Quyền | `customer.read` |
| API cũ | `GET /customers` |
| Tham số | `keyword`, `customer_type`, `created_at_from`, `created_at_to`, `mine`, `limit` |

- `keyword` khớp với **tên, tên công ty, SĐT, email**. Không phân biệt hoa thường hay dấu. SĐT so theo 9 số cuối (`0909123456` và `84909123456` cho cùng kết quả). **Không** tìm được theo mã KH.
- `customer_type`: `lead` (tiềm năng) | `student` (học viên) | `official` (chính thức) | `lost`.
- `mine: true`: chỉ lấy **khách được giao cho chính người đang hỏi** (`assigned_sales_id` = user của token). Dùng cho các câu như "khách của tôi" hay "tôi phụ trách". Bộ lọc này **cộng thêm** vào data scope chứ không thay thế: một tài khoản có scope `ALL` (ví dụ có role WRITER) mà không truyền `mine` thì sẽ thấy toàn bộ khách.
- Kết quả mỗi khách: `id`, `code`, `full_name`, `company_name`, `customer_type`, `status_id`, `organization_id`, `organization_name`, `assigned_sales_id`, `created_at`, `last_contact_at`, …

```json
{"mine":true,"limit":1}                                     // tôi đang phụ trách bao nhiêu KH
{"mine":true,"keyword":"An"}                                // tìm "An" trong KH của tôi
{"keyword":"0909123456"}                                   // tìm đúng 1 KH theo SĐT
{"keyword":"nguyen van an"}                                 // theo tên, không dấu
{"customer_type":"lead","limit":1}                          // đếm KH tiềm năng
{"created_at_from":"2026-11-01","created_at_to":"2026-11-30"} // KH tạo trong tháng 11
```

Tìm **1 khách**: dùng SĐT là chính xác nhất. Nếu tìm theo tên mà `total > 1` thì nên liệt kê ra và hỏi lại người dùng muốn người nào.

### 3.2 `get_customer` — chi tiết một khách hàng
| | |
|---|---|
| Quyền | `customer.read` |
| API cũ | `GET /customers/{id}` |
| Tham số | `customer_id` (**bắt buộc**, lấy từ `search_customers`) |

```json
{"customer_id":"1a5fa1a5-5052-4bd5-b227-b08782e2a74f"}
```

### 3.3 `list_products` — danh mục sản phẩm (loại / model máy)
| | |
|---|---|
| Quyền | `product.read` |
| API cũ | `GET /products` |
| Tham số | `search` (tên hoặc mã), `limit` |

Kết quả: `id`, `code`, `name`, `category`, `warranty_months`.

```json
{"limit":1}           // có bao nhiêu loại sản phẩm
{"search":"CNC"}
```

### 3.4 `list_product_items` — từng máy cụ thể (có serial)
| | |
|---|---|
| Quyền | `product_item.read` |
| API cũ | `GET /product-items` |
| Tham số | `customer_id`, `product_id`, `status`, `keyword`, `created_at_from`, `created_at_to`, `limit` |

- `status`: `stock` | `delivered` | `active` | `maintenance` | `out_of_order` | `decommissioned` | `recalled` | `refurbished`. Nhiều giá trị thì ngăn cách bằng dấu phẩy.
- `keyword`: mã máy, hoặc tên / SĐT / công ty của chủ máy.
- Kết quả: `id`, `code`, `product_id`, `customer_id`, `owner_name`, `status`, `activated_at`, `warranty_expiry`, `managing_agent_name`, …

```json
{"customer_id":"<id>"}                 // KH đã mua những máy nào
{"status":"active","limit":1}          // đếm máy đang hoạt động
{"product_id":"<id>","status":"stock"} // tồn kho của một sản phẩm
```

> "Sản phẩm" có 2 nghĩa: `list_products` là **loại máy**, còn `list_product_items` là **từng máy đã sản xuất hoặc bán**.

### 3.5 `list_support_cases` — yêu cầu hỗ trợ (ticket)
| | |
|---|---|
| Quyền | `support_case.read` |
| API cũ | `GET /support/cases` |
| Tham số | `product_item_id`, `status`, `keyword` (số case, tiêu đề), `limit` |

- `status`: `new` | `pending` | `in_progress` | `resolved` | `closed` | `reopened` | `cancelled` | `rejected`.
- Kết quả: `id`, `case_number`, `subject`, `status`, `priority`, `customer_name`, `product_name`, `created_at`, `closed_at`, …
- Nhân viên không có scope `ALL` chỉ thấy các case được giao cho mình (theo đúng quy tắc của trang Hỗ trợ).

```json
{"product_item_id":"<id>"}
{"status":"new,pending","limit":1}     // đếm case đang chờ
```

### 3.6 `get_support_messages` — tin nhắn mới nhất của một case
| | |
|---|---|
| Quyền | `support_case.read` |
| API cũ | `GET /support/cases/{id}/messages` |
| Tham số | `case_id` (**bắt buộc**), `limit` (bỏ trống = toàn bộ cuộc trò chuyện) |

Trả về **N tin nhắn mới nhất**, sắp từ cũ đến mới. Mỗi tin: `sender_name`, `body`, `type` (`portal` / `email` / `system` / `internal_note`), `created_at`. Ghi chú nội bộ (`internal_note`) chỉ hiện với nhân viên có quyền `support_case.read_internal`.

```json
{"case_id":"<id>","limit":5}
```

---

### 3.7 `list_customer_statuses` — bảng tra trạng thái khách hàng
| | |
|---|---|
| Quyền | `customer.read` |
| API cũ | `GET /customer-statuses` |
| Tham số | `limit` (không bắt buộc) |

Kết quả: `id`, `name`, `label_vi`, `label_en`, `group`, `status_id` (nhóm trạng thái). Khách hàng chỉ lưu `status_id`, nên AI cần tool này để đọc ra tên trạng thái (ví dụ "Đã chốt"), hoặc làm chiều ngược lại: từ tên trạng thái tìm ra `status_id`.

```json
{}
```

### 3.8 `list_users` — nhân viên / người dùng
| | |
|---|---|
| Quyền | `user.read` (hiện chỉ có role **admin**, **agent_admin**) |
| API cũ | `GET /users` (lọc theo data scope) |
| Tham số | `keyword` (tên), `role_code` (vd `sales`), `organization_id`, `limit` |

Kết quả: `id`, `full_name`, `first_name`, `last_name`, `roles`, `organization_id`, `region`. Email và SĐT bị ẩn. Dùng để đọc `assigned_sales_id`, `created_by` hay `sales_id` ra tên người, hoặc tìm id của một sale.

```json
{"role_code":"sales"}            // danh sách sale
{"keyword":"Minh"}               // tìm id của sale tên Minh
```

> Sale không có quyền `user.read` nên không nhận được tool này. Riêng `get_customer_activities` vẫn có sẵn `sales_name`, và `get_customer` có `created_by_name`.

### 3.9 `get_customer_activities` — lịch sử chăm sóc khách hàng
| | |
|---|---|
| Quyền | `customer.read` |
| API cũ | `GET /customers/{id}` (kiểm tra scope) → `GET /customers/{id}/activities` |
| Tham số | `customer_id` (**bắt buộc**), `limit` |

Kết quả: `action` (gọi điện / gặp / nhắn…), `content`, `contact_at`, `sales_name`, `created_at`. Ảnh đính kèm bị ẩn.

> **Bảo mật:** route `/customers/{id}/activities` gốc chỉ kiểm tra `customer.read`, **không** kiểm tra scope. Vì vậy tool gọi `GET /customers/{id}` trước: nếu khách nằm ngoài phạm vi của người hỏi (route trả 404/403) thì tool dừng và **không** đọc lịch sử. (Bản thân route gốc vẫn đang hở với FE / API trực tiếp — nên sửa riêng.)

```json
{"customer_id":"<id>","limit":5}     // 5 lần chăm sóc gần nhất
```

## 4. Ghép các tool cho một câu hỏi

Model tự chọn tool dựa trên mô tả. Đây là các chuỗi gọi thường gặp:

| Câu hỏi | Chuỗi tool |
|---|---|
| "Có bao nhiêu khách hàng?" | `search_customers {limit:1}` → `total` |
| "Tôi đang phụ trách những khách nào?" | `search_customers {mine:true}` |
| "Khách A đang ở trạng thái nào?" | `search_customers` → `list_customer_statuses` (tra `status_id`) |
| "Lần cuối liên hệ khách A là khi nào, nói gì?" | `search_customers` → `get_customer_activities {customer_id}` |
| "Khách A do ai phụ trách?" | `search_customers` → `list_users` (tra `assigned_sales_id`) |
| "Khách hàng A đã mua gì?" | `search_customers {keyword:"A"}` → `list_product_items {customer_id}` |
| "Khách hàng A vừa nhắn gì?" | `search_customers` → `list_product_items {customer_id}` → `list_support_cases {product_item_id}` → `get_support_messages {case_id}` |
| "Có bao nhiêu máy đang hoạt động?" | `list_product_items {status:"active", limit:1}` |
| "Có bao nhiêu sản phẩm?" | `list_products {limit:1}` |

---

## 5. Code mẫu cho agent (Python)

Dùng được với bất kỳ server nào tương thích OpenAI: Ollama, LM Studio, vLLM, OpenAI…

```python
import json, requests
from openai import OpenAI

CRM = "http://localhost:8080/api/v1"
TOKEN = "<access token của người dùng đang đăng nhập>"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

llm = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")   # Ollama
MODEL = "qwen2.5:7b"   # cần model hỗ trợ tool calling

def ask(question: str, history: list | None = None) -> str:
    tools = requests.get(f"{CRM}/ai/tools", headers=H).json()["tools"]
    msgs = [{"role": "system", "content":
             "Bạn là trợ lý CRM. Chỉ trả lời dựa trên dữ liệu lấy từ tool, không bịa. "
             "Câu hỏi 'bao nhiêu' thì gọi tool với limit=1 và đọc total. "
             "Nếu tool báo không có quyền thì nói rõ cho người dùng."}]
    msgs += history or []
    msgs.append({"role": "user", "content": question})

    for _ in range(8):                       # giới hạn số vòng gọi tool
        m = llm.chat.completions.create(model=MODEL, messages=msgs, tools=tools).choices[0].message
        if not m.tool_calls:
            return m.content
        msgs.append(m)
        for call in m.tool_calls:
            r = requests.post(f"{CRM}/ai/tools/{call.function.name}",
                              headers=H, data=call.function.arguments or "{}")
            body = r.json()
            content = body.get("data", body)        # lỗi 400/404 của chính endpoint cũng đưa cho model
            msgs.append({"role": "tool", "tool_call_id": call.id,
                         "content": json.dumps(content, ensure_ascii=False)})
    return "Không trả lời được trong giới hạn số bước."

print(ask("Khách hàng Nguyễn Văn An đã mua sản phẩm gì?"))
```

**Lưu ý:**
- Token phải là token của **người đang hỏi**. Không dùng token admin cho mọi người, vì như vậy mất phân quyền.
- Access token có thời hạn. Khi API trả 401 thì agent phải refresh token (`POST /api/v1/auth/refresh`) hoặc bắt người dùng đăng nhập lại.
- Nên gọi lại `GET /ai/tools` cho từng người dùng, vì mỗi role nhận được một bộ tool khác nhau.

---

## 6. Thêm tool mới

Thêm một phần tử vào slice `tools` trong `internal/platform/aitools/tools.go`:

```go
{
	def: Def{
		Name:        "list_work_orders",
		Description: "Mô tả rõ cho model khi nào nên dùng tool này",
		Parameters:  obj(map[string]any{"status": str("..."), "limit": num(limitDesc)}),
	},
	permission: "work_order.read",                          // quyền mà route gốc yêu cầu
	run:        listRun("/work-orders", "status"),           // GET route đã có sẵn + tên query param
},
```

- Chỉ được trỏ vào route **GET** có sẵn. Không bao giờ thêm tool ghi dữ liệu.
- `permission` phải trùng với `Authorize(...)` của route trong `router.go`. Trường này chỉ dùng để lọc danh sách tool; route gốc vẫn tự kiểm tra quyền.
- Nếu response có trường nhạy cảm mới thì thêm tên trường vào `hiddenFields`.
- Với route có `{id}`, dùng `getRun("/path/%s", "ten_tham_so")`. Hàm `safeID` sẽ chặn các id chứa `/`, `?`, `%`.
- Test: `go test ./internal/platform/aitools/`

> **Dev (Air):** Air có thể không theo dõi thư mục `aitools/` vừa tạo mới. Nếu sửa file trong đó mà API không build lại, hãy `touch internal/adapters/http/router.go` hoặc restart container `api`.
