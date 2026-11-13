# Trạng thái luồng learning

Cập nhật: 2026-11-11

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- `POST /ai/learning` chạy tới hết **privacy**: nạp hội thoại → prefilter → privacy A–D.
- **Chưa có luồng tới tri thức**: chưa gọi LLM segment/extract, chưa lưu job hay record, chưa
  có outbox, embedding, vector index.
- Logic domain cho các bước [4]–[8] có code và test nhưng runtime chưa gọi tới.
- Route chưa có xác thực, chỉ mount khi `LEARNING_API_ENABLED=true`; chỉ dùng kiểm thử nội bộ.
- Chưa kiểm với Supabase thật và Ollama thật.

## Độ chín từng bước

| Bước | Trạng thái |
|---|---|
| [0] Route | có; chưa xác thực |
| [1] Ingestion, prefilter, privacy | có; kết quả không lưu |
| [2] Segmenter | chỉ có schema |
| [3] Extractor | chỉ có schema strict; chưa có prompt và lời gọi provider |
| [4] Ghép draft, [5] validate | có logic, chưa nối runtime |
| [6] Xung đột | một phần: chỉ luật; chưa so ngữ nghĩa, chưa tra DB |
| [7] Duyệt | có logic thuần; chưa persistence, API, UI |
| [8] Index | một phần: `Embedder`, `SearchIndex` chỉ là Protocol |
| [9] Retrieval của chatbot | chưa nối |

## Vấn đề mở

| Vấn đề | Ảnh hưởng |
|---|---|
| Registry chatbot thiếu `topics`, `connectors`, `parameters`, `alarm_codes`; `learning_ai/extraction/registry.py` rỗng | `validate_registry` báo `unknown_code` với registry thật |
| Chưa có bộ đánh giá tiếng Việt cho Ollama; mặc định `qwen3:1.7b` trong `.env.example` có thể quá nhỏ | Recall privacy chưa đo; đề xuất bắt đầu từ `qwen2.5:7b-instruct` |
| Bảng `history_support_chat` cần cột `created_at timestamptz not null default now()` | ORM cần cột này; chưa kiểm trên bảng thật |
| `retry_failed` trong request chưa có tác dụng | Chờ bảng job |

## Kết quả kiểm gần nhất

2026-11-11, từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 938 passed,
14 skipped (gồm `tests\learning_ai`).

## Bước tiếp theo

1. Thêm key registry còn thiếu, dựng một `RegistrySnapshot` dùng chung với query extraction.
2. Bộ đánh giá hội thoại CRM tiếng Việt có nhãn; đo recall của Ollama theo loại finding trước
   khi chọn model.
3. Prompt và lời gọi Segmenter/Extractor qua tầng provider, do learning service điều phối.
4. Bảng Supabase cho job (có `source_content_hash`), record/revision, outbox, chunk/vector;
   cần quyết định schema trước.
5. Thứ tự service: extract → assemble → validate → conflicts → `pending_review`.
6. Review API/UI, so xung đột ngữ nghĩa, `Embedder`/`SearchIndex`, worker outbox, retrieval
   theo `ChunkFilters`.
