# Fixture golden Docling: f54

Sinh tự động bởi `app.modules.doc_ingest.parse.make_fixture`; không sửa tay.
Docling JSON lấy từ output spike (cấu hình ghi trong `docs/ai/reports/parsing_spike.md`),
đã bỏ `pages[].image` và `pictures[].image`. `p{n}.words.json`: từ text layer + bbox (pypdfium2).
`p{n}.objects.json`: bitmap nhúng (bounds + px) và nét vector (pypdfium2; đối tượng trong Form XObject
lấy bounds của form).

| Mục | Giá trị |
|---|---|
| PDF | `F54_Operation Manual (English Version)_V.02.pdf` |
| sha256 PDF | `7cd0e69c1e94d41649fd361a47bd089279897b085f8c2b0b93c99dc1591bce21` |
| Trang (pdf_page_index) | 9, 11, 14, 18, 19, 40, 167, 168, 169, 170, 171 |
| docling | 2.145.0 |
| docling-core | 2.105.0 |
| pypdfium2 | 5.14.0 |

Sinh lại (venv ingest, từ thư mục `backend`; chạy spike trước để có `--spike-dir`):

```powershell
..\.venv-ingest\Scripts\python.exe -m app.modules.doc_ingest.parse.make_fixture `
    --pdf "<F54_Operation Manual (English Version)_V.02.pdf>" --spike-dir <spike output>\f54 `
    --out tests\doc_ingest\fixtures\docling\f54
```
