"""Gán trường cho chunk (contract C2 §4, §7, §8, §9): lọc, trích dẫn, assets, từ khóa, `embed_text`, review."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Sequence

from app.modules.doc_ingest.build.chunker import VISUAL, ChunkPlan, Unit, estimate_tokens
from app.modules.doc_ingest.build.loader import RunInput, enrichment_key
from app.modules.doc_ingest.enrich.checks import missing_codes
from app.modules.doc_ingest.schemas.chunk import ChunkAsset, DraftChunk, EnrichmentRecord, FigureLabel
from app.modules.doc_ingest.schemas.manifest import SCOPE_ORDER, DocManifest, Scope
from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate, NormalizedElement
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.technical_refs.params import ParamRef

TokenCounter = Callable[[str], int]
_SECTION_NO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s")
_TOC_LINE = re.compile(r"(\.{4,}|…{2,}|�{3,})\s*\.?\s*\d*\s*$")
_TOKEN = re.compile(r"#?[A-Za-z0-9][A-Za-z0-9_\-+]*")
_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")
_VOCAB_SPLIT = re.compile(r"[\s,;:()\[\]/|=]+|\.(?=\s|$)")   # giữ "+", "-" và dấu chấm giữa token (DIR1+, 0.5)


def token_counter() -> tuple[TokenCounter | None, str]:
    """tiktoken `cl100k_base` nếu venv có và đã có file mã hóa; không có → (None, "unavailable")."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:   # venv ingest không có tiktoken, hoặc không tải được file mã hóa
        return None, "unavailable"
    return (lambda text: len(encoding.encode(text))), "tiktoken"


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
        self.vocab = self._vocab(run)
        self.interface_terms = self._terms(profile.vocabulary.control_interface, self.cfg.control_interface_terms)
        self.spec_terms = self._terms(profile.vocabulary.spec_attributes, self.cfg.spec_attribute_terms)
        self.param_patterns = [re.compile(re.escape(p) + rx + r"$") for p, rx in profile.param_text_patterns.items()]
        self._scope_rules = [(r.scope, re.compile(r.title) if r.title else None,
                              re.compile(r.content) if r.content else None, set(r.chunk_types))
                             for r in self.cfg.scope_content_rules]
        # Phần đầu `embed_text` chung cho mọi chunk; chunker dùng để chia phần bảng theo ngân sách token (I-38).
        self.head_tokens = (self.counter or estimate_tokens)(
            f"{', '.join(manifest.product_models)} · {manifest.doc_title} · ")
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
        scopes |= self._content_scopes(unit)
        return [s for s in SCOPE_ORDER if s in scopes]

    def _content_scopes(self, unit: Unit) -> set[Scope]:
        """I-46: scope THÊM theo nội dung (luật `chunking.scope_content_rules` của profile; chỉ thêm, không bớt)."""
        if not self._scope_rules:
            return set()
        titles = list(unit.section_path[max(self.cfg.scope_title_min_level - 1, 0):])
        if unit.label:
            titles.append(unit.label)
        title_text = " › ".join(titles)
        content = unit.content
        found: set[Scope] = set()
        for scope, title_rx, content_rx, types in self._scope_rules:
            if ((title_rx is not None and title_text and title_rx.search(title_text))
                    or (content_rx is not None and content_rx.search(content))
                    or unit.chunk_type in types):
                found.add(scope)  # type: ignore[arg-type]
        return found

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

    @staticmethod
    def _vocab(run: RunInput) -> set[str]:
        """Từ vựng text layer của tài liệu (I-40b): token của mọi phần tử trên trang không OCR (kể cả chữ trong hình
        của text layer) và ô bảng, casefold. Nhãn OCR crop chỉ được tin khi xuất hiện ở đây."""
        texts = [e.text or "" for e in run.elements if e.pdf_page_index not in run.ocr_pages]
        texts += [c.text for t in run.tables.values() for r in t.rows for c in r.cells]
        return {tok.casefold() for text in texts for tok in _VOCAB_SPLIT.split(text) if tok}

    def _in_vocab(self, label: str) -> bool:
        """Nhãn OCR crop đáng tin: khớp mẫu tin cậy của profile, hoặc mọi token có trong từ vựng tài liệu."""
        def trusted(text: str) -> bool:
            return any(re.fullmatch(p, text) for p in self.profile.figure_label_trusted_patterns)

        if trusted(label):
            return True
        tokens = [t for t in _VOCAB_SPLIT.split(label) if t]
        return bool(tokens) and all(trusted(t) or t.casefold() in self.vocab for t in tokens)

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
                labels += [FigureLabel(text=t, element_id=visual.element_id, source="crop_ocr",
                                       verified=not self.cfg.figure_label_require_vocab or self._in_vocab(t))
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
            # I-44: khung chữ (T-20 `text_frame`) chỉ lặp lại chữ đã tách vào `content` → không là asset
            if e.normalized_type not in VISUAL or "text_frame" in e.flags:
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
                  path: Sequence[str], label: str | None, extra: Sequence[str] = (),
                  chunk_type: str | None = None) -> list[str]:
        """`extra`: từ khóa tiếng Việt của Bước 3, luôn giữ (chỗ của chúng trừ vào `max_keywords` trước).
        Nhãn hình nguồn OCR chỉ vào từ khóa khi `chunk_type` thuộc `figure_label_keyword_types`."""
        title = path[-1] if path else ""
        number = _SECTION_NO.match(title)
        terms = [title[number.end():].strip() if number else title, (label or "").rstrip(" :")]
        ocr_ok = chunk_type is None or chunk_type in self.cfg.figure_label_keyword_types
        values = ([r.label for r in refs] + list(io) + list(self.manifest.product_models) + ([sid] if sid else [])
                  + [lb.text for lb in labels if lb.verified and (lb.source == "text_layer" or ocr_ok)] + terms)
        vi = _dedupe(v.strip() for v in extra if v and v.strip())
        base = [v for v in _dedupe(v.strip() for v in values if v and v.strip()) if v not in vi]
        return base[: max(0, self.cfg.max_keywords - len(vi))] + vi

    def _enriched_embed(self, path: Sequence[str], label: str | None, base_keywords: Callable[[Sequence[str]], list[str]],
                        content: str, record: EnrichmentRecord) -> tuple[list[str], str, int | None, bool, list[str]]:
        """Dựng `embed_text` có làm giàu (C2 §8) mà **không đẩy `content` ra ngoài**: vượt `embed_max_tokens` thì bớt
        câu hỏi cuối, rồi bớt từ khóa tiếng Việt, rồi bỏ tóm tắt; cờ `enrich_trimmed`. Trả về (keywords, embed,
        tokens, truncated, flags)."""
        summary: str | None = record.summary_vi
        faq = list(record.faq_vi)
        vi = list(record.keywords_vi)
        trimmed = False
        while True:
            keywords = base_keywords(vi)
            embed, tokens, truncated = self._embed(path, label, keywords, content, summary, faq)
            if not truncated or (not faq and not vi and summary is None):
                break
            trimmed = True
            if faq:
                faq.pop()
            elif vi:
                vi.pop()
            else:
                summary = None
        flags = ["enrich_trimmed"] if trimmed else []
        context = "\n".join([content, " ".join(self.manifest.product_models), " › ".join(path)])   # = chunk_context
        if missing_codes(" ".join([record.summary_vi, *record.faq_vi]), context):
            flags.append("enrich_code_mismatch")
        return keywords, embed, tokens, truncated, flags

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
        count = self.counter or estimate_tokens
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
               truncated: bool, over_budget: bool = False) -> list[str]:
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
        if over_budget:
            flags.add("embed_over_budget")
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
        # D-008 (I-43): chỉ chunk lá được embed, tìm và làm giàu; `embed_text` của cha giữ cho schema/export.
        leaf = role != "parent"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        record = self.run.enrichment.get(enrichment_key(content_hash, path)) if leaf else None
        enrich_flags: list[str] = []
        ctype = merged.chunk_type
        if record is None:
            keywords = self._keywords(refs, io, sid, labels, path, merged.label, chunk_type=ctype)
            embed, tokens, truncated = self._embed(path, merged.label, keywords, content)
        else:
            keywords, embed, tokens, truncated, enrich_flags = self._enriched_embed(
                path, merged.label,
                lambda vi: self._keywords(refs, io, sid, labels, path, merged.label, vi, chunk_type=ctype),
                content, record)
        # Chưa làm giàu: phải chừa `embed_enrich_reserve`; đã làm giàu: chỗ dự trữ đã dùng, giới hạn là `embed_max_tokens`.
        budget = self.cfg.embed_max_tokens - (0 if record is not None else self.cfg.embed_enrich_reserve)
        over_budget = leaf and tokens is not None and tokens > budget
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
            summary_vi=record.summary_vi if record else None, faq_vi=list(record.faq_vi) if record else [],
            enrichment_status=("none" if record is None else "approved"
                               if self.run.approval is not None and record.prompt_version == self.run.approval.version
                               else "draft"),
            token_count=tokens, content_hash=content_hash,
            element_ids=[e.element_id for e in merged.elements], extraction=extraction,  # type: ignore[arg-type]
            logical_table_id=merged.table.logical_table_id if merged.table is not None else None,
            row_ids=merged.row_ids, param_refs=refs, io_codes=io, applicability=applicability,
            applies_to_models=sorted({m for c in applicability if c.status == "available_only" for m in c.models}),
            figure_labels=labels, review_blockers=blockers, review_notes=notes,
            flags=self._flags([*merged.flags, *enrich_flags], content, extraction, missing, truncated and leaf,
                              over_budget),
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
