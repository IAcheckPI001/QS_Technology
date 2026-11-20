# Trạng thái chat-platform

Cập nhật: 2026-11-20

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Service key theo kênh, session theo principal, lease theo phiên, ghi history 4 trạng thái
  (`completed`, `error`, `blocked`, `cancelled`) và trace trong tiến trình đều có code và test.
- Đã đọc/ghi Supabase thật qua Workspace (B5, B3, B2 ngày 2026-11-18); lease trên khóa dòng thật
  và `/health/db` vẫn chưa có lần kiểm được ghi lại.
- Các GET `/chatbot/...` của Support Workspace **chưa có xác thực hay ownership**.
- `Idempotency-Key` mới được lưu, chưa chống xử lý trùng.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Service key theo kênh | có | Chưa có scope theo integration, rate limit theo key, `last_used_at` |
| Session + ownership khi ghi | có | Xóa hội thoại chưa có |
| Turn lease | có, test bằng fake | Khóa dòng thật cần kiểm live |
| Ghi `chat_history` | có | B3 (2026-11-18): token và chi phí thật, giá theo model (`core/pricing.py`); bản ghi cũ là ước tính (`usage.source`). Đợt 0 (2026-11-20, đã merge): đọc từ sổ `Trace.usage` (không mất khi vượt trần span), ước tính lời gọi bị ngắt (`usage.estimated_calls`), `model` của agent ở lượt CRM |
| Nạp context từ `chat_history` | có | 2026-11-20 (D-015): chỉ `CONTEXT_HISTORY_TURNS` (10) lượt hoàn tất gần nhất; `conversation_state.facts` của lượt agent |
| Đọc history, retrieval, trace, conversations | có, không xác thực | Giữ nội bộ. B5 (2026-11-18): `sources` theo lượt, `/retrieval?history_id`, nguồn của chunk, mã lỗi nhà cung cấp trong trace; đã kiểm đọc với Supabase thật (hội thoại 95 lượt), chưa có lượt mới ghi nguồn chunk |
| Danh sách, tìm, số liệu hội thoại (B2) | có | 2026-11-18: bảng tóm tắt `chat_conversations` + trigger, cờ lượt do Python ghi, tìm không dấu mọi lượt, phân trang cursor, `/metrics` và `/{id}` sau cờ `WORKSPACE_CONVERSATION_API_ENABLED`; đã áp SQL, điền cờ, so lệch "Khớp" và gọi API trên Supabase thật. Rủi ro R1–R10: FRONTEND_REQUIREMENTS 19.11 |
| Tracing giai đoạn 0 | có | Chưa OpenTelemetry, chưa truyền `traceparent` sang CRM/OpenAI, chưa retention, chưa UI |
| Health | một phần | `/health/db` chỉ `SELECT 1`; chưa định nghĩa readiness, chưa kiểm schema |

## Vấn đề mở

| Mức | Vấn đề |
|---|---|
| Cao | `requirements.txt` cho phép `fastapi>=0.115`; FastAPI 0.106–0.117 đóng dependency trước khi stream xong nên history ghi trong stream không commit. Chưa quyết định nâng mức tối thiểu |
| Cao | Key CRM là tin cậy ủy quyền: `user_id` do CRM backend khẳng định; key lộ thì mạo danh được mọi nhân viên của integration (chỉ có thu hồi + cấp lại) |
| Trung bình | GET `/chatbot/...` không ownership; `/chatbot/conversations` liệt kê mọi session |
| Thấp | B2: chưa có job so lệch `chat_conversations` định kỳ (R1, chạy `scripts/check_conversation_summary.py` bằng tay sau mỗi lần triển khai); chưa `EXPLAIN` truy vấn tìm trên dữ liệu lớn; sửa/xoá `chat_history` bằng tay phải chạy `rebuild_chat_conversations()` |
| Trung bình | Retry sau khi lượt gốc xong vẫn chạy lại (không replay theo `Idempotency-Key`) |
| Thấp | Bảng giá model mặc định (`core/pricing.py`) cần đối chiếu định kỳ với giá OpenAI; bản ghi trước 2026-11-18 vẫn là chi phí ước tính |
| Thấp | `npm run lint` lỗi sẵn có: 139 lỗi trong `src/`, 290 lỗi do eslint quét `.claude/worktrees/` |

## Kết quả kiểm gần nhất

2026-11-20 (nhánh `claude/dot0-on-b3`): `pytest tests` → 1107 passed, 14 skipped, 1 failed có sẵn
(CSV CRLF trong worktree). Lượt thật 2026-11-19 trên backend local (phiên `c999efd3…`) hoàn tất với
usage thật (OpenAI đã có credit lại): ghi `chat_history`, trace, `/retrieval` đọc được.

2026-11-18 (B2): `pytest tests` → 1071 passed. Supabase thật: `check_conversation_summary.py` →
"Khớp" (14 phiên, 222 lượt); gọi API B2 đủ các trường hợp ở LOG.

## Bước tiếp theo

1. Quyết định phiên bản FastAPI tối thiểu.
2. Chạy backend với Supabase thật: `/health/db`, một lượt chat, kiểm dòng `chat_history`,
   lease trên khóa dòng thật.
3. Xác thực và ownership cho GET history (service key hoặc tài khoản; test cho cặp
   session/token khớp và không khớp).
4. Chống xử lý trùng theo `Idempotency-Key`.
5. Merge nhánh `claude/dot0-on-b3` (sổ usage); quyết định kiểu `retrieved_chunk_ids`.
6. Định nghĩa `/health/db` là readiness hay chẩn đoán; trả non-2xx có chủ đích; kiểm schema
   các cột `chat_history` bắt buộc.
7. Xử lý hoặc tách baseline lỗi lint frontend; loại `.claude/worktrees/` khỏi eslint.
