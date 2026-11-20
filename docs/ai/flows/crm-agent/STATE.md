# Trạng thái luồng crm-agent

Cập nhật: 2026-11-20

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md). Tổng hợp ngày 2026-11-20
(luồng xử lý, quyết định, kết quả kiểm thử): [báo cáo](../../reports/crm_agent_status_2026-11-20.md).

## Tóm tắt

- **Thử nghiệm.** Mặc định `CRM_REPORT_ENABLED=false`, agent chỉ có `product_docs_ask`; bật thì có thêm
  `crm_schema` + `crm_query` (phương án C, D-005; phương án A đã xoá, D-010).
- `feature/deploy_ai_service` (`0561487`, chưa push) có Đợt 0 và Đợt 1 bước 1–3: so sánh 1 lần gọi (E), ép tra
  nguồn (D), dừng sớm + `final_reason` (C1–C3), `facts` của phiên + lịch sử theo lượt (A), cùng các sửa LC-2 (thử
  lại khi LLM hết giờ), LC-4 (kiểm cột trước CRM, ép sửa), LC-7 (trần token lượt, chỉ dẫn bước chốt).
- Kiểm thật 7 câu CRM: 1/7 → 5/7 có số liệu đúng (09:19 → 09:57 UTC). Chưa chạy lại sau LC-7: tunnel CRM offline.
- Môi trường kiểm thử của Toma: `AGENT_MODEL=gpt-4.1-mini`, `AGENT_TURN_INPUT_BUDGET=30000` (mặc định code 40000),
  so sánh 3 + 2 chunk (mặc định code 2 + 4, D-014 tạm). Trần token sẽ tinh chỉnh tiếp khi kiểm thử.
- Dữ liệu CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM khi bật tool CRM.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| `AgentRunner`: vòng lặp, deadline, giới hạn, thử lại LLM 1 lần | có; kiểm thật | Hết giờ có `timeout_phase` (lần đo: `read`, phía OpenAI) |
| Dừng sớm, `turn_budget`, bước chốt theo `final_reason` (C1–C3) | có; kiểm thật | Chỉ dẫn mới cho `budget`/`limit` (LC-7) chưa kiểm thật |
| Ép tra nguồn (D), ép sửa argument (LC-4) | có; kiểm thật | Lần kiểm 09:57 LLM tự sửa theo gợi ý, chưa cần ép |
| `product_docs_ask`, so sánh 1 lần gọi (E) | có; kiểm thật C1–C7 | Cặp khác nhiều thiếu bảng, gán sai nhãn |
| `crm_schema`, `crm_query` (kiểm cột theo schema sống) | có; kiểm thật | Eval 78/81 cũ (2026-11-12), chưa eval lại |
| `facts` của phiên (L2) + lịch sử theo lượt (L1), gói A | có; kiểm thật | UUID qua lượt và "khách thứ N" đúng; thiếu nhãn khi không chọn cột tên (LC-8) |
| Usage, chi phí, cached tokens | có; kiểm thật | `usage.source=trace` |
| Giám sát query (trace, audit `CRM_QUERY_AUDIT_LOG`) | có, test bằng fake | Chưa xem log server thật |
| Kiểm nguồn gốc giá trị (B), fan-out `split_by` (C4) | chưa có | Theo kế hoạch Đợt 1 |
| Phân quyền tool theo role/scope; SSE tiến trình | chưa có | Điểm gắn `required_scope` |

## Vấn đề mở

| ID | Vấn đề | Ảnh hưởng / hướng |
|---|---|---|
| LC-8 | Lượt liệt kê không chọn cột tên/tiêu đề thì facts không có nhãn; gọi bản ghi bằng nội dung không khớp | Chờ Toma: guide bắt chọn cột nhãn, hoặc nhãn từ đoạn đầu `content` |
| LC-6 | "Hộp tin nhắn chờ": 18 tin (mọi tin) hay 7 (`staff_deleted_at` null) | Chờ Toma/CRM chốt |
| LC-5 | Khách của tin nhắn: `customer_id` không khoá ngoại; đường đúng `product_item_id.customer_id` | Hint bảng |
| LC-7 | Trần token lượt và chỉ dẫn bước chốt | Code đã merge; Toma đặt 30000, chỉnh theo kiểm thử |
| LC-2 | gpt-4.1-mini đôi khi treo 19–20 s phía OpenAI | Thử lại đã cứu được; theo dõi tần suất |
| LC-1 | Tra tên ra nhiều người → dừng hỏi lại | Đo bằng eval |
| CMP-1, CMP-2 | So sánh: bảng chung chọn theo điểm; "spindle đồng thời" gán sai 4/5 lượt | Làm trước khi chốt D-014 |
| CMP-3, CMP-4 | Model không có tài liệu bị suy đoán; so 3 model sát trần output tool | |
| P4 | Định danh không kiểm nguồn gốc | Gói B |
| G1 | Eval `run_crm_agent_eval.py` chưa chạy lại sau Đợt 0/1 | Toma |
| r1 | "Khách được hỗ trợ" của phiếu: `customer_organization_id` hay `product_item_id.customer_id` | Toma/CRM |
| – | Lượt tài liệu qua agent tốn ~3 lần pipeline ở câu so sánh | Chi phí |
| – | `update_agent_conversation_state` không ghi `language`; `Prune` đếm token theo model chung | Lệch nhỏ |
| – | `CRM_REPORT_ENABLED` đặt tên theo phương án A; `CRM_CHAT_FLOW` mặc định `agent` (D-006) | Xem lại trước production |
| – | CRM: `is_current`, `date_range` theo ngày UTC, index tĩnh lệch 13 bảng, token không làm mới | Chờ CRM |

## Kết quả kiểm gần nhất

- 2026-11-20 09:57 UTC, 7 câu CRM (phiên `45efd790…`, backend `a8da3c9`): 5/7 có số liệu đúng; sai do LC-8 (câu
  3, 4) và LC-7 (câu 5, 6 kèm câu sai "chưa lấy được"). 1 lần hết giờ, thử lại xong 1,5 s. ~0,033 USD cho 7 lượt.
- 2026-11-20 09:19 UTC, cùng 7 câu sau gói A (phiên `38f77fbd…`): 1/7.
- `pytest tests` (nhánh `claude/dot1-lc7`): 1165 passed, 14 skipped, 1 failed có sẵn (`test_f86_baseline`, CSV CRLF).

## Bước tiếp theo

1. Toma: bật lại tunnel CRM; agent chạy lại 7 câu với trần 30000, kiểm câu 5, 6 (LC-7).
2. Toma quyết LC-8 và LC-6; agent làm LC-8, LC-5.
3. Toma chạy `run_crm_agent_eval.py` (G1) và `run_retrieval_eval.py`.
4. Sau đó: gói B, C4; CMP-1, CMP-2 rồi chốt D-014. Gửi CRM: `timezone`, mô tả `is_current`, dump schema mới.
