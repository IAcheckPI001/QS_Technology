"""Ingest offline tài liệu kỹ thuật (PDF -> elements -> chunks/facts/assets).

Chạy bằng CLI trong venv riêng có Docling; module chatbot không được import gói này.
Ranh giới (kiểm bởi `tests/doc_ingest/test_import_boundary.py`):
- chỉ import `app.modules.doc_ingest.*` trong `app`; không dùng `app.core`, `app.db` hay module khác;
- docling, docling_core, pypdfium2, PIL chỉ được import trong `parse/` và `spike/`.
"""
