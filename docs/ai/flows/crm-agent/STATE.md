# Trạng thái luồng crm-agent

Cập nhật: 2026-11-16

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- **Thử nghiệm.** Mặc định `CRM_REPORT_ENABLED=false`, agent chỉ có `product_docs_ask`.
- Khi bật tool CRM, mặc định là phương án C (`crm_schema` + `crm_query`, D-005). Phương án A
  (`crm_report` + `crm_records`) vẫn chạy qua `CRM_TOOLS=catalog`.
- Code phương án C **đã commit** trên `feature/deploy_ai_service` (commit `4a4b5b5`,
  2026-11-14), gồm thay đổi giới hạn gọi tool ngày 2026-11-12 (đối chiếu code 2026-11-16).
- Model của agent: **gpt-4.1-mini** (quyết định 2026-11-12); guide `crm_query` tinh chỉnh cho
  model này. `AGENT_MODEL` chưa có trong `.env.example` và chưa đặt ở môi trường chạy.
- Luật nghiệp vụ và ngày nằm trong code, áp cho mọi model:
  - năm câu hỏi không nêu bị bỏ;
  - kỳ trong filters được chuyển thành `date_range`;
  - "khách hàng" không tính spam;
  - "nhân viên sales" theo vai trò, chỉ tài khoản còn dùng;
  - có kỳ thì bỏ `is_current`.
- Dữ liệu CRM (kể cả liên hệ khách hàng) đi tới nhà cung cấp LLM khi bật tool CRM.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| `AgentRunner`: vòng lặp, deadline, cancel, giới hạn | có, test bằng fake | Trần chung chỉ đếm call không bị `tool_call_limit` (2026-11-12); `plan()` để trống |
| `product_docs_ask` + chọn model theo capabilities | có, test bằng fake | Capabilities nằm trong code; registry có thêm 10S, 10i (2026-11-14) |
| `crm_schema`, `crm_query` (C) | có, đã commit; eval gpt-4.1-mini 78/81 | Trần `crm_query`: 6 lần thử, 4 lần gửi CRM |
| Giám sát query (trace, audit sau `CRM_QUERY_AUDIT_LOG`) | có, test bằng fake | Chưa xem trên log server thật |
| `crm_report`, `crm_records` (A) | có | Catalog kiểm bằng HTTP thật 2026-11-10 |
| Phân quyền tool theo role/scope | chưa có | Mọi nhân viên dùng mọi tool |
| SSE tiến trình, stream token câu trả lời cuối | chưa có | Câu trả lời cuối là một `delta` |
| Tool ghi dữ liệu, chi tiết phiếu, web search, MCP, provider khác OpenAI | chưa có | |

## Vấn đề mở

| Vấn đề | Ảnh hưởng |
|---|---|
| `print()` debug in `AssistantTurn`, body gửi CRM và toàn bộ response CRM ra stdout (`agent/runner.py:289`, `providers/crm_api.py:199,239,255`) | PII khách hàng nằm trong log tiến trình; vi phạm luật "log chỉ metadata"; gỡ trước deploy |
| `chat_history.model` và chi phí ước tính lấy theo `OPENAI_MODEL` và đơn giá gpt-4o-mini, không theo `AGENT_MODEL` (`services/chat_service.py`) | Đặt `AGENT_MODEL` thì history ghi sai model, chi phí thấp hơn thực tế |
| LLM tự suy username từ tên/câu trả lời trước (thiếu `@qstcnc.com`); guide `crm_query` chưa có luật "username chỉ lấy nguyên văn từ kết quả tool" (kiểm code 2026-11-16) | Query rỗng, gọi lại tới hết lượt |
| Câu trả lời khi chạm giới hạn vẫn có thể nói "thử lại sau". Luật "trả lời phần đã có" có trong `agent/prompts.py` từ 2026-11-02 nhưng chưa đủ hiệu lực | Gây hiểu nhầm |
| "Bản ghi đầu/cuối của từng người": CRM không có top-1 theo nhóm, `min/max` chỉ cho cột số; guide chưa hướng dẫn tách query | Cần mỗi người một query; nhiều người dễ chạm trần |
| Chưa có case eval câu hỏi nhiều sale hai lượt (`crm_agent_cases.json` 46 case); chưa eval lại sau thay đổi cách đếm giới hạn | Chưa đo được hai lỗi trên |
| "Khách được hỗ trợ" của phiếu: `customer_organization_id` (trống ở dữ liệu hiện có) hay `product_item_id.customer_id` (chủ hiện tại của máy) chưa được chốt | r1: LLM chọn sai hoặc hỏi lại; cần Toma/CRM chốt |
| Còn tra `auth_users.id` trước khi lọc thay vì lọc thẳng `…username` (q7, q12 1/3) | Thêm 1–2 lần gọi |
| `backend/.env.example`: thiếu `AGENT_MODEL`, `CRM_TOOLS`; `AGENT_MAX_STEPS=5` lệch mặc định code (6); `CRM_REPORT_ENABLED=true` kèm URL ngrok cụ thể | Cấu hình mẫu dễ gây nhầm khi triển khai |
| Mô tả cột `is_current` của CRM ("Count current workload…") mâu thuẫn với luật có kỳ | Code đã ép; đề nghị CRM sửa mô tả |
| Timestamp CRM là UTC; `date_range` và nhóm `_day/_month/_year` cắt theo ngày UTC (ranh giới 07:00 giờ VN) | Bản ghi 00:00–07:00 giờ VN ở hai đầu kỳ rơi sang kỳ khác; chờ CRM thêm `timezone` |
| Index tĩnh lệch cột so với CRM ở 13 bảng (chủ yếu module kho) | Thiếu giá trị hợp lệ của cột mới; cần dump mới rồi chạy `build_crm_schema_index.py` |
| `contains` phân biệt dấu tiếng Việt | Tên gõ không dấu trả 0 |
| Chi phí LLM gpt-4.1-mini khoảng 2,5 lần gpt-4o-mini mỗi câu | Token giảm 30% bù một phần |
| `product_user_access`, `product_agents` chưa khớp mô tả CRM (giữ nguyên, Toma 2026-11-12) | Số liệu có thể lệch màn hình CRM |
| Token CRM không được làm mới; bảng ngoài `customers` cần `auth.manage_roles` | `crm_auth_failed` ở phiên dài; sale thường nhận `crm_forbidden` |
| `CRM_CHAT_FLOW` mặc định `agent` dù thử nghiệm (D-006) | Xem lại trước production |

## Kết quả kiểm gần nhất

- 2026-11-16, commit `671fe22`, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` →
  1120 passed, 14 skipped.
- 2026-11-12, eval gpt-4.1-mini 27 case × 3 ([báo cáo](../../reports/crm_agent_eval_C_gpt41_2026-11-12.md)):
  - mốc sáng 50/81 → (a) 64 → (b) 69 → (c) **78/81**; 21 case cũ 38/63 → 60/63;
  - token vào mỗi câu ~29,9k → 21,0k; phần cố định mỗi bước 5.868 → 4.251 token.
- 2026-11-12, kiểm `POST /reports/query` cho câu hỏi nhiều sale: đếm gộp một query đúng (259/76/8);
  "khách đầu tiên của từng sale" phải tách query.
- Đợt cũ (đo nền 2026-11-11, đo lại sáng 2026-11-12 hai model): xem LOG.

## Bước tiếp theo

1. Guide `crm_query`: username chỉ lấy nguyên văn từ kết quả tool; nhiều người thì đếm gộp, bản
   ghi đầu/cuối tách query; khi chạm giới hạn thì trả lời phần đã có.
2. Thêm case câu hỏi nhiều sale (hai lượt) vào eval; Toma eval lại sau thay đổi giới hạn gọi.
3. Chốt nghĩa "khách được hỗ trợ" của phiếu (r1).
4. Sửa `backend/.env.example` (`AGENT_MODEL`, `CRM_TOOLS`, `AGENT_MAX_STEPS`); đặt
   `AGENT_MODEL=gpt-4.1-mini` ở môi trường chạy.
5. Gửi CRM: tham số `timezone`, sửa mô tả `is_current`, dump schema mới.
6. P1 semantic layer; phân quyền tool theo role/scope; backlog SSE tiến trình, stream token, MCP.
