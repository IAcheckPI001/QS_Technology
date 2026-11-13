"""Bước 3 (làm giàu tiếng Việt): client giả, không gọi API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.modules.doc_ingest.build.builder import build_chunks
from app.modules.doc_ingest.build.loader import ENRICHMENT_FILE, RunInput, enrichment_key, load_enrichment
from app.modules.doc_ingest.enrich import runner
from app.modules.doc_ingest.enrich.checks import check_output, chunk_context, missing_codes
from app.modules.doc_ingest.enrich.client import EnrichResult
from app.modules.doc_ingest.profile import load_profile
from app.modules.doc_ingest.schemas.chunk import ChunkQuality, DraftChunk, EnrichmentOutput, EnrichmentRecord
from tests.doc_ingest.chunk_helpers import MANIFEST, Doc, report

SENT = "Connect the X41 input to terminal CN3 and set parameter #12010 before homing the axis. "
GOOD = EnrichmentOutput(summary_vi="Hướng dẫn đấu ngõ vào X41 vào cổng CN3 và đặt tham số #12010.",
                        faq_vi=["Đấu X41 vào cổng nào?", "Cần đặt tham số nào trước khi về home?"],
                        keywords_vi=["đấu dây", "về home"])


class FakeEnricher:
    model = "fake-model"

    def __init__(self, output: EnrichmentOutput = GOOD, fail: set[str] = frozenset()) -> None:
        self.output, self.fail, self.calls = output, set(fail), []

    def enrich(self, chunk: DraftChunk) -> EnrichResult:
        self.calls.append(chunk.chunk_key)
        if chunk.chunk_key in self.fail:
            raise RuntimeError("api down")
        return EnrichResult(self.output, 700, 250)


def _doc(notes: int = 3, repeat: int = 8) -> Doc:
    """`notes` khối ~700 ký tự (không gộp overview) → 3 lá + 1 cha khi `notes = 3`."""
    doc = Doc()
    doc.add("heading", "2.3 Homing", path=("2.3 Homing",))
    for i in range(notes):
        doc.add("label_heading", f"Note {i}:", path=("2.3 Homing",), label=f"Note {i}:")
        doc.add("text", f"Step text {i}. " + SENT * repeat, path=("2.3 Homing",), label=f"Note {i}:")
    return doc


def _build(doc: Doc, run_dir: Path, enrichment: dict[str, EnrichmentRecord] | None = None, embed_max: int = 800):
    run = RunInput(run_dir=run_dir, report=report([1]), elements=doc.elements, tables={}, review=[],
                   enrichment=enrichment or {})
    base = load_profile("qs_controller")
    profile = base.model_copy(update={"chunking": base.chunking.model_copy(update={"embed_max_tokens": embed_max})})
    return build_chunks(run, MANIFEST, profile)


def _record(chunk: DraftChunk, output: EnrichmentOutput = GOOD) -> EnrichmentRecord:
    return EnrichmentRecord(**output.model_dump(), content_hash=chunk.content_hash, chunk_key=chunk.chunk_key,
                            section_path=list(chunk.section_path),
                            model="fake-model", prompt_version="v1", created_at="2026-11-13T00:00:00")


def test_build_uses_enrichment_for_leaves_only(tmp_path: Path) -> None:
    """Chunk lá có bản ghi khớp content_hash → tóm tắt + câu hỏi vào embed_text, từ khóa VI giữ, status draft;
    chunk cha không làm giàu (D-008); 2c đạt khi mọi lá đã làm giàu."""
    plain = _build(_doc(), tmp_path)
    leaves = [c for c in plain.chunks if c.chunk_role != "parent"]
    assert plain.quality.enrichment.passed is None
    records = {enrichment_key(c.content_hash, c.section_path): _record(c) for c in leaves}
    parent = next((c for c in plain.chunks if c.chunk_role == "parent"), None)
    if parent is not None:
        records[enrichment_key(parent.content_hash, parent.section_path)] = _record(parent)   # cha có bản ghi cũng không dùng
    result = _build(_doc(), tmp_path, records)
    for c in result.chunks:
        if c.chunk_role == "parent":
            assert c.enrichment_status == "none" and c.summary_vi is None and "Tóm tắt:" not in c.embed_text
        else:
            assert c.enrichment_status == "draft" and c.summary_vi == GOOD.summary_vi
            assert "Tóm tắt: " + GOOD.summary_vi in c.embed_text and "- Đấu X41 vào cổng nào?" in c.embed_text
            assert {"đấu dây", "về home"} <= set(c.keywords) and c.content in c.embed_text
    e = result.quality.enrichment
    assert (e.leaves, e.enriched, e.auto_passed, e.passed) == (len(leaves), len(leaves), True, None)   # chưa có mẫu


def test_enrichment_never_pushes_content_out_of_embed_text(tmp_path: Path) -> None:
    """Giới hạn embed nhỏ (300): làm giàu dài → bớt câu hỏi/từ khóa/tóm tắt, `content` vẫn nằm trọn, cờ
    enrich_trimmed (chạy được cả khi chỉ có ước lượng token)."""
    doc = _doc(notes=1)
    [leaf] = [c for c in _build(doc, tmp_path, embed_max=300).chunks if c.chunk_role != "parent"]
    assert leaf.content in leaf.embed_text
    long = EnrichmentOutput(summary_vi="Tóm tắt rất dài về đấu dây và về home. " * 5,
                            faq_vi=["Câu hỏi dài về đấu dây và cách về home của trục?"] * 3,
                            keywords_vi=["đấu dây", "về home", "công tắc hành trình"])
    [enriched] = [c for c in _build(doc, tmp_path, {enrichment_key(leaf.content_hash, leaf.section_path): _record(leaf, long)}, embed_max=300).chunks
                  if c.chunk_role != "parent"]
    assert enriched.content in enriched.embed_text and "embed_truncated" not in enriched.flags
    assert "enrich_trimmed" in enriched.flags and enriched.enrichment_status == "draft"
    assert enriched.embed_text.count("- Câu hỏi dài") < 3


def test_code_checks() -> None:
    content = "Set #12010 = 1000 and connect X41 to CN3."
    assert missing_codes("Đặt #12010 cho X41 ở CN3", content) == []
    assert missing_codes("Đặt #12011 cho X42", content) == ["#12011", "X42"]
    bad = GOOD.model_copy(update={"summary_vi": "Đặt #99999.", "faq_vi": ["Một câu?"]})
    assert {"enrich_code_mismatch", "faq_count"} <= set(check_output(bad, content))
    assert check_output(GOOD, SENT) == []
    # tên model và section path được đưa vào prompt → không tính là mã bịa (thí điểm F54: "cho model F54")
    chunk = _build(_doc(notes=1), Path(".")).chunks[-1]
    assert "F54" not in chunk.content and missing_codes("Hướng dẫn cho model F54.", chunk_context(chunk)) == []


def _run_dir(tmp_path: Path, chunks: list[DraftChunk], gate: bool | None) -> Path:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / "chunks.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in chunks), encoding="utf-8")
    quality = ChunkQuality(doc_id="syn", run_dir=str(tmp_path), chunks=len(chunks), gate_passed=gate)
    (build / "chunk_quality.json").write_text(quality.model_dump_json(), encoding="utf-8")
    return tmp_path


def test_runner_requires_gate_resumes_and_skips_parents(tmp_path: Path) -> None:
    chunks = _build(_doc(), tmp_path / "b").chunks
    leaves = [c for c in chunks if c.chunk_role != "parent"]
    blocked = _run_dir(tmp_path / "no", chunks, False)
    with pytest.raises(runner.GateNotPassed):
        runner.require_gate(blocked)
    run_dir = _run_dir(tmp_path / "ok", chunks, True)
    runner.require_gate(run_dir)
    todo = runner.pending_leaves(runner.load_chunks(run_dir), run_dir)
    assert [c.chunk_key for c in todo] == [c.chunk_key for c in leaves]
    fake = FakeEnricher(fail={leaves[0].chunk_key})
    events = list(runner.run_enrichment(run_dir, todo, fake, now=lambda: datetime(2026, 11, 13)))
    stats = events[-1][3]
    assert stats.done == len(leaves) - 1 and stats.failed == [leaves[0].chunk_key]
    assert (stats.input_tokens, stats.output_tokens) == (700 * (len(leaves) - 1), 250 * (len(leaves) - 1))
    stored = load_enrichment(run_dir)
    assert set(stored) == {enrichment_key(c.content_hash, c.section_path) for c in leaves[1:]}
    assert all(r.prompt_version == "v4" and r.model == "fake-model" for r in stored.values())
    # chạy lại: chỉ còn chunk lỗi
    again = runner.pending_leaves(runner.load_chunks(run_dir), run_dir)
    assert [c.chunk_key for c in again] == [leaves[0].chunk_key]
    lines = (run_dir / "build" / ENRICHMENT_FILE).read_text(encoding="utf-8").splitlines()
    assert all(json.loads(line)["content_hash"] for line in lines)


def test_runner_rejects_unusable_output_and_flags_code_mismatch(tmp_path: Path) -> None:
    chunks = _build(_doc(notes=1), tmp_path / "b").chunks
    run_dir = _run_dir(tmp_path / "r", chunks, True)
    todo = runner.pending_leaves(chunks, run_dir)
    empty = GOOD.model_copy(update={"summary_vi": " "})
    *_, (_, record, error, stats) = runner.run_enrichment(run_dir, todo, FakeEnricher(empty))
    assert record is None and "summary_empty" in (error or "") and stats.done == 0
    odd = GOOD.model_copy(update={"summary_vi": "Đặt tham số #55555."})
    *_, (_, record, error, stats) = runner.run_enrichment(run_dir, todo, FakeEnricher(odd))
    assert record is not None and record.checks == ["enrich_code_mismatch"] and stats.flagged


def test_glossary_changes_prompt_and_version() -> None:
    from app.modules.doc_ingest.enrich.prompt import PROMPT_VERSION, prompt_version, system_prompt
    from app.modules.doc_ingest.schemas.profile import GlossaryTerm

    terms = [GlossaryTerm(en="MPG", vi="tay quay MPG"), GlossaryTerm(en="tool setter")]
    assert prompt_version([]) == PROMPT_VERSION and "Bảng thuật ngữ" not in system_prompt([])
    text = system_prompt(terms)
    assert "- MPG → tay quay MPG" in text and 'giữ nguyên tiếng Anh "tool setter"' in text
    v1 = prompt_version(terms)
    v2 = prompt_version([*terms, GlossaryTerm(en="backlash", vi="bù khe hở")])
    assert v1.startswith(PROMPT_VERSION + "+g") and v1 != v2 and v1 == prompt_version(list(terms))
    # profile qs_controller có bảng thuật ngữ (bổ sung dần)
    assert any(t.en == "MPG" for t in load_profile("qs_controller").glossary)


def test_clean_output_drops_code_keywords_and_flags_preamble() -> None:
    from app.modules.doc_ingest.enrich.checks import clean_output

    raw = GOOD.model_copy(update={"summary_vi": "Đoạn này  hướng dẫn đấu X41.",
                                  "keywords_vi": ["tham số M1920", "đấu dây", "Đấu dây ", "về home"]})
    out = clean_output(raw)
    assert clean_output(raw.model_copy(update={"keywords_vi": ["mặt sau F54"]}), ["F54"]).keywords_vi == ["mặt sau F54"]
    assert out.keywords_vi == ["đấu dây", "về home"] and out.summary_vi == "Đoạn này hướng dẫn đấu X41."
    assert "summary_preamble" in check_output(out, "Connect X41")


def test_same_content_in_two_sections_is_enriched_separately(tmp_path: Path) -> None:
    """F54: thủ tục "vào màn hình PARAMETER, đặt giá trị" lặp nguyên văn ở 13 mục tham số; làm giàu khóa theo
    (`content_hash`, `section_path`) nên mỗi mục có tóm tắt riêng, không dùng chung tóm tắt của mục đầu."""
    doc = Doc()
    for title in ("2.6.4.10 Axis acceleration JOG RAPID (G00)", "2.6.4.16 Homing Feedrate 1st"):
        doc.add("heading", title, path=(title,))
        doc.add("text", "Go to the PARAMETER screen and set the value for each axis. " * 4, path=(title,))
    chunks = _build(doc, tmp_path / "b").chunks
    leaves = [c for c in chunks if c.chunk_role != "parent"]
    run_dir = _run_dir(tmp_path / "r", chunks, True)
    todo = runner.pending_leaves(chunks, run_dir)
    assert len(todo) == len(leaves) == 2
    list(runner.run_enrichment(run_dir, todo, FakeEnricher()))
    assert len(load_enrichment(run_dir)) == 2 and runner.pending_leaves(chunks, run_dir) == []


def test_gate_2c_sample_verdicts_expire_and_approval(tmp_path: Path) -> None:
    """Cổng 2c: mẫu lấy mọi chunk có cờ kiểm + phân tầng; verdict hết hạn khi phiên bản làm giàu đổi; đạt khi 0 lỗi
    nặng và ≥ 90% ok; bản ghi cùng phiên bản đã duyệt → `approved`."""
    from app.modules.doc_ingest.build.builder import enrichment_summary
    from app.modules.doc_ingest.enrich import review as rv
    from app.modules.doc_ingest.schemas.chunk import ChunkReviewEntry, ChunkReviewFile, EnrichmentApproval

    plain = _build(_doc(), tmp_path).chunks
    leaves = [c for c in plain if c.chunk_role != "parent"]
    records = {enrichment_key(c.content_hash, c.section_path): _record(c).model_copy(update={"prompt_version": "v4"})
               for c in leaves}
    first = enrichment_key(leaves[0].content_hash, leaves[0].section_path)
    records[first] = records[first].model_copy(update={"checks": ["faq_meta"]})
    sample = rv.select_sample(leaves, records, size=2)
    assert leaves[0] in sample and len(sample) == 2                     # chunk có cờ luôn vào mẫu
    assert rv.select_sample(leaves, records, size=2, exclude=frozenset({first})) and leaves[0] not in \
        rv.select_sample(leaves, records, size=2, exclude=frozenset({first}))
    review = ChunkReviewFile(doc_id="syn", reviews=[ChunkReviewEntry(chunk_key=c.chunk_key, content_hash=c.content_hash)
                                                    for c in plain])
    assert rv.mark_sample(review, sample, records) == 2
    counts = rv.sample_counts(plain, review, records)
    assert (counts.sample, counts.pending) == (2, 2) and rv.gate_2c(True, counts) is None
    for e in review.reviews:
        if e.enrichment_verdict == "pending":
            e.enrichment_verdict = "ok"
    assert rv.gate_2c(True, rv.sample_counts(plain, review, records)) is True
    marked = next(e for e in review.reviews if e.enrichment_verdict == "ok")
    marked.enrichment_verdict, marked.enrichment_severe = "fix", True
    assert rv.gate_2c(True, rv.sample_counts(plain, review, records)) is False      # lỗi nặng → không đạt
    newer = {k: r.model_copy(update={"prompt_version": "v5"}) for k, r in records.items()}
    assert rv.sample_counts(plain, review, newer).sample == 0                      # phiên bản đổi → verdict hết hạn
    approved = _build(_doc(), tmp_path, records)
    run = approved.run
    run.approval = EnrichmentApproval(version="v4", approved_at="2026-11-13", reviewer="toma", sample=2, sample_ok=2)
    rebuilt = build_chunks(run, MANIFEST, load_profile("qs_controller"))
    assert {c.enrichment_status for c in rebuilt.chunks if c.chunk_role != "parent"} == {"approved"}
    assert enrichment_summary(rebuilt.chunks, review, run).approved_version == "v4"


def test_meta_questions_dropped_and_kept_terms_checked() -> None:
    """v3: câu hỏi về tài liệu/hình bị bỏ khi còn ≥ 2 câu (còn lại thì gắn cờ); thuật ngữ "giữ tiếng Anh" có trong
    content phải xuất hiện nguyên văn ở tóm tắt/câu hỏi/từ khóa."""
    from app.modules.doc_ingest.enrich.checks import clean_output, is_meta_question

    assert is_meta_question("Hình ảnh bộ điều khiển F54 có thể tìm ở đâu?")
    assert is_meta_question("Có hình vẽ nào về kích thước bộ điều khiển không?")
    assert not is_meta_question("Sơ đồ đấu dây MPG gồm những gì?")
    assert not is_meta_question("Đèn báo bắt đầu được kết nối ở đâu?")
    three = GOOD.model_copy(update={"faq_vi": ["Đấu X41 vào cổng nào?", "Cần đặt tham số nào?",
                                               "Hình ảnh F54 có thể tìm ở đâu?"]})
    assert clean_output(three).faq_vi == ["Đấu X41 vào cổng nào?", "Cần đặt tham số nào?"]
    two = GOOD.model_copy(update={"faq_vi": ["Đấu X41 vào cổng nào?", "Có hình vẽ nào về X41?"]})
    kept = clean_output(two)
    assert len(kept.faq_vi) == 2 and "faq_meta" in check_output(kept, "Connect X41")
    content = "Backlash compensation for X41."
    bad = GOOD.model_copy(update={"summary_vi": "Bù trục cho X41.", "faq_vi": ["Đấu X41?", "Bù trục X41?"],
                                  "keywords_vi": ["bù trục"]})
    assert "glossary_term_missing" in check_output(bad, content, ["backlash", "tool setter"])
    good = bad.model_copy(update={"summary_vi": "Bảng tham số backlash cho X41."})
    assert "glossary_term_missing" not in check_output(good, content, ["backlash", "tool setter"])


def test_only_enriched_redoes_old_version_records(tmp_path: Path) -> None:
    chunks = _build(_doc(), tmp_path / "b").chunks
    leaves = [c for c in chunks if c.chunk_role != "parent"]
    run_dir = _run_dir(tmp_path / "r", chunks, True)
    list(runner.run_enrichment(run_dir, leaves[:1], FakeEnricher(), version="v1"))
    assert runner.pending_leaves(chunks, run_dir, "v1", only_enriched=True) == []
    redo = runner.pending_leaves(chunks, run_dir, "v2", only_enriched=True)
    assert [c.chunk_key for c in redo] == [leaves[0].chunk_key]
    assert len(runner.pending_leaves(chunks, run_dir, "v2")) == len(leaves)


def test_stratified_sample_and_estimate(tmp_path: Path) -> None:
    base = _build(_doc(notes=1), tmp_path).chunks[-1]
    chunks = [base.model_copy(update={"chunk_key": f"syn:B{i:04d}", "chunk_index": i, "chunk_type": t})
              for i, t in enumerate(["procedure"] * 10 + ["figure"] * 6 + ["table"] * 3 + ["alarm"])]
    picked = runner.stratified(chunks, 8)
    types = [c.chunk_type for c in picked]
    assert len(picked) == 8 and set(types) == {"procedure", "figure", "table", "alarm"}
    assert types.count("procedure") >= types.count("figure") >= types.count("alarm")
    assert picked == sorted(picked, key=lambda c: c.chunk_index)
    inp, out = runner.estimate(picked, lambda text: len(text) // 4)
    assert inp > 0 and out == 8 * runner.EST_OUTPUT_TOKENS
    assert runner.cost_usd(1_000_000, 1_000_000, 0.15, 0.60) == pytest.approx(0.75)
