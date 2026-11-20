# Trạng thái luồng crm-agent

Cập nhật: 2026-11-20

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- **Thử nghiệm.** Mặc định `CRM_REPORT_ENABLED=false`, agent chỉ có `product_docs_ask`.
- Bật tool CRM thì agent có `crm_schema` + `crm_query` (phương án C, D-005). Phương án A
  (`crm_report`, `crm_records`, `CRM_TOOLS`) **đã xoá 2026-11-16** (D-010).
- **Đợt 0 xong ở mức code + test bằng fake** (2026-11-20, nhánh `claude/dot0-on-b3`, **chưa merge**
  vào `feature/deploy_ai_service`): history ghi model của agent, usage lấy từ sổ của trace (không
  mất khi vượt trần span, có ước tính cho lời gọi bị ngắt), cached tokens của bước agent, luật
  username trong guide `crm_query`. Chi phí thật của lượt là B3 (D-013).
- Model của agent: **gpt-4.1-mini** (quyết định 2026-11-12); `AGENT_MODEL` chưa đặt ở môi trường
  chạy (lượt kiểm 2026-11-19 chạy gpt-4o-mini).
- Luật nghiệp vụ và ngày nằm trong code, áp cho mọi model: năm câu hỏi không nêu bị bỏ; kỳ trong
  filters thành `date_range`; "khách hàng" không tính spam; "nhân viên sales" theo vai trò, chỉ
  tài khoản còn dùng; có kỳ thì bỏ `is_current`.
- Dữ liệu CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM khi bật tool CRM.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| `AgentRunner`: vòng lặp, deadline, cancel, giới hạn | có; kiểm thật 2026-11-19 (1 lượt) | Trần chung chỉ đếm call không bị `tool_call_limit`; `plan()` để trống (điểm gắn) |
| `product_docs_ask` + chọn model theo capabilities | có; kiểm thật 2026-11-19 | Tra cứu trên `doc_chunks_v2` (chỉ chunk approved nếu `RETRIEVAL_APPROVED_ONLY=true`, hiện chưa có chunk approved) |
| `crm_schema`, `crm_query` | có; eval gpt-4.1-mini 78/81 | Trần `crm_query`: 6 lần thử, 4 lần gửi CRM |
| Giám sát query (trace, audit sau `CRM_QUERY_AUDIT_LOG`) | có, test bằng fake | Chưa xem trên log server thật |
| Usage, model, cached tokens của lượt agent (Đợt 0) | có, test bằng fake; chưa merge | Chưa kiểm trên server thật |
| Phân quyền tool theo role/scope | chưa có | `required_scope`, `scopes` là điểm gắn, chưa dùng |
| SSE tiến trình, stream token câu trả lời cuối | chưa có | Câu trả lời cuối là một `delta` |
| Tool ghi dữ liệu, web search, MCP, provider khác OpenAI | chưa có | |

## Vấn đề mở

| Vấn đề | Ảnh hưởng |
|---|---|
| Lượt tài liệu qua agent tốn hơn pipeline khoảng 25% (lượt F54 2026-11-19: 9,9k so với 7,9k token): bước analysis trong `product_docs_ask` tốn ~5,1k token, không được cache | Chi phí, độ trễ; xem E7/E8 |
| LLM tự suy username (thiếu `@qstcnc.com`): luật trong guide đã thêm (Đợt 0), chưa đo; code chưa chặn giá trị không có nguồn gốc (E2) | Query rỗng, gọi lại tới hết lượt |
| Chạm giới hạn vẫn có thể trả lời "thử lại sau" (E5) | Gây hiểu nhầm |
| "Bản ghi đầu/cuối của từng người" phải mỗi người một query (E4) | Nhiều người dễ chạm trần |
| Chưa có case eval câu hỏi nhiều sale hai lượt; chưa eval lại sau đợt dọn và Đợt 0 | Chưa đo được các lỗi trên |
| "Khách được hỗ trợ" của phiếu (r1): `customer_organization_id` hay `product_item_id.customer_id` | Cần Toma/CRM chốt |
| `update_agent_conversation_state` không ghi `language`, mang theo `pending` cũ; `Prune` đếm token theo model chung | Lệch nhỏ |
| `CRM_REPORT_ENABLED` đặt tên theo phương án A nhưng bật `crm_schema`/`crm_query` | Đổi tên cần quyết định |
| CRM: mô tả `is_current` mâu thuẫn luật có kỳ; `date_range` cắt theo ngày UTC; index tĩnh lệch 13 bảng; `contains` phân biệt dấu | Chờ CRM (`timezone`, dump mới) |
| Token CRM không được làm mới; bảng ngoài `customers` cần `auth.manage_roles` | `crm_auth_failed` ở phiên dài; sale thường nhận `crm_forbidden` |
| `CRM_CHAT_FLOW` mặc định `agent` dù thử nghiệm (D-006) | Xem lại trước production |

## Kết quả kiểm gần nhất

- 2026-11-20, Đợt 0, từ `backend/` của worktree (nhánh `claude/dot0-on-b3`): `pytest tests` →
  1107 passed, 14 skipped, 1 failed có sẵn (`test_f86_baseline`: CSV bị checkout CRLF trong
  worktree). Thêm `test_usage_ledger.py` (8 test).
- 2026-11-19, lượt thật "F54 có bao nhiêu trục" (phiên `c999efd3…`, `flow=agent`): 2 bước LLM,
  1 lần `product_docs_ask`, trả lời đúng "4 trục" với nguồn catalog; 9.914 token vào, 9,2 s.
- 2026-11-12, eval gpt-4.1-mini 27 case × 3 ([báo cáo](../../reports/crm_agent_eval_C_gpt41_2026-11-12.md)): **78/81**.

## Bước tiếp theo

1. Toma review và merge nhánh `claude/dot0-on-b3`; khởi động lại backend, gửi một lượt CRM và kiểm
   `usage.cached_input_tokens`, `model` trong history.
2. Toma chạy lại eval (`run_crm_agent_eval.py`) sau đợt dọn và luật username; đặt `AGENT_MODEL`.
3. Đợt 1 theo [kế hoạch 2026-11-20](../../reports/crm_agent_dot1_plan_2026-11-20.md) (chờ Toma duyệt
   Q1–Q5): context phiên ba lớp, kiểm nguồn gốc, điều khiển vòng lặp + hỏi lại, bắt buộc tra nguồn, so sánh.
4. Chốt r1; gửi CRM: `timezone`, mô tả `is_current`, dump schema mới.
