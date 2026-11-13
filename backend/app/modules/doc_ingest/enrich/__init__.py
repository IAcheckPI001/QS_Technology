"""Bước 3: làm giàu tiếng Việt cho chunk lá (contract C2 §8, D-008).

- `checks`: kiểm tự động đầu ra (độ dài, mã kỹ thuật phải có trong content) — không phụ thuộc SDK;
- `prompt`: prompt hệ thống + thông điệp người dùng, `PROMPT_VERSION`;
- `client`: gọi OpenAI (chỉ venv chính có SDK `openai`; import khi cần);
- `runner`: chọn chunk, ước tính chi phí, gọi client, ghi `build/enrichment.jsonl` (append-only, chạy tiếp được).
"""
