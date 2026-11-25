"""Bảng chấm tay (`evals/grading.py`) và các hàm thuần của `evals/run_generation_eval.py`. Không cần DB hay LLM."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
sys.path.insert(0, str(EVALS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, EVALS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


grading = _load("grading")
gen = _load("run_generation_eval")
rre = sys.modules["run_retrieval_eval"]


def _row(case: str, mode: str, dung: str = "", loi: str = "", run: str = "1", **extra: str) -> dict[str, str]:
    return {"case_id": case, "mode": mode, "run": run, "dung": dung, "loi": loi, "so_khang_dinh": "",
            "khang_dinh_co_nguon": "", "needs_review": "0", **extra}


def test_sheet_roundtrip_keeps_vietnamese(tmp_path: Path) -> None:
    path = tmp_path / "g.csv"
    grading.write_sheet(path, [{"case_id": "G1", "mode": "real", "answer": "Kích thước 220 × 140 mm\nxuống dòng", "run": 1}])
    rows = grading.read_sheet(path)
    assert rows[0]["answer"] == "Kích thước 220 × 140 mm\nxuống dòng" and rows[0]["dung"] == ""
    assert list(rows[0]) == grading.COLUMNS


def test_validate_sheet() -> None:
    bad = [_row("A", "real", dung="2"), _row("B", "real", dung="0", loi="bịa"), _row("C", "real", dung="1", loi="bia"),
           {**_row("D", "real", dung="0", loi="bia"), "so_khang_dinh": "2", "khang_dinh_co_nguon": "3"}]
    problems = grading.validate_sheet(bad)
    assert len(problems) == 4 and not grading.validate_sheet([_row("E", "real", dung="0,5", loi="thieu;nham_so")])


def test_summarize_and_attribute_errors() -> None:
    rows = [
        {**_row("A", "oracle", "1"), "so_khang_dinh": "4", "khang_dinh_co_nguon": "4"},
        {**_row("A", "real", "0", "thieu"), "so_khang_dinh": "4", "khang_dinh_co_nguon": "2", "needs_review": "1"},
        _row("B", "oracle", "0", "bia;nham_so"), _row("B", "real", "0", "bia"),
        _row("C", "oracle", "1"), _row("C", "real", "1"),
        _row("D", "oracle", "0", "thieu"), _row("D", "real", "1"),
        _row("E", "real", ""),
    ]
    s = grading.summarize_grading(rows)
    assert s["oracle"]["dung"] == 0.5 and s["real"]["dung"] == 0.5 and s["real"]["da_cham"] == 4 and s["real"]["n"] == 5
    assert s["oracle"]["khang_dinh_co_nguon"] == 1.0 and s["real"]["khang_dinh_co_nguon"] == 0.5
    assert s["oracle"]["loi"] == {"bia": 1, "nham_so": 1, "thieu": 1} and s["real"]["needs_review"] == 1
    assert grading.attribute_errors(rows) == {
        "loi_sinh": ["B"], "loi_ngu_canh": ["A"], "dung_ca_hai": ["C"], "chi_real_dung": ["D"]}
    assert "Nguồn gốc lỗi" in grading.render_summary(rows)


def test_sampling_is_deterministic() -> None:
    assert gen.in_sample("Q1|real|1", 1.0) is True
    assert gen.in_sample("Q1|real|1", 0.3) == gen.in_sample("Q1|real|1", 0.3)
    assert 20 < sum(gen.in_sample(f"Q{i}|real|1", 0.3) for i in range(100)) < 45


def _case(**kw):
    base = dict(id="G1", question="Kích thước F54?", domain="technical_docs", models=("F54",), tags=(),
                expected=frozenset({("h1", ("A",))}), acceptable=frozenset(), expected_keys=())
    return rre.Case(**{**base, **kw})


def test_context_model_and_expected_ids() -> None:
    assert gen.context_model(_case(question="Kích thước?")) == "F54"
    assert gen.context_model(_case(question="Kích thước F54?")) is None
    assert gen.context_model(_case(models=())) is None
    index = {5: rre.ChunkInfo("d:B5", "h1", ("A",), "child", "t", "S"), 9: rre.ChunkInfo("d:B9", "h2", ("B",), "child", "t", "S")}
    assert gen.expected_ids(_case(), index) == [5]
    assert gen.expected_ids(_case(expected=frozenset({("zz", ("A",))})), index) == []


def test_oracle_retriever_and_hits_expand_parent() -> None:
    from app.modules.chatbot.schemas.system import ChunkRecord, RetrievalRequest, RetrievalQuery

    def rec(i: int, parent: int | None, content: str) -> ChunkRecord:
        return ChunkRecord(id=i, parent_id=parent, doc_id="d", section_title="T", section_path=["T"], content=content)

    class Repo:
        async def fetch_by_ids(self, ids, audiences):
            assert list(audiences) == ["public"]
            table = {1: rec(1, 10, "con"), 2: rec(2, 10, "con 2"), 10: rec(10, None, "CHA")}
            return [table[i] for i in ids if i in table]

    hits = asyncio.run(gen.oracle_hits(Repo(), [1, 2]))
    assert len(hits) == 1 and hits[0].content == "CHA" and hits[0].matched_chunk_ids == ["1", "2"]
    assert asyncio.run(gen.oracle_hits(Repo(), [])) == []
    request = RetrievalRequest(task_id="t", domain="technical_docs", queries=[RetrievalQuery(sub_query_id="q1", query="x", answer_mode="full")])
    result = asyncio.run(gen.OracleRetriever(hits).search([request]))
    assert result.sub_query_id == "q1" and len(result.hits) == 1 and not result.metadata
    empty = asyncio.run(gen.OracleRetriever([]).search([request]))
    assert empty.metadata == {"no_hits": "true"}


def test_sheet_row_marks_flagged_rows() -> None:
    from gen_checks import auto_flags

    sources = {"S1": "Kích thước 220 x 140 x 30 mm"}
    flags = auto_flags("Kích thước 220 x 150 x 30 mm [S1].", "kích thước?", sources, ["220 x 140 x 30"]).as_dict()
    record = {"route": "retrieve", "answer": "Kích thước 220 x 150 x 30 mm [S1].", "flags": flags,
              "sources": {"S1": {"content": sources["S1"], "section": "QS F54", "pages": "8", "doc": "cat"}}}
    row = gen.sheet_row("r1", _case(), "real", 1, record, sample_rate=0.0)
    assert row["needs_review"] == 1 and row["sample"] == 1 and "thiếu fact" in row["auto_flags"]
    assert "S1: cat § QS F54 (tr. 8)" in row["sources"]
    clean = auto_flags("Kích thước 220 x 140 x 30 mm [S1].", "kích thước?", sources, ["220 x 140 x 30"]).as_dict()
    row2 = gen.sheet_row("r1", _case(), "real", 1, {**record, "flags": clean}, sample_rate=0.0)
    assert row2["needs_review"] == 0 and row2["sample"] == 0 and row2["auto_flags"] == ""


def test_render_report_counts_flags() -> None:
    from gen_checks import auto_flags

    flags = auto_flags("Không có thông tin.", "q", {}, ["220"]).as_dict()
    rec = {"case_id": "G1", "mode": "real", "run": 1, "route": "retrieve", "error": None, "answer": "", "sources": {},
           "context_chunks": 5, "context_gold": 2, "flags": flags}
    meta = {"at": "t", "split": "dev", "modes": ["real"], "repeat": 1, "cases": "c.yaml", "model": "m",
            "prompt_version": "production", "routing": "r0"}
    text = gen.render_report(meta, [_case()], [rec])
    assert "| real | 1 | 0 | 0.0 | 1 | 1 |" in text and "G1 [real#1]" in text


def test_modes_validated() -> None:
    with pytest.raises(SystemExit):
        gen.main(["--modes", "x"])
