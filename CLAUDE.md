# QS Technology - hướng dẫn cho Claude

## Bối cảnh

Đây là chatbot AI phân tích, nạp dữ liệu và truy vấn tài liệu. Frontend dùng
React/Vite tại `src/`; backend dùng FastAPI/Python tại `backend/`; database là
Supabase Cloud. Đọc [docs/ai/architecture.md](docs/ai/architecture.md) để
hiểu flow runtime và [docs/ai/api_guidelines.md](docs/ai/api_guidelines.md)
trước khi thay đổi API.

## Quy trình trước khi triển khai

1. Đọc hai tài liệu kiến trúc nêu trên và các rule trong `.claude/rules/`.
2. Kiểm tra current state/decisions nếu thay đổi database, security, API
   contract hoặc architecture.
3. Lập kế hoạch ngắn, xác định module/schema/API/test bị ảnh hưởng và hỏi lại
   khi có lựa chọn hành vi chưa rõ.
4. Tìm prior art trong code trước khi thêm helper, stage hoặc abstraction.
5. Giữ transport, business logic, provider và repository tách biệt; không gọi
   LLM trực tiếp từ FastAPI route.

## Quy ước code

- Backend đặt trong `backend/app/`; file và function nhiều từ dùng `snake_case`,
  class dùng `PascalCase`.
- Frontend đặt trong `src/`, dùng function component + hooks.
- TypeScript strict, không dùng `any`.
- Schema API phải explicit/versionable; không thay contract bằng untyped dict.
- Secrets lấy từ environment/settings; không commit `.env` hoặc credentials.
- Không thêm dependency mới nếu chưa được hỏi.
- Không biến scaffold/stub (learning, retrieval, final answer stream) thành
  mô tả tính năng đã hoàn thiện; phải ghi rõ trạng thái hoặc nối đủ flow.
- Không sửa unrelated modules. Nếu thay đổi API/schema/SSE/error code, cập nhật
  tài liệu và test liên quan.

## Validation

Từ repository root, chạy:

```powershell
npm run lint
npm run build
```

Khi thay đổi backend, chạy thêm:

```powershell
.\venv\Scripts\python.exe -m pytest backend\tests
```

Nếu virtual environment không tồn tại, báo rõ thay vì tự cài dependency.
Báo cáo mọi validation failure; không coi lint/build frontend hiện có là bằng
chứng backend đã đúng.

## Tài liệu chuẩn

- Kiến trúc runtime: [docs/ai/architecture.md](docs/ai/architecture.md)
- API contract: [docs/ai/api_guidelines.md](docs/ai/api_guidelines.md)
- Trạng thái và backlog: [docs/ai/current-state.md](docs/ai/current-state.md)
