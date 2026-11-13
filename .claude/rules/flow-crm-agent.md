---
paths:
  - "backend/app/modules/chatbot/agent/**"
  - "backend/app/modules/chatbot/tools/**"
  - "backend/app/modules/chatbot/reporting/**"
  - "backend/app/modules/chatbot/schemas/system/**"
  - "backend/app/modules/chatbot/providers/crm_api.py"
  - "backend/evals/**"
  - "backend/scripts/build_crm_schema_index.py"
---

# Luồng crm-agent (agent gọi tool trên kênh CRM)

Đọc trước khi sửa: `docs/ai/flows/crm-agent/README.md` và `STATE.md`.

- Luồng thử nghiệm: `CRM_REPORT_ENABLED` mặc định tắt; mặc định `CRM_TOOLS=query`
  (phương án C, D-005). Không mô tả như đã hoàn thiện.
- Tool mới theo contract `tools/base.py`, đăng ký ở `agent/setup.py`; gọi CRM chỉ qua
  `providers/crm_api.py`.
- Bảng/cột bị chặn của `crm_query` nằm ở `reporting/raw/policy.py`; đổi danh sách là đổi
  chính sách dữ liệu, cần người duyệt.
- Test, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests\chatbot`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md` của luồng.
