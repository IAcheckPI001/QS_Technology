"""Hai bản `normalize_code` (chat và doc-ingest) phải cho cùng kết quả.

Ranh giới import của tool offline không cho dùng chung một hàm, nên test này chặn việc hai bản lệch nhau:
cột `doc_chunks_v2.codes` (nạp bởi doc-ingest) khớp chính xác với mã trích từ câu hỏi (chat).
"""

import pytest

from app.modules.chatbot.retrieval.codes import normalize_code as chat_normalize
from app.modules.doc_ingest.export.doc_chunks_v2 import normalize_code as ingest_normalize

CASES = [
    "M1920", "m1920", "M 1920", "#0008", "#12010", "X41", "CN3", "D4000", "G54", "AX1.ENA", "ax1.ena", "PUL1+",
    "X40-", "M0001", "ABCD123456", "ABCDE1", "A1234567", "24V", "GND", "F54", "", "  ", "M", "#", "1920", "M1920A",
    "M1920.", "M-1920", "Tiếng Việt", "X41\n",
]


@pytest.mark.parametrize("text", CASES)
def test_normalize_code_is_identical_in_chat_and_ingest(text: str) -> None:
    assert chat_normalize(text) == ingest_normalize(text)
