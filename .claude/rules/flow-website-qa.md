---
paths:
  - "backend/app/modules/chatbot/adapters/**"
  - "backend/app/modules/chatbot/stages/**"
  - "backend/app/modules/chatbot/analysis/**"
  - "backend/app/modules/chatbot/orchestration/**"
  - "backend/app/modules/chatbot/retrieval/**"
  - "backend/app/modules/chatbot/clarification/**"
  - "backend/app/modules/chatbot/prompts/**"
  - "backend/app/modules/chatbot/extraction/**"
  - "src/chatbot/**"
  - "widget-backend/**"
---

# Luồng website-qa (tra cứu, hỏi đáp trên website)

Đọc trước khi sửa: `docs/ai/flows/website-qa/README.md` và `STATE.md`; stage bảo mật:
`docs/ai/security-stage-pipeline.md`.

- `RetrievalPipeline` được tool `product_docs_ask` của crm-agent dùng lại; đổi nó thì chạy
  cả test agent.
- Handler orchestration không gọi LLM; handoff là scaffold; retrieval mới ở mức test.
- Test, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api`;
  `npm test` trong `widget-backend/`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md` của luồng.
