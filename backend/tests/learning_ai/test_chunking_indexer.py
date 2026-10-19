from typing import Sequence
from uuid import UUID

from app.modules.learning_ai.chunking.chunk_builder import build_chunks
from app.modules.learning_ai.indexing.indexer import sync_record
from app.modules.learning_ai.schemas.derived import Chunk
from app.modules.learning_ai.schemas.knowledge_record import PrivacyInfo, RecordStatus, Visibility


class FakeIndex:
    def __init__(self) -> None:
        self.rows: dict[UUID, dict[str, str]] = {}

    def existing_hashes(self, record_id: UUID, embedding_model: str) -> dict[str, str]:
        return dict(self.rows.get(record_id, {}))

    def upsert(self, chunks: Sequence[Chunk], vectors: dict[str, list[float]], embedding_model: str) -> None:
        for c in chunks:
            self.rows.setdefault(c.record_id, {})[c.chunk_id] = c.embedding_text_hash

    def delete_record(self, record_id: UUID, keep_chunk_ids: set[str] = frozenset()) -> int:
        rows = self.rows.get(record_id, {})
        stale = [k for k in rows if k not in keep_chunk_ids]
        for k in stale:
            del rows[k]
        return len(stale)


class FakeEmbedder:
    model_id = "fake-embed@1"

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[float(len(t))] for t in texts]


def test_small_record_is_single_full_chunk(make_param_record, reg):
    record = make_param_record()

    chunks = build_chunks(record, reg)

    assert len(chunks) == 1
    c = chunks[0]
    assert (c.section, c.chunk_index, c.chunk_count) == ("full", 0, 1)
    assert "Phạm vi: chỉ áp dụng cho F86" in c.display_text
    assert "P01 (Pr.01)" in c.embedding_text
    assert c.filters.parameter_ids == ["P01"]
    assert c.filters.registry_version == record.provenance.registry_version


def test_procedure_split_keeps_units_and_safety_header(make_procedure_record, reg):
    chunks = build_chunks(make_procedure_record(), reg, max_chars=900)

    assert [c.section for c in chunks] == ["steps:1-2", "steps:3-5", "steps:6-6"]
    assert all("Ngắt nguồn trước khi mở vỏ" in c.display_text for c in chunks)
    assert ["Không siết quá lực" in c.display_text for c in chunks] == [False, False, True]
    assert "3. Thao tác bước 3" in chunks[1].display_text
    assert "5. Thao tác bước 5" in chunks[1].display_text
    assert [c.prev_chunk_id for c in chunks] == [None, chunks[0].chunk_id, chunks[1].chunk_id]
    assert [c.next_chunk_id for c in chunks] == [chunks[1].chunk_id, chunks[2].chunk_id, None]


def test_chunk_ids_are_deterministic(make_procedure_record, reg):
    record = make_procedure_record()

    first = [c.chunk_id for c in build_chunks(record, reg, max_chars=900)]
    second = [c.chunk_id for c in build_chunks(record, reg, max_chars=900)]
    assert first == second


def test_sync_record_reuses_unchanged_vectors(make_param_record, reg):
    record = make_param_record(status=RecordStatus.APPROVED)
    index, embedder = FakeIndex(), FakeEmbedder()

    first = sync_record(record, reg, index, embedder)
    second = sync_record(record, reg, index, embedder)

    assert (first.upserted, first.reused, first.skipped_reason) == (1, 0, None)
    assert (second.upserted, second.reused) == (0, 1)
    assert len(embedder.embedded) == 1


def test_sync_record_removes_non_approved_record(make_param_record, reg):
    record = make_param_record(status=RecordStatus.APPROVED)
    index, embedder = FakeIndex(), FakeEmbedder()
    sync_record(record, reg, index, embedder)

    superseded = record.model_copy(deep=True)
    superseded.lifecycle.status = RecordStatus.SUPERSEDED
    result = sync_record(superseded, reg, index, embedder)

    assert result.deleted == 1
    assert result.skipped_reason == "status=superseded"
    assert index.rows[record.record_id] == {}


def test_sync_record_skips_restricted_record(make_param_record, reg):
    record = make_param_record(status=RecordStatus.APPROVED,
                               privacy=PrivacyInfo(redaction_applied=True, visibility=Visibility.RESTRICTED))

    result = sync_record(record, reg, FakeIndex(), FakeEmbedder())

    assert result.skipped_reason == "visibility=restricted"
