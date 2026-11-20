# Trạng thái luồng crm-agent

Cập nhật: 2026-11-20

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- **Thử nghiệm.** Mặc định `CRM_REPORT_ENABLED=false`, agent chỉ có `product_docs_ask`.
- Bật tool CRM thì agent có `crm_schema` + `crm_query` (phương án C, D-005). Phương án A đã xoá (D-010).
- Trên `feature/deploy_ai_service` (chưa push): Đợt 0; Đợt 1 bước 1 (E so sánh, D ép tra nguồn), bước 2
  (C1–C3 dừng sớm, `final_reason`), bước 3 (gói A: `facts` của phiên, lịch sử theo lượt; `98f2db4`).
- Lỗi lớn nhất hiện tại không ở code mới: gpt-4.1-mini hết giờ 20 s (LC-2) và LLM không thử lại sau lỗi cột (LC-4).
- Câu so sánh theo quyết định **tạm** D-014: chunk riêng từng model + chunk chung, cắt cột bảng. Đã kiểm
  bộ C1–C7: cắt cột đạt cả 7 câu; mặc định code 2 + 4, Toma đang chạy 3 + 2 qua env.
- Model agent ở môi trường chạy: gpt-4.1-mini (`AGENT_MODEL`); analysis trong `product_docs_ask` vẫn
  dùng `OPENAI_MODEL` (gpt-4o-mini).
- Dữ liệu CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM khi bật tool CRM.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| `AgentRunner`: vòng lặp, deadline, cancel, giới hạn | có; kiểm thật 2026-11-20 | Dừng theo số bước, số lần gọi, deadline |
| Dừng sớm (ambiguous, plateau, budget), `turn_budget`, bước chốt có khung (C1–C3) | có, test bằng fake; đã merge, chưa kiểm thật | Ngưỡng 50% lượt gọi, `AGENT_TURN_INPUT_BUDGET=15000` chưa đo; lưu câu hỏi dở chờ Gói A |
| Ép tra nguồn (gói D) | có; kiểm thật | Câu nhắc mã model hoặc trích nguồn bị xoá mà không gọi tool → chạy lại 1 bước `required` |
| `product_docs_ask`, câu so sánh 1 lần gọi (gói E) | có; kiểm thật C1–C7 | Đủ khác biệt ở cặp gần giống; cặp khác nhiều thiếu bảng và LLM gán sai nhãn |
| `crm_schema`, `crm_query` | có; eval gpt-4.1-mini 78/81 (2026-11-12) | Chưa eval lại sau đợt dọn, Đợt 0, Đợt 1 |
| Usage, chi phí, cached tokens của lượt | có; kiểm thật | `usage.source=trace`, chi phí theo bảng giá từng model |
| Giám sát query (trace, audit `CRM_QUERY_AUDIT_LOG`) | có, test bằng fake | Chưa xem trên log server thật |
| Context phiên L1 + L2 (`facts`, lịch sử theo lượt), gói A | có; kiểm thật 1 phiên (UUID qua lượt dùng đúng) | Đã merge `98f2db4`; ordinal chưa kiểm thật |
| Kiểm nguồn gốc giá trị (gói B) | chưa có | Cần facts (đã có) |
| Phân quyền tool theo role/scope | chưa có | `required_scope`, `scopes` là điểm gắn |
| SSE tiến trình, stream token câu trả lời cuối | chưa có | Câu trả lời cuối là một `delta` |

## Vấn đề mở

| ID | Vấn đề | Ảnh hưởng |
|---|---|---|
| CMP-1 | Chunk chung của câu so sánh chọn theo điểm, hay lấy bảng giống nhau (Compensation) thay bảng có khác biệt | Thiếu khác biệt, kết quả đổi theo cách hỏi |
| CMP-2 | LLM gán "Max. Spindle" thành "spindle đồng thời" (4/5 lượt F54–F86), bỏ qua dòng có trong nguồn | Sai dữ liệu; đề xuất code tính sẵn khác/giống |
| CMP-3 | Model không có tài liệu (F86E): vẫn suy đoán "bản nâng cấp" | Thông tin bịa |
| CMP-4 | So 3 model đã ~2.890/2.968 token output tool | So 4 model bị cắt nguồn |
| D-014 | Hạn mức 2 + 4 hay 3 + 2 chưa chốt | Chờ CMP-1 rồi Toma chốt |
| P4 | Định danh không kiểm nguồn gốc | Gói B của [kế hoạch Đợt 1](../../reports/crm_agent_dot1_plan_2026-11-20.md); P1–P3 đã có code (A, C1–C3) |
| LC-1 | `crm_query` tra tên ra nhiều người → dừng hỏi lại; câu "liệt kê nhân viên tên X" không đi tiếp được | Cần đo bằng eval |
| LC-2 | gpt-4.1-mini đôi khi treo 20 s (phía OpenAI: `timeout_phase=read`) | Đã merge thử lại một lần; kiểm thật 2026-11-20: cứu được lượt hết giờ |
| LC-4 | LLM đoán cột khi chưa đọc `crm_schema` | Đã merge kiểm cột kèm gợi ý + bắt sửa; kiểm thật: LLM tự sửa theo gợi ý |
| LC-7 | `AGENT_TURN_INPUT_BUDGET=15000` thấp: lượt CRM 3 bước ~20k → dừng `budget`, bước chốt nói sai "chưa lấy được" | Đề xuất 40k, sửa chỉ dẫn bước chốt |
| LC-8 | Bản ghi liệt kê không có cột tên/tiêu đề thì facts không có nhãn; gọi bằng nội dung không khớp | Cần quyết định nhãn từ `content` |
| LC-5 | "Có thuộc khách hàng" kết luận từ một trang khách bất kỳ; `support_waiting_messages.customer_id` không khoá ngoại | Sai logic; cần hint bảng |
| LC-6 | "Hộp tin nhắn chờ" lúc 18 tin (mọi tin) lúc 7 (`staff_deleted_at` null) | Cần Toma/CRM chốt nghĩa |
| LC-3 | Bản ghi nhắc ở lượt trước mất UUID (P1) | Gói A đã giải ở lượt thật; theo dõi thêm |
| – | Lượt tài liệu qua agent tốn hơn pipeline ~3 lần ở câu so sánh (0,0023–0,0035 so với 0,0009–0,0011 USD) | Chi phí; analysis không cache được |
| r1 | "Khách được hỗ trợ" của phiếu: `customer_organization_id` hay `product_item_id.customer_id` | Cần Toma/CRM chốt |
| – | `update_agent_conversation_state` không ghi `language`, mang theo `pending` cũ; `Prune` đếm token theo model chung | Lệch nhỏ |
| – | `CRM_REPORT_ENABLED` đặt tên theo phương án A | Đổi tên cần quyết định |
| – | CRM: `is_current` mâu thuẫn luật có kỳ; `date_range` theo ngày UTC; index tĩnh lệch 13 bảng; token CRM không làm mới | Chờ CRM |
| – | `CRM_CHAT_FLOW` mặc định `agent` dù thử nghiệm (D-006) | Xem lại trước production |

## Kết quả kiểm gần nhất

- 2026-11-20 09:57, sau LC-2/LC-4, 7 câu CRM (phiên `45efd790…`): 5/7 có số liệu đúng (trước 1/7); sai do LC-7, LC-8.
- 2026-11-20, lượt CRM thật sau C1–C3 (phiên `8de1e4b1…`, đối chiếu Reporting API): 5/7 lượt đúng; sai do mất
  UUID qua lượt (LC-3) và hết giờ LLM (LC-2). `final_reason` ghi đúng (`answered`, `budget`, `limit`).
- 2026-11-20, bộ câu so sánh C1–C7 (phiên `8de1e4b1…`, `97fa9b85…`, backend `14196d6`, hạn mức 3 + 2):
  1 lần gọi tool mỗi lượt agent, 9,7k–11,8k token vào; cắt cột đúng ở cả 7 câu; C2, C3 đủ khác biệt.
- 2026-11-20, nhánh `claude/dot1-a`, `pytest tests` (worktree): 1151 passed, 14 skipped, 1 failed có sẵn
  (`test_f86_baseline`, CSV CRLF).

## Bước tiếp theo

1. Agent (chờ Toma duyệt): LC-7 nâng trần token lượt và sửa chỉ dẫn bước chốt; LC-8 theo quyết định của Toma;
   LC-5 hint bảng tin nhắn chờ. Toma chốt LC-6.
2. Toma: thêm `AGENT_TURN_INPUT_BUDGET`, `AGENT_HISTORY_TURNS`, `CONTEXT_HISTORY_TURNS` vào `.env.example`; chạy
   `run_crm_agent_eval.py` (G1) và `run_retrieval_eval.py`.
3. Sau đó: gói B, C4; CMP-1, CMP-2 rồi chốt D-014.
4. Chốt r1; gửi CRM: `timezone`, mô tả `is_current`, dump schema mới.
