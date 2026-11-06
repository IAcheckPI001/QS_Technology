# Fixture Docling: f86_ocr

Sao nguyên `raw/` của lần chạy CLI `data/ingest_runs/f86/20261103-113235` (2026-11-03,
`--ocr auto`); không sửa tay. PDF không có text layer nên mọi trang được OCR (RapidOCR
backend torch, xem `profile.json`). Không có `p{n}.words.json` (không có text layer).
Dùng cho T-17 (heading bị gắn `page_header`, I-21), T-06 và T-07 trên trang OCR.

| Mục | Giá trị |
|---|---|
| PDF | `F86_Operation Manual (English Version).pdf` (97 trang) |
| sha256 PDF | `660ed264c2cfa10d40cd731126ac5beb4c55e6e8db7734475261b66080d9ad27` |
| Trang (pdf_page_index) | 5–17 |
| docling | 2.145.0 |
| docling-core | 2.105.0 |
| pypdfium2 | 5.14.0 |

Sinh lại (venv ingest, từ thư mục `backend`), rồi chép `raw/p005…p017.docling.json` và
lọc `raw/profile.json` về trang 5–17:

```powershell
..\.venv-ingest\Scripts\python.exe -m app.modules.doc_ingest.cli run `
    --pdf "<F86_Operation Manual (English Version).pdf>" --pages 1-17 --doc-id f86 --profile qs_controller
```

OCR có thể khác giữa các lần chạy/phiên bản; test chỉ kiểm các chuỗi đã ghi trong file này.
