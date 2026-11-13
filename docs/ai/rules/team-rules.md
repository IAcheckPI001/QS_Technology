# Quy tắc chung cho agent và team (team-rules)

Cập nhật: 2026-11-11

Đây là nguồn chuẩn của quy tắc áp dụng cho từ hai luồng trở lên. Quy tắc chỉ đúng cho
một luồng nằm ở mục "Bất biến" trong `README.md` của luồng đó. File khác chỉ trỏ tới ID
(TR-xx), không chép lại nội dung.

Thêm hoặc đổi quy tắc: ghi một dòng vào [decisions.md](../decisions.md) kèm bằng chứng
và người duyệt, rồi mới sửa file này.

## Kiến trúc và contract

| ID | Quy tắc | Lý do | Cách kiểm |
|---|---|---|---|
| TR-01 | Router chỉ làm transport: không gọi LLM provider, không chứa business rule, không truy cập database ngoài dependency wiring. | Giữ contract HTTP/SSE độc lập với logic; test được service không cần HTTP. | Review; test route trong `backend/tests/chatbot/test_chat_routes.py` |
| TR-02 | Service điều phối stage; stage trả kết quả có kiểu, không tự tạo HTTP response. Repository là ranh giới duy nhất cho persistence. | Một nơi duy nhất quyết định ánh xạ lỗi và ghi dữ liệu. | Review |
| TR-03 | Code riêng của nhà cung cấp LLM nằm sau interface provider; hạ tầng được đưa vào qua dependency injection. | Đổi provider không lan sang service; test dùng fake. | Review; fake trong `backend/tests/chatbot/agent_fakes.py` |
| TR-04 | Schema request/response explicit, versionable, đặt trong module tương ứng; không dùng `dict` tùy ý thay contract. | Contract kiểm được bằng máy và so sánh được giữa các phiên bản. | Test schema (`test_chatbot_schema.py`, `test_tool_schema.py`) |
| TR-05 | Lỗi phải được phân loại và ánh xạ rõ ràng; không nuốt exception, không trả fallback có hình dạng thành công. | Lỗi bị che làm sai kết quả mà không ai biết. | Review; test mã lỗi |
| TR-06 | Thay đổi schema, SSE event, mã lỗi hoặc status code là thay đổi API: cập nhật [api_guidelines.md](../api_guidelines.md) và test trong cùng thay đổi. | Client và tài liệu không được lệch với backend. | Review |
| TR-15 | Luồng offline và luồng chat không import chéo nhau (`doc_ingest` ↔ `chatbot`). | Image chat không chứa Docling; hai bên phát hành độc lập. | `backend/tests/doc_ingest/test_import_boundary.py` |

## An toàn và cấu hình

| ID | Quy tắc | Lý do | Cách kiểm |
|---|---|---|---|
| TR-07 | Secrets và cấu hình triển khai lấy từ environment/settings (`backend/app/core/config.py`); không ghi vào source hay response; không commit, không đọc, không in nội dung `.env`. `.env.example` là danh sách khóa tham chiếu. | Tránh lộ credential qua repo, log hoặc ngữ cảnh của agent. | Review |
| TR-13 | Khi không chắc thì chặn hoặc đưa vào hàng review, không đoán im lặng. | Dữ liệu sai lặng lẽ khó phát hiện hơn dữ liệu bị giữ lại. Ví dụ: hàng review của `doc_ingest`, bước privacy fail-closed của `learning_ai`, agent bỏ citation không xác định. | Test từng luồng |
| TR-16 | Tính năng thử nghiệm hoặc chưa có xác thực phải nằm sau cờ cấu hình, mặc định tắt. Ngoại lệ phải ghi vào [decisions.md](../decisions.md) (hiện có D-006: `CRM_CHAT_FLOW=agent`). | Deploy mặc định không mở bề mặt chưa kiểm. Ví dụ: `CRM_REPORT_ENABLED`, `LEARNING_API_ENABLED`, `CHAT_TRACE_PERSIST`. | `backend/tests/chatbot/test_config.py`; [deploy-rules.md](deploy-rules.md) |

## Cách làm việc

| ID | Quy tắc | Lý do | Cách kiểm |
|---|---|---|---|
| TR-08 | Không thêm dependency mới khi chưa hỏi. | Dependency ảnh hưởng image, bảo mật và hai venv. | Review diff `requirements*.txt`, `package.json` |
| TR-09 | Không sửa module không liên quan; task nhỏ thì thay đổi tối thiểu. Tìm prior art trong code trước khi thêm helper, stage hoặc abstraction. | Diff nhỏ duyệt được; tránh hai cách làm cho một việc. | Review |
| TR-10 | Không mô tả scaffold/stub như tính năng hoàn chỉnh. Độ chín ghi trong `STATE.md` của luồng. | Agent và người đọc sau sẽ dựng tiếp trên thứ chưa tồn tại. | Review tài liệu |
| TR-11 | Khi tài liệu mâu thuẫn với code: kiểm code, báo chỗ lệch, rồi sửa tài liệu trong cùng thay đổi. | Tài liệu lệch sẽ dẫn nhầm agent kế tiếp. | Review |
| TR-12 | Khi contract hoặc quy tắc tỏ ra sai, hoặc có cách tốt hơn: dừng và hỏi kèm bằng chứng. Thay đổi contract phải có bằng chứng và người duyệt, ghi vào `LOG.md`. | Contract là thỏa thuận của team, không phải của một phiên làm việc. | Mục LOG loại "quyết định" |
| TR-14 | Mỗi thay đổi hành vi phải có bằng chứng: lệnh đã chạy và kết quả. Báo cáo mọi validation failure. Lint/build frontend đạt không chứng minh backend đúng. | Tuyên bố "đã xong" không kèm bằng chứng không kiểm lại được. | Mục "Kiểm chứng" trong LOG |
| TR-17 | Một thông tin có một nơi ở. Sau mỗi thay đổi: viết lại `STATE.md` của luồng và thêm một mục vào đầu `LOG.md`; không sửa mục LOG cũ. | Trạng thái nối thêm sẽ tự mâu thuẫn; nhật ký bị sửa mất giá trị truy vết. | `backend/scripts/check_ai_docs.py` (chạy trong `tests/test_check_ai_docs.py`) |

## Quy ước code

- Backend đặt trong `backend/app/`; file và function nhiều từ dùng `snake_case`, class
  dùng `PascalCase`.
- Frontend đặt trong `src/`, dùng function component + hooks. Frontend hiện viết bằng
  JavaScript/JSX; nếu thêm TypeScript thì bật strict và không dùng `any`.
- Prompt là chuỗi Python đặt cạnh code dùng nó (`agent/prompts.py`, `prompts/`,
  `analysis/prompt/`); đổi prompt là đổi hành vi và phải chạy test/eval của luồng.
