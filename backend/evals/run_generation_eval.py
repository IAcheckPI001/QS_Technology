"""Đánh giá bước sinh câu trả lời của luồng web (kế hoạch §9, GD0). Chỉ đọc database; không dùng LLM-judge.

Hai chế độ cho mỗi câu của bộ vàng:
- `oracle`: pipeline thật (phân tích LLM) nhưng bước tra cứu bị thay bằng **chunk đúng** của câu (`expected`; chunk cha nếu
  có, như production). Câu `expect_abstain` / không có chunk đúng thì ngữ cảnh rỗng. Sai ở đây là lỗi của bước sinh.
- `real`: pipeline thật với retriever v2 như production (`approved_only=False` vì chunk còn `draft`).
Ghép cặp hai chế độ cho biết lỗi do sinh hay do tra cứu/ngữ cảnh (`grading.attribute_errors`).

Mỗi câu trả lời được kiểm tự động (`gen_checks.py`: fact vàng, số/mã không có trong ngữ cảnh, `[S#]` hợp lệ, "không biết")
và ghi vào `grading.csv` để người chấm điền; xem `grading.py`.

Chạy từ `backend/` (cần OPENAI_API_KEY, DATABASE_URL):
    .\\venv\\Scripts\\python.exe evals\\run_generation_eval.py --cases evals\\retrieval_cases\\gold_v1.yaml --split dev --label baseline
Kết quả: `data/generation_eval/<thời điểm>[-nhãn]/` gồm `results.json`, `grading.csv`, `report.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS))

import grading  # noqa: E402
import run_retrieval_eval as rre  # noqa: E402
from gen_checks import auto_flags  # noqa: E402

ROOT = rre.ROOT
OUTPUT = ROOT.parent / "data" / "generation_eval"
MODES = ("oracle", "real")


class OracleRetriever:
    """Retriever giả: trả đúng các chunk đã chọn (chunk đúng của câu), không tìm gì."""

    def __init__(self, hits: list[Any]) -> None:
        self.hits = hits

    async def search(self, targets: list[Any], fallback_targets: list[Any] | None = None) -> Any:
        from app.modules.chatbot.schemas.system import RetrievalSubQueryResult

        return RetrievalSubQueryResult(
            sub_query_id=targets[0].queries[0].sub_query_id, hits=list(self.hits), traces=[],
            metadata={} if self.hits else {"no_hits": "true"})


async def oracle_hits(repository: Any, ids: list[int]) -> list[Any]:
    """ChunkHit của các chunk đúng, mở rộng sang chunk cha như `Retriever._expand_parents`."""
    from app.modules.chatbot.schemas.system import ChunkHit

    if not ids:
        return []
    records = {r.id: r for r in await repository.fetch_by_ids(ids, ["public"])}
    parent_ids = [r.parent_id for r in records.values() if r.parent_id is not None and r.parent_id not in records]
    parents = {r.id: r for r in await repository.fetch_by_ids(parent_ids, ["public"])} if parent_ids else {}
    groups: dict[int, list[int]] = {}
    for chunk_id in ids:
        record = records.get(chunk_id)
        if record is None:
            continue
        context_id = record.parent_id if record.parent_id in parents else record.id
        groups.setdefault(context_id, []).append(record.id)
    hits = []
    for context_id, children in groups.items():
        record = parents.get(context_id) or records[context_id]
        hits.append(ChunkHit(
            chunk_id=str(record.id), matched_chunk_ids=[str(c) for c in children], doc_id=record.doc_id,
            section_title=record.section_title, section_path=record.section_path, page_start=record.page_start,
            page_end=record.page_end, content=record.content, assets=record.assets, domain=record.domain,
            scopes=record.scopes, control_interface=record.control_interface, spec_attributes=record.spec_attributes,
            score=1.0, similarity=None))
    return hits


def expected_ids(case: rre.Case, index: dict[int, rre.ChunkInfo]) -> list[int]:
    """Id (đang hoạt động) của các chunk `expected` của câu (thứ tự ổn định giữa các lần chạy)."""
    by_key: dict[rre.GoldKey, int] = {}
    for chunk_id, info in sorted(index.items()):
        by_key.setdefault(info.gold_key, chunk_id)
    return [by_key[key] for key in sorted(case.expected, key=str) if key in by_key]


def context_model(case: rre.Case) -> str | None:
    """Câu cần model mà câu hỏi không nêu: giả lập người dùng đã nêu ở lượt trước (như `web2` của eval tra cứu), để đo
    bước sinh chứ không đo việc hỏi lại."""
    return case.models[0] if case.models and not case.model_in_question else None


def in_sample(row_key: str, rate: float) -> bool:
    """Chọn mẫu cố định theo khóa (cùng bộ câu + lần chạy luôn cho cùng mẫu)."""
    if rate >= 1.0:
        return True
    return int(hashlib.sha256(row_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < rate


def sources_text(sources: dict[str, dict[str, Any]]) -> str:
    return "\n".join(f"{sid}: {s['doc']} § {s['section']} (tr. {s['pages']}) — {s['content'][:140].strip()!r}"
                     for sid, s in sources.items())


def sheet_row(run_id: str, case: rre.Case, mode: str, run: int, record: dict[str, Any], sample_rate: float) -> dict[str, Any]:
    flags = record["flags"]
    key = f"{case.id}|{mode}|{run}"
    return {
        "run_id": run_id, "case_id": case.id, "split": case.split, "source": case.source, "mode": mode, "run": run,
        "question": case.question, "route": record["route"], "answer": record["answer"],
        "sources": sources_text(record["sources"]), "facts_missing": "; ".join(flags["facts_missing"]),
        "auto_flags": "; ".join(name for name, bad in (
            ("thiếu fact", flags["facts_missing"]), ("[S#] không hợp lệ", flags["invalid_citations"]),
            ("không trích nguồn", flags["no_citation"]), ("số/mã không có trong ngữ cảnh", flags["numbers_not_in_context"]),
            ("câu trích sai chỗ", flags["unsupported_sentences"]), ("abstain lệch", flags["abstain_mismatch"])) if bad),
        "needs_review": int(flags["needs_review"]),
        "sample": int(flags["needs_review"] or in_sample(key, sample_rate)),
    }


async def collect_answer(provider: Any, messages: list[dict[str, str]]) -> str:
    return "".join([chunk async for chunk in provider.stream_chat(messages)])


async def run_case(case: rre.Case, mode: str, run: int, env: dict[str, Any]) -> dict[str, Any]:
    from app.modules.chatbot.orchestration import collect_results
    from app.modules.chatbot.stages.answer_composer import serialize_turn
    from app.modules.chatbot.stages.clarification_resume_stage import ClarificationResumeStage
    from app.modules.chatbot.stages.execution_stage import ExecutionStage
    from app.modules.chatbot.stages.retrieval_pipeline import RetrievalPipeline

    ctx_model = context_model(case)
    if mode == "oracle":
        retriever: Any = OracleRetriever(await oracle_hits(env["repository"], expected_ids(case, env["index"])))
    else:
        retriever = env["retriever"]
    pipeline = RetrievalPipeline(ClarificationResumeStage(env["routing_version"]), env["analysis_stage"],
                                 ExecutionStage(retriever=retriever))
    state = rre._website_state(case.question, ctx_model)
    record: dict[str, Any] = {"case_id": case.id, "mode": mode, "run": run, "context_model": ctx_model, "error": None,
                              "answer": "", "route": "", "sources": {}, "context_chunks": 0, "context_gold": 0}
    try:
        await pipeline.run(state)
        record["route"] = ",".join(sq.route.value for sq in state.analysis.sub_queries) if state.analysis else ""
        messages = env["composer"].build_messages(state)
        record["answer"] = await collect_answer(env["answer_provider"], messages)
        _, groups = serialize_turn(state, env["composer"]._source_char_limit)
        hits = [h for task, res in zip(state.plan.tasks, collect_results(state.plan)) if res.retrieval
                for sub in res.retrieval.results for h in sub.hits]
        meta = {h.source_id: h for h in hits}
        record["sources"] = {
            s["source_id"]: {"content": s["content"], "section": s["section"], "pages": s["pages"],
                             "doc": meta[s["source_id"]].doc_id if s["source_id"] in meta else ""}
            for g in groups for s in g["sources"]}
        index = env["index"]
        children = {int(c) for h in hits for c in h.matched_chunk_ids}
        record["context_chunks"] = len(children)
        record["context_gold"] = sum(1 for c in children if c in index and index[c].gold_key in case.gold)
    except Exception as exc:                      # noqa: BLE001 - lỗi từng câu không dừng cả lượt đo
        from app.modules.chatbot.analysis.analyzer import AnalysisError

        if isinstance(exc, AnalysisError) and exc.code == "analysis_provider_error":
            raise SystemExit(f"bước phân tích lỗi provider ở câu {case.id}: {exc.__cause__!r}") from exc
        record["error"] = f"{type(exc).__name__}: {getattr(exc, 'code', '') or exc}"[:200]
    flags = auto_flags(record["answer"], case.question, {s: v["content"] for s, v in record["sources"].items()},
                       list(case.facts), case.expect_abstain, known=list(case.models))
    record["flags"] = flags.as_dict()
    return record


def render_report(meta: dict[str, Any], cases: list[rre.Case], records: list[dict[str, Any]]) -> str:
    lines = ["# Đánh giá bước sinh câu trả lời (luồng web)", "",
             f"- Thời điểm: {meta['at']} · {len(cases)} câu · phần: {meta['split']} · chế độ: {', '.join(meta['modes'])}"
             f" · số lần: {meta['repeat']} · file: `{meta['cases']}`",
             f"- Model phân tích và sinh: `{meta['model']}` (như production: một provider cho cả hai); "
             f"prompt `{meta['prompt_version']}`, luật định tuyến `{meta['routing']}`",
             "- Không có LLM-judge: các số dưới đây chỉ là **kiểm tự động**; độ đúng do người chấm trong `grading.csv`.", "",
             "| Chế độ | n | lỗi chạy | fact recall | cần xem | thiếu fact | [S#] sai | không trích | số/mã lạ | câu trích sai chỗ | abstain lệch | chunk/lượt | chunk đúng/lượt |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for mode in meta["modes"]:
        rs = [r for r in records if r["mode"] == mode]
        if not rs:
            continue
        f = [r["flags"] for r in rs]
        recalls = [x["fact_recall"] for x in f if x["fact_recall"] is not None]
        lines.append(
            f"| {mode} | {len(rs)} | {sum(1 for r in rs if r['error'])} | "
            f"{round(sum(recalls) / len(recalls), 3) if recalls else '—'} | {sum(x['needs_review'] for x in f)} | "
            f"{sum(1 for x in f if x['facts_missing'])} | {sum(1 for x in f if x['invalid_citations'])} | "
            f"{sum(1 for x in f if x['no_citation'])} | {sum(1 for x in f if x['numbers_not_in_context'])} | "
            f"{sum(1 for x in f if x['unsupported_sentences'])} | {sum(1 for x in f if x['abstain_mismatch'])} | "
            f"{round(sum(r['context_chunks'] for r in rs) / len(rs), 2)} | "
            f"{round(sum(r['context_gold'] for r in rs) / len(rs), 2)} |")
    flagged = [r for r in records if r["flags"]["needs_review"] or r["error"]]
    lines += ["", f"## Câu có cờ ({len(flagged)})", ""]
    for r in flagged:
        fl = r["flags"]
        lines.append(f"- {r['case_id']} [{r['mode']}#{r['run']}] route={r['route'] or '—'}"
                     + (f" LỖI={r['error']}" if r["error"] else "")
                     + (f" · thiếu fact: {fl['facts_missing']}" if fl["facts_missing"] else "")
                     + (f" · số/mã lạ: {fl['numbers_not_in_context']}" if fl["numbers_not_in_context"] else "")
                     + (" · không trích nguồn" if fl["no_citation"] else "")
                     + (f" · [S#] sai: {fl['invalid_citations']}" if fl["invalid_citations"] else "")
                     + (" · abstain lệch" if fl["abstain_mismatch"] else ""))
    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> Path:
    from app.core.config import settings
    from app.db.engine import engine
    from app.modules.chatbot.extraction.registry import ROUTING_VERSION, routing_rules
    from app.modules.chatbot.prompts.answer import SYSTEM_PROMPT  # noqa: F401  (đảm bảo prompt production nạp được)
    from app.modules.chatbot.providers.openai import OpenAIProvider
    from app.modules.chatbot.repositories.doc_chunk_v2_repository import DocChunkV2Repository, MatchV2Options
    from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
    from app.modules.chatbot.stages.analysis_stage import AnalysisStage
    from app.modules.chatbot.stages.answer_composer import AnswerComposer

    if not settings.openai_api_key:
        raise SystemExit("thiếu OPENAI_API_KEY")
    cases = rre.load_cases(args.cases, args.ids, args.split)
    if not cases:
        raise SystemExit("không có câu hỏi nào khớp (kiểm --split và danh sách id)")
    model = args.model or settings.openai_model
    provider = OpenAIProvider(api_key=settings.openai_api_key, model=model, embedding_model=settings.embedding_model)
    embedder = rre.CachedEmbedder(provider)
    try:
        index, models = await rre.load_index()
        rre._patch_coverage(models)
        repository = DocChunkV2Repository(MatchV2Options(approved_only=False))
        analysis_stage = AnalysisStage(provider, timeout_s=args.analysis_timeout_s, prompt_version=args.prompt_version,
                                       intent_desc_version=args.intent_desc_version, routing_version=args.routing_version)
        env = {"index": index, "repository": repository, "analysis_stage": analysis_stage,
               "routing_version": args.routing_version, "answer_provider": provider,
               "composer": AnswerComposer(provider),
               "retriever": Retriever(embedder, repository, RetrieverConfig.from_settings(settings))}
        records: list[dict[str, Any]] = []
        for case in cases:
            for mode in args.modes:
                for run in range(1, args.repeat + 1):
                    rec = await run_case(case, mode, run, env)
                    records.append(rec)
                    fl = rec["flags"]
                    print(f"  {case.id} {mode}#{run}: route={rec['route'] or '—'} chunks={rec['context_chunks']}"
                          f"(đúng {rec['context_gold']}) fact={fl['fact_recall']} "
                          f"{'CẦN XEM' if fl['needs_review'] else 'ok'}" + (f" LỖI={rec['error']}" if rec["error"] else ""),
                          flush=True)
    finally:
        await provider.close()
        await engine.dispose()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.label}" if args.label else "")
    out = OUTPUT / run_id
    out.mkdir(parents=True, exist_ok=True)
    meta = {"at": datetime.now().strftime("%Y-%m-%d %H:%M"), "cases": str(args.cases.relative_to(ROOT)),
            "split": args.split, "modes": list(args.modes), "repeat": args.repeat, "model": model,
            "prompt_version": args.prompt_version or "production", "label": args.label,
            "routing": args.routing_version or ROUTING_VERSION, "routing_rules": sorted(routing_rules(args.routing_version)),
            "sample_rate": args.sample_rate, "approved_only": False, "audience": "public"}
    by_id = {c.id: c for c in cases}
    (out / "results.json").write_text(json.dumps({"meta": meta, "records": records}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    grading.write_sheet(out / "grading.csv", [sheet_row(run_id, by_id[r["case_id"]], r["mode"], r["run"], r,
                                                         args.sample_rate) for r in records])
    (out / "report.md").write_text(render_report(meta, cases, records), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá bước sinh câu trả lời của luồng web (oracle/real)")
    parser.add_argument("--cases", type=Path, default=EVALS / "retrieval_cases" / "gold_v1.yaml")
    parser.add_argument("--split", choices=(*rre.SPLITS, "all"), default="dev")
    parser.add_argument("--modes", default="oracle,real", help="oracle, real hoặc cả hai (cách nhau bằng dấu phẩy)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--model", default=None, help="model phân tích + sinh (mặc định OPENAI_MODEL như production)")
    parser.add_argument("--label", default="")
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--intent-desc-version", default=None)
    parser.add_argument("--routing-version", default=None)
    parser.add_argument("--analysis-timeout-s", type=float, default=120.0)
    parser.add_argument("--sample-rate", type=float, default=1.0,
                        help="tỉ lệ dòng không có cờ được đánh dấu `sample` để người chấm (mặc định 1 = tất cả)")
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args(argv)
    args.modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    if not args.modes or any(m not in MODES for m in args.modes):
        parser.error(f"--modes phải thuộc {MODES}")
    args.cases = args.cases.resolve()
    if sys.platform == "win32":   # psycopg async không chạy trên ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    out = asyncio.run(main_async(args))
    print(f"Báo cáo: {out / 'report.md'}\nBảng chấm: {out / 'grading.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
