# crm-agent: trạng thái, quyết định và kết quả kiểm thử (2026-11-20)

Tổng hợp một ngày làm Đợt 1 trên `feature/deploy_ai_service` (đến `0561487`, chưa push). Chi tiết từng
thay đổi ở [LOG crm-agent](../flows/crm-agent/LOG.md); ảnh chụp hiện tại ở [STATE](../flows/crm-agent/STATE.md).

## 1. Luồng xử lý hiện tại (kênh CRM, `CRM_CHAT_FLOW=agent`)

```text
ChatbotService: security → session/lease → ContextLoader (10 lượt gần nhất) → prune
 └─ AgentRunner.run (gpt-4.1-mini, AGENT_MODEL)
     ├─ prompt: luật chung + guide của tool được dùng + <session_state> (facts, ≤ 500 token) + 3 lượt hỏi/đáp gần nhất
     ├─ lặp ≤ 6 bước, ≤ 8 lần gọi tool, deadline 60 s:
     │    ├─ gọi LLM (timeout request 19 s, không để SDK tự thử lại); hết giờ/429/5xx → thử lại 1 lần
     │    ├─ chạy tool (crm_schema, crm_query, product_docs_ask), song song khi được phép
     │    ├─ message tool kèm turn_budget; tool để lại định danh cho facts (ToolSpec.remember)
     │    ├─ dừng sớm: ambiguous, plateau (2 bước rỗng/lỗi liên tiếp), budget (nửa số lần gọi chưa có kết quả,
     │    │   hoặc token vào cộng dồn > AGENT_TURN_INPUT_BUDGET)
     │    ├─ trả lời mà không gọi tool cho câu cần nguồn → ép gọi tool 1 lần (gói D)
     │    └─ trả lời ngay sau lỗi argument sửa được → ép sửa 1 lần (LC-4)
     ├─ bước chốt (tool_choice=none) khi dừng sớm, kèm chỉ dẫn theo final_reason
     └─ lưu history: answer, usage thật theo trace, retrieval_snapshot (agent_steps, final_reason),
        conversation_state.facts (merge_facts)
```

`crm_query` trước khi gửi CRM: chặn hình dạng sai, bảng/cột bị chặn, sai kiểu giá trị; tải schema sống của bảng
gốc (cache 600 s) và chặn cột không có, kèm cột gần đúng.

## 2. Quyết định trong ngày

| # | Quyết định | Duyệt | Căn cứ |
|---|---|---|---|
| 1 | D-014 (tạm): câu so sánh chia chunk riêng từng model + chunk chung; cắt cột bảng về model được hỏi | Toma | Bộ C1–C7: cắt cột đạt 7/7; hạn mức (2 + 4 hay 3 + 2) chưa chốt |
| 2 | Kế hoạch Đợt 1 làm theo thứ tự E + D → C1–C3 → A → B → C4 | Toma (Q1–Q5) | [Kế hoạch Đợt 1](crm_agent_dot1_plan_2026-11-20.md) |
| 3 | Gói A, L2 `facts`: khung cố định, nội dung theo bảng; chỉ code ghi từ output tool; 10 dòng mỗi danh sách, 20 thực thể, TTL 10 lượt; nhãn chỉ từ cột cho phép (không SĐT, email khách, nội dung, ghi chú); 8 luật chống dùng nhầm | Toma | Lỗi mất UUID qua lượt (LC-3) |
| 4 | LC-2: timeout request riêng, không để SDK tự thử lại; runner thử lại 1 lần; ghi `provider_request_id`, `timeout_phase` | Toma | 4 lần treo 20 s trong 1 giờ; gửi lại cùng nội dung xong 2–5 s |
| 5 | LC-4: kiểm cột trong `crm_query` trước CRM (chính) + ép sửa 1 lần (lưới an toàn); không tự sửa cột, không dùng `enum` cột động | Toma | Tham khảo Pydantic AI `ModelRetry`, LangChain `sql_db_query_checker` |
| 6 | LC-7: trần token lượt nâng khỏi 15k; chỉ dẫn bước chốt khi `budget`/`limit` xét "đủ thì trả lời bình thường" trước | Toma | Lượt CRM 3 bước ~20k |
| 7 | Trần token lượt ở môi trường kiểm thử: **30000** (Toma đặt qua env; mặc định code 40000), tinh chỉnh tiếp khi kiểm thử | Toma | Một lượt 4 bước ~30k; 30k cho phép 3–4 bước rồi chốt |

## 3. Kết quả kiểm thử

Tất cả trên backend local của Toma, gpt-4.1-mini, đối chiếu Reporting API của CRM dev (chỉ đọc).

### Câu so sánh tài liệu (D-014)

| Lượt | Cấu hình | Kết quả |
|---|---|---|
| C1–C7, 07:14–07:29 | 3 + 2, cắt cột | Cắt cột đúng 7/7 (alias ASTRO-10S, 3 model, model lạ F86E, website). C2, C3 đủ khác biệt; C1 thiếu bảng Tool Manager/Multi axis; "spindle đồng thời" gán sai 4/5 lượt F54–F86; F86E bị suy đoán |

### Câu báo cáo CRM (cùng 7 câu, ba lần chạy)

Câu: (1) số tin trong hộp tin nhắn chờ; (2) 7 tin đó là gì; (3) tin "F54_…382" có ai phản hồi; (4) người nhắn có
thuộc khách công ty; (5) phiếu hỗ trợ mới tháng này theo trạng thái; (6) 5 khách mới nhất kèm sale; (7) khách thứ 2
có bao nhiêu thiết bị.

| Câu | Đáp án CRM | 09:19 (gói A) | 09:57 (+ LC-2, LC-4) |
|---|---|---|---|
| 1 | 18 tin (7 nếu bỏ tin nhân viên đã xoá, LC-6) | ❌ hết giờ | ✅ 18 (hết giờ 1 lần, thử lại được) |
| 2 | 7 tin mới nhất | ⚠️ đúng theo "mọi tin" | ✅ |
| 3 | 9 phản hồi (4 của khách, 5 của nhân viên) | ✅ nhờ facts (UUID) | ❌ lọc `title`, facts không có nhãn (LC-8) |
| 4 | Có: máy F54 thuộc khách C000418 (`official`) | ⚠️ đúng nhưng suy luận sai (LC-5) | ❌ cùng LC-8 |
| 5 | 2 phiếu, đều `closed` | ❌ hết giờ | ✅ số đúng, kèm câu sai "chưa lấy được" (LC-7) |
| 6 | C000612…C000608 kèm sale | ❌ đoán cột `name`, không sửa | ✅ cột bị chặn kèm gợi ý, LLM tự sửa; kèm câu sai (LC-7) |
| 7 | C000611: 0 thiết bị | ❌ đoán cột, không sửa | ✅ hiểu "khách thứ 2" nhờ facts |
| | | 1/7 | 5/7 |

Sau LC-7 (`0561487`) chưa chạy lại: tunnel CRM offline từ khoảng 10:00 UTC.

### Chi phí và độ trễ (7 câu, lần 09:57)

- Khoảng 0,033 USD cho 7 lượt; mỗi lượt 11k–32k token vào, 5–28 s (lượt có thử lại ~27 s).
- Mỗi bước LLM ~6–8k token vào, phần lớn là system prompt + guide `crm_query`; cache prompt đỡ được 70–95% ở bước 2 trở đi.

### Test tự động

`pytest tests` (worktree, `DATABASE_URL` giả): 1165 passed, 14 skipped, 1 failed có sẵn (`test_f86_baseline`: CSV
bị checkout CRLF trong worktree). Test mới trong ngày: `test_agent_loop_control.py` (17), `test_agent_session_facts.py`
(17), `test_agent_lc_fixes.py` (13), cộng các test so sánh và luật guide.

## 4. Vấn đề còn mở

| ID | Vấn đề | Hướng |
|---|---|---|
| LC-8 | Lượt liệt kê không chọn cột tên/tiêu đề thì facts không có nhãn | Chờ Toma: guide bắt chọn cột nhãn, hoặc nhãn từ đoạn đầu `content` |
| LC-6 | "Hộp tin nhắn chờ": mọi tin hay chỉ tin nhân viên chưa xoá | Chờ Toma/CRM |
| LC-5 | Khách của tin nhắn: `customer_id` không khoá ngoại, đường đúng `product_item_id.customer_id` | Hint bảng |
| LC-1 | Tra tên ra nhiều người → dừng hỏi lại | Đo bằng eval |
| CMP-1, CMP-2 | Chọn bảng chung có khác biệt; code tính sẵn khác/giống | Trước khi chốt D-014 |
| G1 | Eval `run_crm_agent_eval.py` chưa chạy lại sau Đợt 0/1 | Toma |
| – | Gói B (kiểm nguồn gốc giá trị), C4 (fan-out) | Theo kế hoạch Đợt 1 |

## 5. Cấu hình mới trong ngày

| Biến | Mặc định code | Môi trường kiểm thử |
|---|---|---|
| `AGENT_TURN_INPUT_BUDGET` | 40000 | 30000 (Toma) |
| `AGENT_HISTORY_TURNS` | 3 | mặc định |
| `CONTEXT_HISTORY_TURNS` | 10 | mặc định |
| `RETRIEVAL_COMPARE_PER_MODEL`, `RETRIEVAL_COMPARE_SHARED` | 2, 4 | 3, 2 (Toma) |

`AGENT_HISTORY_MESSAGES` không còn dùng. Timeout request tool-calling = `AGENT_LLM_TIMEOUT_S − 1` (không có biến riêng).
