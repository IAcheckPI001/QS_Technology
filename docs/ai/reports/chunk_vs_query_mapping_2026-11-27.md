# Đối chiếu dữ liệu chunk với bước hiểu câu hỏi và `match_doc_chunks_v2` (2026-11-27)

Báo cáo đánh giá, chỉ đọc. Nguồn: code `chatbot/schemas/system/analysis.py`, `extraction/registry.py`,
`retrieval/retriever.py`, `retrieval/fts_query.py`, `repositories/doc_chunk_v2_repository.py`, `sql/doc_chunks_v2.sql`;
phân bố metadata của 858 chunk lá active trên Supabase thật (2026-11-27). Không đổi code, không ghi DB.

## 1. Hai đầu của đường ống

```text
Câu hỏi ─► Analysis (LLM gpt-4o-mini + luật registry)                 Chunk (doc_ingest / curated → loader)
            sub_query: standalone_query, intent, route                 domain, scopes, chunk_type
            entities: product_models, control_interface,               product_models, applies_to_models
                      spec_attributes, unresolved_mentions             control_interface, spec_attributes
            retrieval_scope: targets(domain, scopes), model_filter     codes, keywords, section_path
                 │                                                     content, embed_text → embedding, fts
                 ▼                                                     review_status, audience, is_active
          RetrievalRequest ─► Retriever ─► match_doc_chunks_v2 ◄────────────────┘
```

## 2. Bảng ghép từng trường

| Câu hỏi (analysis) | Cách vào SQL | Cột chunk | Kiểu tác động | Hiện trạng dữ liệu chunk (lá active) |
|---|---|---|---|---|
| `standalone_query` | embedding `text-embedding-3-small` | `embedding` (từ `embed_text`) | **xếp hạng chính** (vector top 20) | `embed_text` = model · tài liệu · đường dẫn mục + từ khoá + `content`; 0/786 chunk CRM có làm giàu tiếng Việt |
| `standalone_query` sau `clean_fts_query` (bỏ model, từ chức năng) | `websearch_to_tsquery('simple')`, `&` → `\|` | `fts` (từ `embed_text`) | xếp hạng (FTS top 20) | Chunk 601 `en` / 185 `vi`; câu hỏi tiếng Việt chỉ khớp mã, tên riêng, từ tiếng Anh |
| intent → `targets.domain` (registry) | **lọc cứng** `domain = p_domain` | `domain` | lọc | `product_catalog` 72, `technical_docs` 786 |
| intent → `targets.scopes` | **cộng 0,003** (`scope_mode=boost`) | `scopes` | cộng điểm rất nhỏ | installation/operation/configuration có; **`maintenance` chỉ 1 chunk** (F10T); catalog không có scope |
| `model_filter` (từ `product_models`) | **lọc cứng** `product_models && p_models` | `product_models` | lọc | Catalog: `6AV`, `10i`, `10S`… ; tài liệu kỹ thuật: `6AVE`, `10iV` (tên khác nhau giữa hai nguồn) |
| `product_scope_mode = comparison` | retriever tách mỗi model một lần gọi | `product_models` | chia hạn mức 2 + 4 chung | — |
| `control_interface` | lọc: giữ chunk khớp **hoặc rỗng** | `control_interface` | lọc mềm | Tài liệu kỹ thuật: chỉ 27 chunk `pulse_train`, còn lại rỗng → gần như không lọc |
| `spec_attributes` | cộng `spec_boost` 0,005 | `spec_attributes` | cộng điểm nhỏ | Catalog 9 thuộc tính đủ; kỹ thuật chủ yếu `io` 118, `ports` 113, `monitor_size` 22, `dimension` 7 |
| (không có) | `p_codes` = rỗng trong production | `codes` | **nhánh mã tắt** | 457/786 chunk có `codes` (6.364 mã: G54, `#4130`, CN…) nhưng không dùng; `retrieval/codes.py` chỉ eval dùng |
| (không có) | `p_chunk_types` rỗng, `type_boost` 0 | `chunk_type` | không dùng | figure 268, overview 135, procedure 128, table 100, wiring 96, parameter 45… |
| (không có) | — | `applies_to_models` | không dùng | 0 chunk có giá trị |
| kênh (website/CRM) | lọc `audience`, `is_active`; `approved_only` | `audience`, `review_status` | lọc | mọi chunk `public`, 0 `approved` |
| — | `min_similarity` 0,25 + `top_k` 6 + gom cha (tối đa 5) | `parent_id` | cắt ở retriever | chunk cha không embed (D-008) |

Điểm cuối: `fused = 1/(60+hạng vector) + 1/(60+hạng FTS) [+ 1/(60+hạng mã)] + 0,003 scope + 0,005 spec`. Hạng 1 và
hạng 2 của một nhánh chênh nhau khoảng 0,00027, nên hai điểm cộng nhỏ vẫn đủ đảo vài hạng nhưng không cứu được chunk
ngoài top 20 của cả hai nhánh.

## 3. Chỗ lệch giữa hai đầu

1. **Lọc cứng chỉ còn hai trục, cả hai đều do LLM quyết:** `domain` (từ intent) và `product_models`. Sai một trong hai
   là chunk đúng không bao giờ vào ứng viên. Ví dụ đã đo: `lookup.product_info` chỉ tìm catalog (G114 CN1 của 6AVE),
   `Astro 10i` → `10i` (chỉ catalog) trong khi tài liệu gắn `10iV` (G108, G118 → `no_docs`).
2. **Tên model khác nhau giữa catalog và tài liệu kỹ thuật** (`6AV`/`6AVE`, `10i`/`10iV`): không có ánh xạ "cùng
   dòng" khi lọc; câu hỏi `6AV` lọc ra 0 chunk kỹ thuật dù 147 chunk `6AVE` tồn tại.
3. **Scope `maintenance` gần như rỗng:** intent `troubleshoot.error` nhắm `maintenance` nhưng chunk báo lỗi/alarm được
   gán `operation`/`configuration` (chỉ 1 chunk `alarm`). Nhờ chế độ cộng điểm nên không mất chunk, nhưng scope không
   giúp gì; nếu đổi về lọc cứng thì mất hết.
4. **Mã kỹ thuật được trích ở cả hai đầu nhưng không nối:** chunk có `codes`, câu hỏi có mã (CN5, `#4130`, G54), registry
   có `MODEL_SPECIFIC_PATTERN`, `retrieval/codes.py` có chuẩn hoá giống hệt (test parity) — nhưng production không truyền
   `p_codes`. Mã chỉ khớp qua FTS (bị tách token, `#4130` thành `4130`).
5. **Ngôn ngữ:** câu hỏi tiếng Việt, 76% chunk kỹ thuật tiếng Anh, chưa làm giàu tiếng Việt → FTS gần như chỉ khớp mã và
   tên; vector cosine Việt–Anh 0,4–0,65 nên `min_similarity` 0,25 không lọc được gì.
6. **`chunk_type` và `spec_attributes` giàu ở chunk nhưng nghèo ở câu hỏi:** analysis không trích loại câu trả lời mong
   muốn (bảng chân, thủ tục, tham số), nên `p_chunk_types`/`type_boost` không dùng; `spec_attributes` chỉ có 9 giá trị kiểu
   catalog, không có từ vựng cho tài liệu kỹ thuật (thủ tục, alarm, tham số).
7. **Chunk rỗng vẫn qua mọi bộ lọc:** chunk chỉ có tiêu đề hình đúng domain, model, scope nên lọt top 6 và chiếm chỗ
   (xem [chunk_pass_vs_retrieval](chunk_pass_vs_retrieval_2026-11-26.md)).
8. **`control_interface` của chunk kỹ thuật gần như rỗng** nên lọc theo interface không có tác dụng với tài liệu kỹ thuật;
   chỉ catalog được lọc thật.

## 4. Đề xuất (chờ Toma quyết, chưa làm; mỗi mục cần đo trên bộ vàng trước khi bật)

| # | Việc | Luồng |
|---|---|---|
| 1 | Bảng "dòng model" trong registry (`6AV`↔`6AVE`, `10i`↔`10iV`…) dùng khi lọc `technical_docs`, hoặc chuẩn hoá `product_models` khi nạp | website-qa + doc-ingest |
| 2 | Bật nhánh mã: truyền mã trích từ câu hỏi (`retrieval/codes.py`) vào `p_codes` | website-qa |
| 3 | Gán scope `maintenance` cho chunk alarm/xử lý sự cố khi chunk (manifest `scope_rules`), hoặc bỏ scope khỏi `troubleshoot.error` | doc-ingest |
| 4 | Intent → `chunk_type` ưu tiên (`guide.installation` → wiring/pinout/table; `guide.configuration` → parameter) qua `type_boost`, đo trước | website-qa |
| 5 | Làm giàu tiếng Việt (2c) hoặc dịch câu hỏi cho nhánh FTS; đo riêng | doc-ingest / website-qa |
| 6 | Không embed chunk chỉ-tiêu-đề, hoặc gộp cha | doc-ingest |
| 7 | Nới lọc `domain` khi intent là `lookup.product_info` mà câu nhắc cổng/mã (luật `r1`/`r2` RT-1 đã có code, chưa đo) | website-qa |
