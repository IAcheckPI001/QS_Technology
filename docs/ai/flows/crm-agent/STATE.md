# Trạng thái luồng crm-agent

Cập nhật: 2026-11-16

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- **Thử nghiệm.** Mặc định `CRM_REPORT_ENABLED=false`, agent chỉ có `product_docs_ask`.
- Bật tool CRM thì agent có `crm_schema` + `crm_query` (phương án C, D-005). Phương án A
  (`crm_report`, `crm_records`, `CRM_TOOLS`) **đã xoá 2026-11-16** (D-010).
- Đã dọn luồng 2026-11-16, merge và push lên `feature/deploy_ai_service`: gỡ `print()` in dữ
  liệu CRM, xoá A, gom code trùng. `backend/.env.example` Toma đã sửa tay cùng ngày.
- Model của agent: **gpt-4.1-mini** (quyết định 2026-11-12); guide `crm_query` tinh chỉnh cho
  model này. `AGENT_MODEL` chưa đặt ở môi trường chạy.
- Luật nghiệp vụ và ngày nằm trong code, áp cho mọi model: năm câu hỏi không nêu bị bỏ; kỳ trong
  filters thành `date_range`; "khách hàng" không tính spam; "nhân viên sales" theo vai trò, chỉ
  tài khoản còn dùng; có kỳ thì bỏ `is_current`.
- Dữ liệu CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM khi bật tool CRM.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| `AgentRunner`: vòng lặp, deadline, cancel, giới hạn | có, test bằng fake | Trần chung chỉ đếm call không bị `tool_call_limit`; `plan()` để trống (điểm gắn) |
| `product_docs_ask` + chọn model theo capabilities | có, test bằng fake | Registry có thêm 10S, 10i (2026-11-14). Từ 2026-11-19 tra cứu trên `doc_chunks_v2` (chỉ chunk approved nếu `RETRIEVAL_APPROVED_ONLY=true`, hiện chưa có) |
| `crm_schema`, `crm_query` | có; eval gpt-4.1-mini 78/81 | Trần `crm_query`: 6 lần thử, 4 lần gửi CRM |
| Giám sát query (trace, audit sau `CRM_QUERY_AUDIT_LOG`) | có, test bằng fake | Chưa xem trên log server thật |
| Phân quyền tool theo role/scope | chưa có | `required_scope`, `scopes` là điểm gắn, chưa dùng |
| SSE tiến trình, stream token câu trả lời cuối | chưa có | Câu trả lời cuối là một `delta` |
| Tool ghi dữ liệu, web search, MCP, provider khác OpenAI | chưa có | |

## Vấn đề mở

| Vấn đề | Ảnh hưởng |
|---|---|
| `chat_history.model` và chi phí ước tính theo `OPENAI_MODEL`, đơn giá gpt-4o-mini, không theo `AGENT_MODEL`; bước agent không ghi `cached_tokens` | History sai model, chi phí thấp hơn thực tế; chưa đo được cache (E1) |
| LLM tự suy username (thiếu `@qstcnc.com`); guide chưa có luật "username chỉ lấy nguyên văn từ kết quả tool" | Query rỗng, gọi lại tới hết lượt |
| Chạm giới hạn vẫn có thể trả lời "thử lại sau" (luật "trả lời phần đã có" ở `prompts.py` chưa đủ) | Gây hiểu nhầm |
| "Bản ghi đầu/cuối của từng người" phải mỗi người một query; guide chưa hướng dẫn | Nhiều người dễ chạm trần |
| Chưa có case eval câu hỏi nhiều sale hai lượt; chưa eval lại sau đổi giới hạn và sau đợt dọn | Chưa đo được các lỗi trên |
| "Khách được hỗ trợ" của phiếu (r1): `customer_organization_id` hay `product_item_id.customer_id` | Cần Toma/CRM chốt |
| `update_agent_conversation_state` không ghi `language`, mang theo `pending` cũ; `Prune` đếm token theo model chung; `ChatbotService` dựng stage pipeline cả trên đường agent | Lệch nhỏ; làm ở Đợt 0/1 |
| `CRM_REPORT_ENABLED` đặt tên theo phương án A nhưng bật `crm_schema`/`crm_query` | Dễ hiểu nhầm; đổi tên cần quyết định (đổi biến môi trường) |
| Mô tả cột `is_current` của CRM mâu thuẫn luật có kỳ | Code đã ép; đề nghị CRM sửa |
| CRM cắt `date_range` và `_day/_month/_year` theo ngày UTC (ranh giới 07:00 giờ VN) | Lệch biên kỳ; chờ CRM thêm `timezone` |
| Index tĩnh lệch 13 bảng (chủ yếu kho); `contains` phân biệt dấu tiếng Việt | Cần dump mới; tên gõ không dấu trả 0 |
| Token CRM không được làm mới; bảng ngoài `customers` cần `auth.manage_roles` | `crm_auth_failed` ở phiên dài; sale thường nhận `crm_forbidden` |
| `CRM_CHAT_FLOW` mặc định `agent` dù thử nghiệm (D-006) | Xem lại trước production |

Code chết dùng chung với website-qa/chat-platform (ngoài phạm vi đợt dọn): xem LOG 2026-11-16.

## Kết quả kiểm gần nhất

- 2026-11-16, sau đợt dọn, trên `feature/deploy_ai_service`, từ `backend/`: `pytest tests` →
  1016 passed, 14 skipped (trước dọn 1120: bớt test của phương án A, thêm `test_crm_render.py`
  và test trace 401 của `crm_query`). `check_ai_docs.py` đạt.
- 2026-11-12, eval gpt-4.1-mini 27 case × 3 ([báo cáo](../../reports/crm_agent_eval_C_gpt41_2026-11-12.md)):
  mốc sáng 50/81 → **78/81**; token vào mỗi câu ~29,9k → 21,0k.
- 2026-11-12, kiểm `POST /reports/query` câu hỏi nhiều sale: đếm gộp một query đúng (259/76/8);
  "khách đầu tiên của từng sale" phải tách query.

## Bước tiếp theo

1. Chạy lại eval sau đợt dọn; đặt `AGENT_MODEL=gpt-4.1-mini` ở môi trường chạy.
2. Đợt 0: E1 (model, chi phí, `cached_tokens`), luật username trong guide.
3. Đợt 1: E2–E5 ([báo cáo thảo luận](../../reports/crm_agent_architecture_discussion_2026-11-16.md)).
4. Chốt r1; gửi CRM: `timezone`, mô tả `is_current`, dump schema mới.
