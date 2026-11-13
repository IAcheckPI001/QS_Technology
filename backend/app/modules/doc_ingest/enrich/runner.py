"""Chạy Bước 3 trên một thư mục chạy: chọn chunk lá chưa làm giàu, ước tính chi phí, gọi `Enricher`, ghi
`build/enrichment.jsonl` (append-only, mỗi kết quả ghi ngay → dừng giữa chừng chạy tiếp được).

Chỉ chạy khi `build/chunk_quality.json` đạt cổng 2b (kể cả "tạm"). Chunk cha không làm giàu (D-008).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.modules.doc_ingest.build.loader import ENRICHMENT_FILE, enrichment_key, load_enrichment
from app.modules.doc_ingest.enrich.checks import BLOCKING, check_output, chunk_context, clean_output
from app.modules.doc_ingest.enrich.client import Enricher
from app.modules.doc_ingest.enrich.prompt import PROMPT_VERSION, SYSTEM_PROMPT, user_message
from app.modules.doc_ingest.schemas.chunk import ChunkQuality, DraftChunk, EnrichmentRecord

EST_OUTPUT_TOKENS = 250   # tóm tắt + 2–3 câu hỏi + từ khóa, dạng JSON (ước tính trước khi chạy)


class GateNotPassed(RuntimeError):
    pass


def load_chunks(run_dir: Path) -> list[DraftChunk]:
    path = run_dir / "build" / "chunks.jsonl"
    return [DraftChunk.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def require_gate(run_dir: Path) -> ChunkQuality:
    path = run_dir / "build" / "chunk_quality.json"
    if not path.is_file():
        raise GateNotPassed(f"chưa có {path}: chạy build trước")
    quality = ChunkQuality.model_validate_json(path.read_text(encoding="utf-8"))
    if quality.gate_passed is not True:
        raise GateNotPassed("cổng 2b chưa đạt (contract C2 §10: chưa đạt cổng thì không làm giàu LLM)")
    return quality


def pending_leaves(chunks: Sequence[DraftChunk], run_dir: Path, version: str = PROMPT_VERSION,
                   only_enriched: bool = False) -> list[DraftChunk]:
    """Chunk lá chưa có bản ghi cùng khóa (`content_hash`, `section_path`) và phiên bản `version`; mỗi khóa một lần.
    `only_enriched`: chỉ chunk đã có bản ghi phiên bản khác (làm lại để so sánh prompt/thuật ngữ mới)."""
    records = load_enrichment(run_dir)
    done = {k for k, r in records.items() if r.prompt_version == version}
    out, seen = [], set()
    for c in chunks:
        key = enrichment_key(c.content_hash, c.section_path)
        if c.chunk_role == "parent" or key in done or key in seen:
            continue
        if only_enriched and key not in records:
            continue
        seen.add(key)
        out.append(c)
    return out


def stratified(chunks: Sequence[DraftChunk], n: int) -> list[DraftChunk]:
    """Mẫu thí điểm: chia `n` theo tỉ lệ loại chunk (mỗi loại ≥ 1 khi đủ chỗ), trong mỗi loại lấy cách đều theo thứ
    tự đọc. Deterministic."""
    groups: dict[str, list[DraftChunk]] = {}
    for c in chunks:
        groups.setdefault(c.chunk_type, []).append(c)
    order = sorted(groups, key=lambda t: (-len(groups[t]), t))
    quota = {t: 0 for t in order}
    for t in order[:n]:
        quota[t] = 1
    left = n - sum(quota.values())
    total = len(chunks)
    while left > 0:
        t = max(order, key=lambda t: (len(groups[t]) / total - quota[t] / n if quota[t] < len(groups[t]) else -1))
        if quota[t] >= len(groups[t]):
            break
        quota[t] += 1
        left -= 1
    picked: list[DraftChunk] = []
    for t in order:
        items, k = groups[t], quota[t]
        picked += [items[(i * len(items)) // k] for i in range(k)] if k else []
    return sorted(picked, key=lambda c: c.chunk_index)


def estimate(chunks: Sequence[DraftChunk], count: Callable[[str], int],
             system_text: str = SYSTEM_PROMPT) -> tuple[int, int]:
    """(token vào, token ra) ước tính cho các chunk."""
    system = count(system_text)
    return sum(system + count(user_message(c)) + 10 for c in chunks), EST_OUTPUT_TOKENS * len(chunks)


@dataclass
class RunStats:
    done: int = 0
    failed: list[str] = field(default_factory=list)
    flagged: dict[str, list[str]] = field(default_factory=dict)    # chunk_key -> checks (không chặn ghi)
    input_tokens: int = 0
    output_tokens: int = 0


def run_enrichment(run_dir: Path, chunks: Sequence[DraftChunk], enricher: Enricher,
                   now: Callable[[], datetime] = datetime.now,
                   version: str = PROMPT_VERSION,
                   keep_terms: Sequence[str] = ()) -> Iterator[tuple[DraftChunk, EnrichmentRecord | None,
                                                                     str | None, RunStats]]:
    """Làm giàu từng chunk, ghi ngay vào `enrichment.jsonl`. Yield (chunk, bản ghi hoặc None, lỗi, thống kê)."""
    path = run_dir / "build" / ENRICHMENT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = RunStats()
    for chunk in chunks:
        try:
            result = enricher.enrich(chunk)
        except Exception as exc:   # lỗi API/JSON: bỏ qua chunk này, chạy lại sau
            stats.failed.append(chunk.chunk_key)
            yield chunk, None, f"{type(exc).__name__}: {exc}", stats
            continue
        stats.input_tokens += result.input_tokens
        stats.output_tokens += result.output_tokens
        output = clean_output(result.output, chunk.product_models)
        problems = check_output(output, chunk_context(chunk), list(keep_terms))
        if BLOCKING & set(problems):
            stats.failed.append(chunk.chunk_key)
            yield chunk, None, f"đầu ra không dùng được: {problems}", stats
            continue
        record = EnrichmentRecord(
            **output.model_dump(), content_hash=chunk.content_hash, section_path=list(chunk.section_path),
            chunk_key=chunk.chunk_key,
            model=enricher.model, prompt_version=version, created_at=now().isoformat(timespec="seconds"),
            input_tokens=result.input_tokens, output_tokens=result.output_tokens, checks=problems)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
        stats.done += 1
        if problems:
            stats.flagged[chunk.chunk_key] = problems
        yield chunk, record, None, stats


def cost_usd(input_tokens: int, output_tokens: int, input_price: float, output_price: float) -> float:
    """Giá theo USD mỗi 1M token."""
    return input_tokens / 1e6 * input_price + output_tokens / 1e6 * output_price
