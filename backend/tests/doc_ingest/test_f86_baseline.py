"""RB-01 (BL-03): khóa baseline chunk F86 biên soạn tay; đổi CSV phải đổi hash có chủ đích."""
import hashlib
from pathlib import Path

BASELINE_CSV = (
    Path(__file__).resolve().parents[2]
    / "app" / "modules" / "chunking_loader" / "documents" / "doc_chunks_f86.csv"
)
BASELINE_SHA256 = "a8629f5878fc1d4f16c2706d7b0440a46fe9ecfe098e0b7ec525f16c878f02aa"


def test_f86_baseline_csv_unchanged() -> None:
    assert hashlib.sha256(BASELINE_CSV.read_bytes()).hexdigest() == BASELINE_SHA256
