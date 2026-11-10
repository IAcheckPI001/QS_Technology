"""Gán trường cho chunk (contract C2 §4, §7, §8, §9): lọc, trích dẫn, assets, từ khóa, `embed_text`, review."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Sequence

from app.modules.doc_ingest.build.chunker import VISUAL, ChunkPlan, Unit
from app.modules.doc_ingest.build.loader import RunInput
from app.modules.doc_ingest.schemas.chunk import ChunkAsset, DraftChunk, FigureLabel
from app.modules.doc_ingest.schemas.manifest import SCOPE_ORDER, DocManifest, Scope
from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate, NormalizedElement
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.technical_refs.params import ParamRef

TokenCounter = Callable[[str], int]
_SECTION_NO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s")
_TOC_LINE = re.compile(r"(\.{4,}|…{2,}|�{3,})\s*\.?\s*\d*\s*$")
_TOKEN = re.compile(r"#?[A-Za-z0-9][A-Za-z0-9_\-+]*")
_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")


def token_counter() -> tuple[TokenCounter | None, str]:
    """tiktoken `cl100k_base` nếu venv có và đã có file mã hóa; không có → (None, "unavailable")."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:   # venv ingest không có tiktoken, hoặc không tải được file mã hóa
        return None, "unavailable"
    return (lambda text: len(encoding.encode(text))), "tiktoken"


def _estimate(text: str) -> int:
    return (len(text) + 3) // 4


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def section_id(path: Sequence[str]) -> str | None:
    for heading in reversed(path):
        match = _SECTION_NO.match(heading)
        if match:
            return match.group(1)
    return None


def _term_re(term: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])", re.IGNORECASE)


_PAGE_ID = re.compile(r":p(\d+)$")

ReviewEntries = dict[str, list[tuple[str, str]]]


def review_index(run: RunInput) -> tuple[ReviewEntries, dict[int, list[tuple[str, str]]]]:
    """(code, blocks) theo element (cả `element_id` lẫn `target`) và theo trang (review cấp trang `{doc}:p005`)."""
    by_element: ReviewEntries = {}
    by_page: dict[int, list[tuple[str, str]]] = {}
    for item in run.review:
        entry = (item.code, item.blocks)
        for ref in {item.element_id, item.target or item.element_id}:
            page = _PAGE_ID.search(ref)
            if page:
                by_page.setdefault(int(page.group(1)), []).append(entry)
            else:
                by_element.setdefault(ref, []).append(entry)
    return by_element, by_page


def _printed_int(value: str | None) -> int | None:
    return int(value) if value is not None and value.isdigit() else None


class Assembler:
    def __init__(self, run: RunInput, manifest: DocManifest, profile: Profile) -> None:
        self.run = run
        self.manifest = manifest
        self.profile = profile
        self.cfg = profile.chunking
        self.counter, self.token_method = token_counter()
        self.by_id = {e.element_id: e for e in run.elements}
        self.figure_text: dict[str, list[NormalizedElement]] = {}
        for e in run.elements:
            if e.normalized_type == "figure_text" and e.parent_element_id:
                self.figure_text.setdefault(e.parent_element_id, []).append(e)
        self.interface_terms = self._terms(profile.vocabulary.control_interface, self.cfg.control_interface_terms)
        self.spec_terms = self._terms(profile.vocabulary.spec_attributes, self.cfg.spec_attribute_terms)
        self.param_patterns = [re.compile(re.escape(p) + rx + r"$") for p, rx in profile.param_text_patterns.items()]
        self.review_by_element, self.review_by_page = review_index(run)
        self.review_by_table: dict[str, list[tuple[str, str, str | None]]] = {}
        for item in run.review:
            for tid in run.tables:
                if item.target and (item.target == tid or item.target.startswith(tid + ":")):
                    row = item.target[len(tid) + 1:].split(":")[0] if item.target != tid else None
                    self.review_by_table.setdefault(tid, []).append((item.code, item.blocks, row or None))

    @staticmethod
    def _terms(vocabulary: dict[str, str], extra: dict[str, list[str]]) -> dict[str, list[re.Pattern[str]]]:
        out: dict[str, list[re.Pattern[str]]] = {}
        for key, label in vocabulary.items():
            terms = [t.strip() for t in label.split("/") if t.strip()] + extra.get(key, [])
            out[key] = [_term_re(t) for t in _dedupe(terms)]
        return out

    # trường theo đơn vị ---------------------------------------------------------------------------
    def _scopes(self, unit: Unit) -> list[Scope]:
        joined = " › ".join(unit.section_path)
        scopes: set[Scope] = set(self.manifest.default_scopes)
        for rule in self.manifest.scope_rules:
            if re.search(rule.match, joined):
                scopes = set(rule.scopes)
                break
        if unit.chunk_type == "parameter":
            scopes.add("configuration")
        if unit.chunk_type == "alarm":
            scopes.add("maintenance")
        return [s for s in SCOPE_ORDER if s in scopes]

    def _matches(self, terms: dict[str, list[re.Pattern[str]]], text: str) -> list[str]:
        return [key for key, patterns in terms.items() if any(p.search(text) for p in patterns)]

    def _title_text(self, unit: Unit) -> str:
        captions = [e.text or "" for e in unit.elements if e.normalized_type == "caption"]
        return " | ".join([unit.section_path[-1] if unit.section_path else "", unit.label or "", *captions])

    def _param_refs(self, unit: Unit) -> list[ParamRef]:
        refs: dict[str, ParamRef] = {}
        for e in unit.elements:
            for r in e.param_refs:
                refs.setdefault(r.label, ParamRef(prefix=r.prefix, kind=r.kind, codes=r.codes,
                                                  range_start=r.range_start, range_end=r.range_end, label=r.label))
        if unit.table is not None:
            rows = set(unit.row_ids)
            for row in unit.table.rows:
                if row.row_id in rows and row.param_ref is not None:
                    refs.setdefault(row.param_ref.label, row.param_ref)
        return list(refs.values())

    def _applicability(self, unit: Unit) -> list[ApplicabilityCandidate]:
        out = [c for e in unit.elements for c in e.applicability_candidates]
        if unit.table is not None:
            rows = set(unit.row_ids)
            out += [c for row in unit.table.rows if row.row_id in rows for c in row.applicability_candidates]
        return out

    def _io_codes(self, content: str) -> list[str]:
        codes = []
        for token in _TOKEN.findall(content):
            if any(re.search(p, token) for p in self.profile.code_patterns) and not any(
                    p.match(token) for p in self.param_patterns) and not any(
                    token.startswith(pfx) for pfx in self.profile.param_prefixes if not pfx.isalpha()):
                codes.append(token)
        return _dedupe(codes)

    def _keep_label(self, text: str) -> list[str]:
        t = " ".join(text.split())
        if len(t) < 2 or not any(ch.isalnum() for ch in t):
            return []
        patterns = list(self.profile.code_patterns) + list(self.cfg.figure_label_patterns)
        if any(re.search(p, t) for p in patterns):
            return [t]
        return [tok for tok in re.split(r"[\s,;]+", t) if len(tok) >= 2 and any(re.search(p, tok) for p in patterns)]

    def _figure_labels(self, unit: Unit) -> list[FigureLabel]:
        labels: list[FigureLabel] = []
        for visual in (e for e in unit.elements if e.normalized_type in VISUAL):
            source = "ocr" if visual.pdf_page_index in self.run.ocr_pages else "text_layer"
            for ft in self.figure_text.get(visual.element_id, []):
                labels += [FigureLabel(text=t, element_id=visual.element_id, bbox=ft.bbox, source=source)
                           for t in self._keep_label(ft.text or "")]
            for raw in self.run.figure_ocr.get(visual.element_id, []):
                labels += [FigureLabel(text=t, element_id=visual.element_id, source="crop_ocr")
                           for t in self._keep_label(raw)]
        seen: set[tuple[str, str]] = set()
        out = []
        for label in labels:
            key = (label.element_id, label.text.casefold())
            if key not in seen:
                seen.add(key)
                out.append(label)
        return out

    def _assets(self, unit: Unit) -> tuple[list[ChunkAsset], bool]:
        assets, missing = [], False
        for e in unit.elements:
            if e.normalized_type not in VISUAL:
                continue
            local = e.image.original_path if e.image is not None else None
            missing = missing or local is None or not (self.run.run_dir / local).is_file()
            assets.append(ChunkAsset(bucket=self.manifest.storage_bucket,
                                     path=f"{self.manifest.doc_id}/{e.element_id.replace(':', '_')}.png",
                                     page=e.pdf_page_index, printed_page=_printed_int(e.printed_page.value),
                                     element_id=e.element_id, local_path=local))
        return assets, missing

    def _reviews(self, unit: Unit) -> tuple[list[str], list[str]]:
        blockers, notes = [], []
        entries = [x for e in unit.elements for x in self.review_by_element.get(e.element_id, [])]
        entries += [x for p in self._pages(unit) for x in self.review_by_page.get(p, [])]
        for code, blocks in entries:
            (blockers if blocks == "chunk" else notes).append(code)
        if unit.table is not None:
            rows = set(unit.row_ids)
            for code, blocks, row in self.review_by_table.get(unit.table.logical_table_id, []):
                if row is None or not row.startswith("r") or row in rows:
                    (blockers if blocks == "chunk" else notes).append(code)
        return sorted(set(blockers)), sorted(set(notes))

    def _pages(self, unit: Unit) -> list[int]:
        return sorted({e.pdf_page_index for e in unit.elements} | unit.table_pages)

    def _printed(self, unit: Unit, pages: list[int]) -> tuple[str | None, str | None]:
        by_page = {e.pdf_page_index: e.printed_page.value for e in unit.elements if e.printed_page.value}
        by_page.update({p: v for p, v in self.run.report.printed_pages.items() if p in pages and v})
        return by_page.get(pages[0]), by_page.get(pages[-1])

    def _extraction(self, pages: Sequence[int]) -> str:
        if self.run.report.s0 is None:
            return "unknown"
        ocr = [p in self.run.ocr_pages for p in pages]
        return "ocr" if all(ocr) else "mixed" if any(ocr) else "text_layer"

    def _keywords(self, refs: Sequence[ParamRef], io: Sequence[str], sid: str | None, labels: Sequence[FigureLabel],
                  path: Sequence[str], label: str | None) -> list[str]:
        title = path[-1] if path else ""
        number = _SECTION_NO.match(title)
        terms = [title[number.end():].strip() if number else title, (label or "").rstrip(" :")]
        values = ([r.label for r in refs] + list(io) + list(self.manifest.product_models) + ([sid] if sid else [])
                  + [lb.text for lb in labels] + terms)
        return _dedupe(v.strip() for v in values if v and v.strip())[: self.cfg.max_keywords]

    def _embed(self, path: Sequence[str], label: str | None, keywords: Sequence[str], content: str,
               summary: str | None = None, faq: Sequence[str] = ()) -> tuple[str, int | None, bool]:
        crumbs = " › ".join([*path, label] if label else path) or self.manifest.doc_title
        head = [f"{', '.join(self.manifest.product_models)} · {self.manifest.doc_title} · {crumbs}"]
        if summary:
            head.append(f"Tóm tắt: {summary}")
        if faq:
            head.append("Câu hỏi thường gặp:")
            head += [f"- {q}" for q in faq]
        if keywords:
            head.append(f"Từ khóa: {', '.join(keywords)}")
        head.append("---")
        count = self.counter or _estimate
        text = "\n".join(head + [content])
        truncated = False
        if count(text) > self.cfg.embed_max_tokens:
            truncated = True
            pieces = [p for line in content.split("\n") for p in _SENTENCE_END.split(line)]
            kept: list[str] = []
            for piece in pieces:
                if count("\n".join(head + kept + [piece])) > self.cfg.embed_max_tokens:
                    break
                kept.append(piece)
            text = "\n".join(head + kept)
        return text, (self.counter(text) if self.counter else None), truncated

    def _flags(self, unit_flags: Sequence[str], content: str, extraction: str, asset_missing: bool,
               truncated: bool) -> list[str]:
        flags = set(unit_flags)
        lines = [line for line in content.split("\n") if line.strip()]
        if len(lines) >= 3 and sum(1 for line in lines if _TOC_LINE.search(line)) >= len(lines) / 2:
            flags.add("toc_like")
        if "�" in content:
            flags.add("replacement_char")
        if extraction in ("ocr", "mixed"):
            flags.add("ocr_page")
        if asset_missing:
            flags.add("asset_missing")
        if truncated:
            flags.add("embed_truncated")
        return sorted(flags)

    def _chunk(self, index: int, units: Sequence[Unit], role: str, parent_key: str | None,
               content: str) -> DraftChunk:
        """Một chunk từ một đơn vị (lá) hoặc nhiều đơn vị (cha: `content` = nối nguyên văn các con)."""
        merged = Unit(chunk_type="section" if role == "parent" else units[0].chunk_type,
                      section_path=units[0].section_path, label=None if role == "parent" else units[0].label,
                      elements=[e for u in units for e in u.elements], lines=content.split("\n"),
                      flags=sorted({f for u in units for f in u.flags}) if role != "parent" else [],
                      table=units[0].table if len(units) == 1 else None,
                      row_ids=[r for u in units for r in u.row_ids],
                      table_pages={p for u in units for p in u.table_pages})
        path = list(merged.section_path)
        pages = self._pages(merged)
        printed_start, printed_end = self._printed(merged, pages)
        refs = self._param_refs(merged)
        io = self._io_codes(content)
        labels = self._figure_labels(merged)
        sid = section_id(path)
        keywords = self._keywords(refs, io, sid, labels, path, merged.label)
        embed, tokens, truncated = self._embed(path, merged.label, keywords, content)
        assets, missing = self._assets(merged)
        blockers, notes = self._reviews(merged)
        extraction = self._extraction(pages)
        applicability = self._applicability(merged)
        title = path[-1] if path else self.manifest.doc_title
        if merged.label and role != "parent":
            title = f"{title} › {merged.label}"
        scopes = sorted({s for u in units for s in self._scopes(u)}, key=SCOPE_ORDER.index)
        title_text = " | ".join(self._title_text(u) for u in units)
        return DraftChunk(
            chunk_key=f"{self.manifest.doc_id}:B{index:04d}", parent_key=parent_key, chunk_role=role,  # type: ignore[arg-type]
            chunk_index=index, scopes=scopes, product_models=list(self.manifest.product_models),
            control_interface=self._matches(self.interface_terms, content + "\n" + " › ".join(path)),
            spec_attributes=self._matches(self.spec_terms, title_text),
            chunk_type=merged.chunk_type,  # type: ignore[arg-type]
            doc_id=self.manifest.doc_id, doc_type=self.manifest.doc_type, doc_title=self.manifest.doc_title,
            doc_version=self.manifest.doc_version, lang=self.manifest.lang, section_id=sid, section_path=path,
            section_title=title, page_start=pages[0], page_end=pages[-1], printed_page_start=printed_start,
            printed_page_end=printed_end, assets=assets, content=content, keywords=keywords, embed_text=embed,
            token_count=tokens, content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            element_ids=[e.element_id for e in merged.elements], extraction=extraction,  # type: ignore[arg-type]
            logical_table_id=merged.table.logical_table_id if merged.table is not None else None,
            row_ids=merged.row_ids, param_refs=refs, io_codes=io, applicability=applicability,
            applies_to_models=sorted({m for c in applicability if c.status == "available_only" for m in c.models}),
            figure_labels=labels, review_blockers=blockers, review_notes=notes,
            flags=self._flags(merged.flags, content, extraction, missing, truncated),
        )

    def assemble(self, plan: ChunkPlan) -> list[DraftChunk]:
        chunks: list[DraftChunk] = []
        for window in plan.windows:
            parent_key = None
            if window.has_parent:
                content = "\n\n".join(u.content for u in window.units)
                parent = self._chunk(len(chunks), window.units, "parent", None, content)
                chunks.append(parent)
                parent_key = parent.chunk_key
            for unit in window.units:
                role = "child" if parent_key else "standalone"
                chunks.append(self._chunk(len(chunks), [unit], role, parent_key, unit.content))
        return self._link_alarms(chunks)

    @staticmethod
    def _link_alarms(chunks: list[DraftChunk]) -> list[DraftChunk]:
        """`alarm` ngay sau `procedure` cùng mục (bỏ qua chunk cha) → `related_chunk_keys` hai chiều (CQ-04)."""
        leaves = [c for c in chunks if c.chunk_role != "parent"]
        links: dict[str, list[str]] = {}
        for prev, cur in zip(leaves, leaves[1:]):
            if (cur.chunk_type == "alarm" and prev.chunk_type == "procedure"
                    and prev.section_path == cur.section_path):
                links.setdefault(cur.chunk_key, []).append(prev.chunk_key)
                links.setdefault(prev.chunk_key, []).append(cur.chunk_key)
        return [c.model_copy(update={"related_chunk_keys": links[c.chunk_key]}) if c.chunk_key in links else c
                for c in chunks]
