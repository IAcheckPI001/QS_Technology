"""crm-sync: đồng bộ tài liệu công khai trên CRM (`company-docs/website-tree`) vào luồng chunking.

Giai đoạn 1 (2026-11-19): phát hiện mới/đổi phiên bản, tải PDF, sinh manifest nháp; pipeline `run`/`build` có sẵn
tạo chunk. Không ghi database; nạp và gỡ phiên bản cũ trong `doc_chunks_v2` thuộc giai đoạn 2.
"""
