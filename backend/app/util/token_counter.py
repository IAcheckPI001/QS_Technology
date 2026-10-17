

from functools import lru_cache

import tiktoken


@lru_cache(maxsize=16)
def _get_encoding(model: str):
    """Cache tokenizer để tránh khởi tạo lại nhiều lần."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback chỉ là ước lượng theo encoding này,
        # không đảm bảo chính xác với model không được hỗ trợ.
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str) -> int:
    """
    Đếm token của một chuỗi văn bản theo tokenizer tương ứng.

    Lưu ý: Kết quả không bao gồm overhead của message,
    role, tool schema hoặc metadata trong request.
    """
    if not text:
        return 0

    encoding = _get_encoding(model)
    return len(encoding.encode(text))