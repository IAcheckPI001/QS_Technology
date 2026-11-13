---
paths:
  - "backend/app/modules/doc_ingest/**"
  - "backend/tests/doc_ingest/**"
---

# Luồng doc-ingest (chunking tài liệu)

Đọc trước khi sửa: `docs/ai/flows/doc-ingest/README.md` và `STATE.md`.

- Tool offline: không import `chatbot`, không ghi database, không nằm trong image chat.
- Luật T-xx, V-xx và schema là contract đã duyệt (`docs/ai/reports/p1_normalization_contract.md`,
  `p2_chunk_contract.md`); đổi luật phải có bằng chứng và người duyệt.
- Không chắc thì đưa vào hàng review, không gán im lặng.
- Run mới dùng run id mới; không ghi đè thư mục run cũ trong `data/ingest_runs/`.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest`.
- Xong việc: viết lại `STATE.md`, thêm mục vào đầu `LOG.md` của luồng.
