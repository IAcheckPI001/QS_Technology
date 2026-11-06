"""PI-07: snapshot từ vựng registry của doc_ingest khớp registry chatbot.

doc_ingest không được import chatbot (test ranh giới), nên từ vựng được chép ra file dữ
liệu; test này đọc cả hai phía. Registry đổi thì sinh lại snapshot trong cùng commit.
"""
import json
from pathlib import Path

from app.modules.chatbot.extraction.registry import REGISTRY

SNAPSHOT = (Path(__file__).resolve().parents[2] / "app" / "modules" / "doc_ingest" / "profiles"
            / "registry_snapshot.json")


def test_doc_ingest_registry_snapshot_matches_registry() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for key in ("product_models", "aliases", "control_interface"):
        assert snapshot[key] == REGISTRY[key], key
