# Ví dụ mục LOG và lỗi hay gặp

Các ví dụ dưới rút từ LOG thật của repo, có rút gọn. Dùng để tham khảo giọng văn và mức chi tiết,
không chép nguyên.

## Mục lục

1. [thay đổi](#thay-đổi)
2. [quyết định](#quyết-định)
3. [kiểm chứng](#kiểm-chứng)
4. [sự cố](#sự-cố)
5. [Mục ngắn ở luồng phụ thuộc](#mục-ngắn-ở-luồng-phụ-thuộc)
6. [Đính chính mục cũ](#đính-chính-mục-cũ)
7. [Lỗi hay gặp](#lỗi-hay-gặp)

## thay đổi

```
## 2026-11-19 · Chat chuyển sang doc_chunks_v2 (D-009 bước 6) · loại: thay đổi

- Vấn đề: chat production vẫn tra `doc_chunks` (bảng thử, 3 dòng); `doc_chunks_v2` chỉ eval dùng.
- Quyết định/luật: thay hẳn bảng cũ, rollback bằng revert; thêm `RETRIEVAL_APPROVED_ONLY` (mặc định
  true); coverage `technical_docs` nạp từ DB lúc khởi động (duyệt: Toma, 2026-11-19).
- File: `main.py` (`build_doc_repository`, `load_technical_coverage`), `doc_chunk_v2_repository.py`,
  `registry.py` (`extend_technical_coverage`), xoá `doc_chunk_repository.py`; test
  `tests/chatbot/test_retrieval_v2_wiring.py`.
- Kiểm chứng: `pytest tests\chatbot tests\api` → 594 passed; `pytest tests` → 1077 passed, 14 skipped,
  1 failed có sẵn (CRLF của CSV baseline trong worktree, blob git đúng hash); `check_ai_docs` đạt.
- Ảnh hưởng contract/API/schema/cấu hình: không đổi API; cờ mới `RETRIEVAL_APPROVED_ONLY`.
- Chưa kiểm / mở tiếp: chưa smoke trên Supabase thật; mọi chunk v2 đang `draft` nên production mặc
  định không có tài liệu (A-1).
```

Vì sao tốt: tiêu đề nói kết quả, có người duyệt, tách lỗi có sẵn, nêu rõ cái chưa kiểm và hệ quả
vận hành của cờ mặc định.

## quyết định

```
## 2026-11-14 · Chốt scope cộng điểm 0,003 (R-2) · loại: quyết định

- Toma chốt scope cộng điểm, mức 0,003 (vùng tốt 0,003–0,005), thay lọc cứng. Căn cứ: web2 trung bình
  3 bộ: lọc 0,807 / 0,736 → 0,003: 0,856 / 0,803; eval 40 câu `20261113-180934-diverse40`.
- Đánh đổi đã biết: khi intent đúng, lọc vẫn tốt hơn ở S8 (1,0 vs 0,887) → đo lại sau R-1.
- Chưa đổi code: `MatchV2Options` vẫn mặc định `filter`; đổi cùng kế hoạch R-1.
```

Vì sao tốt: có con số, có run id để tra, ghi đánh đổi (để người sau không đề xuất lại phương án đã
cân nhắc), và nói rõ quyết định **chưa** vào code.

## kiểm chứng

```
## 2026-11-18 · Kiểm B3 với lượt thật (khóa OpenAI hết hạn) · loại: kiểm chứng

- Lượt mới (phiên `10507a81…`) lỗi vì khóa OpenAI hết hạn (chi tiết ở LOG của chat-platform).
- Giao diện hiện đúng "thất bại ở bước Phân tích câu hỏi" và câu giải thích mã `expired_secret_key`.
- Kiểm chứng: `npm test` → 65 đạt; eslint → 0 lỗi.
- Chưa kiểm: số liệu của một lượt thành công (cần khóa mới).
```

Vì sao tốt: ghi cả khi kết quả không như mong đợi, trỏ phiên để tra lại, và có dòng "Chưa kiểm".

## sự cố

```
## 2026-11-19 · Lượt kiểm thử v2 không tới bước tra cứu (B-1) · loại: sự cố, kiểm chứng

- Vấn đề: lượt 10:26 (kênh crm, trace `295fa2aa…`) lỗi `provider_error`: `llm.chat_tools` 429
  `credit_balance_exhausted`; agent 0 bước, 0 tool → `retrieval_status=not_applicable`.
- Đã kiểm: checkout chạy server ở `d2c907e` (có PR #3); bước khởi động v2 chạy đúng trên DB thật
  (`approved_only=False`, coverage thêm F54).
- Chưa kiểm / mở tiếp: tra cứu v2 trong lượt thật, chờ nạp credit OpenAI (B-1).
```

Vì sao tốt: tách điều đã xác nhận khỏi điều chưa, nêu trace để tra, không đổ kết luận "v2 lỗi" khi
nguyên nhân là provider.

## Mục ngắn ở luồng phụ thuộc

```
## 2026-11-19 · `product_docs_ask` tra cứu trên doc_chunks_v2 · loại: thay đổi

- Theo website-qa (D-009 bước 6): retriever dùng chung chuyển sang `DocChunkV2Repository`, nên tool
  cũng đọc `doc_chunks_v2`, chỉ chunk `approved` khi `RETRIEVAL_APPROVED_ONLY=true`.
  Chi tiết: [website-qa/LOG.md](../website-qa/LOG.md) mục 2026-11-19.
```

## Đính chính mục cũ

Ví dụ minh hoạ (không có trong LOG thật):

```
## 2026-11-20 · Đính chính: mục 2026-11-14 "Bàn giao phiên…" ghi nhầm chưa commit · loại: tài liệu

- Mục 2026-11-14 nói thay đổi catalog → R-1 "chưa commit"; thực tế đã có trong commit `0da64e9`
  (kiểm bằng `git log -- backend/evals`). Không sửa mục cũ; STATE đã viết lại.
```

## Lỗi hay gặp

| Lỗi | Hệ quả | Thay bằng |
|---|---|---|
| Ghi "đã xong", "chạy tốt" chỉ dựa trên unit test | Agent sau tưởng đã kiểm trên môi trường thật | Ghi mức chín cụ thể và dòng "Chưa kiểm" |
| Ghi "đã chạy trên server" khi mới merge trên GitHub | Kết luận sai về hành vi production | Kiểm commit của checkout đang chạy, trace, log khởi động |
| Nối thêm vào STATE ("Cập nhật 19/11: …") | STATE tự mâu thuẫn với các dòng cũ | Viết lại đoạn bị ảnh hưởng |
| Quên dòng `current-state.md` hoặc luồng phụ thuộc | Bức tranh tổng sai, luồng khác không biết | Đi qua bảng lan truyền, grep câu cũ |
| Tự ghi "duyệt: Toma" khi Toma chưa duyệt | Quyết định giả, khó gỡ | Ghi "chờ Toma duyệt", loại `đánh giá` |
| Loại tự đặt ("triển khai, phân tích", "thử nghiệm", "kiểm thử") | Khó lọc LOG | Dùng danh sách loại chuẩn trong SKILL.md |
| Dán bảng số đo dài vào LOG | LOG phình nhanh, vượt 300 dòng | Đặt bảng trong `docs/ai/reports/`, trỏ tới |
| Gộp lỗi có sẵn chung với lỗi mới | Người sau sửa nhầm chỗ hoặc bỏ qua lỗi thật | Tách hai loại, ghi lý do |
| Ghi nội dung tin nhắn, token, secret khi dẫn trace | Vi phạm quy tắc log chỉ chứa metadata | Ghi id, outcome, mã lỗi, số liệu |
