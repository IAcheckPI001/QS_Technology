"""Chia đơn vị chunk và cửa sổ cha–con (contract C2 §5, §6). Deterministic, không LLM.

Trình tự:
1. Luồng phần tử theo `reading_order`, bỏ phần tử không vào chunk (§6); caption đi cùng hình/bảng sở hữu nó;
   mỗi bảng logic xuất hiện một lần tại segment đầu.
2. Nhóm theo mục (`section_path` liên tiếp), trong mục nhóm theo khối `label_heading` liên tiếp. Bảng là khối riêng.
3. Khối chỉ có heading/label heading gộp vào khối sau (trước bảng thì thành dòng dẫn của bảng).
4. Phân loại khối: parameter (có định nghĩa T-12) → procedure (≥ 2 bước, hoặc label heading thủ tục + ≥ 2 mục
   list) → figure (có hình, chữ ≤ `figure_text_max`) → overview. Chuỗi ≥ 2 khối có label heading dạng bước
   ("Stage 1:", "Stage 2:" …) gộp thành một thủ tục, kèm khối dẫn ngắn ngay trước.
5. Tách: parameter theo nhóm định nghĩa ≤ `child_soft_max`; thủ tục và khối khác giữ nguyên tới `parent_max`,
   dài hơn thì tách ở ranh giới bước/phần tử; bảng theo nhóm dòng, lặp header.
6. Gộp overview liên tiếp cùng mục tới `child_soft_max`; loại ngữ nghĩa theo `chunk_type_rules`.
7. Cửa sổ cha: đơn vị liên tiếp cùng mục (bảng ngắt cửa sổ), tổng ≤ `parent_max`; cửa sổ ≥ 2 con mới tạo cha.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.build.render import data_rows, element_line, header_line, row_line, separator_line
from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement, Row
from app.modules.doc_ingest.schemas.profile import Chunking, Profile

_CODE_TOKEN = re.compile(r"#?[A-Za-z0-9][A-Za-z0-9_\-+]*")   # như `fields._TOKEN`: ứng viên mã vào từ khóa
_HEAD_SLACK = 16   # token của "Từ khóa:", "---", model, section_id và dấu nối trong phần đầu `embed_text`

VISUAL = frozenset({"picture", "screenshot"})
TITLE_TYPES = frozenset({"heading", "label_heading"})
TEXT_TYPES = frozenset({"text", "list_item", "warning"})
EXCLUDED_TYPES = {
    "furniture": "furniture", "figure_text": "figure_text", "toc": "toc",
    "watermark_candidate": "watermark", "unsupported": "unsupported",
}


@dataclass
class TableItem:
    table: LogicalTable
    first: NormalizedElement
    caption: NormalizedElement | None


@dataclass
class Block:
    label: str | None
    elements: list[NormalizedElement] = field(default_factory=list)
    table: TableItem | None = None
    lead: list[NormalizedElement] = field(default_factory=list)   # heading/label heading dẫn trước bảng


@dataclass
class Unit:
    """Một chunk lá (con hoặc độc lập) trước khi gán trường."""

    chunk_type: str
    section_path: tuple[str, ...]
    label: str | None
    elements: list[NormalizedElement]           # phần tử nguồn theo thứ tự (gồm hình, caption, dòng dẫn)
    lines: list[str]
    flags: list[str] = field(default_factory=list)
    table: LogicalTable | None = None
    row_ids: list[str] = field(default_factory=list)
    table_pages: set[int] = field(default_factory=set)

    @property
    def content(self) -> str:
        return "\n".join(self.lines)


@dataclass
class Window:
    section_path: tuple[str, ...]
    units: list[Unit]

    @property
    def has_parent(self) -> bool:
        return len(self.units) >= 2


@dataclass
class ChunkPlan:
    windows: list[Window]
    excluded: Counter[str] = field(default_factory=Counter)
    heading_only: list[str] = field(default_factory=list)    # element_id heading của mục không có nội dung


def _lines(elements: Sequence[NormalizedElement]) -> list[str]:
    return [line for line in (element_line(e) for e in elements) if line is not None]


def _length(elements: Sequence[NormalizedElement]) -> int:
    return len("\n".join(_lines(elements)))


def _any(patterns: Sequence[str], text: str | None) -> bool:
    return bool(text) and any(re.search(p, text or "") for p in patterns)


def estimate_tokens(text: str) -> int:
    """Ước lượng khi không có tiktoken (venv ingest): 4 ký tự một token."""
    return (len(text) + 3) // 4


class Chunker:
    def __init__(self, profile: Profile, elements: Sequence[NormalizedElement], tables: dict[str, LogicalTable],
                 count: Callable[[str], int] | None = None, head_tokens: int = 0,
                 exclude_pages: Sequence[int] = (), exclude_sections: Sequence[str] = ()) -> None:
        """`count`: bộ đếm token của `embed_text` (mặc định ước lượng); `head_tokens`: token phần đầu
        `embed_text` chung cho mọi chunk của tài liệu (model · tên tài liệu), builder đo từ manifest.
        `exclude_pages`/`exclude_sections`: trang/mục manifest loại khỏi chunk (lý do `manifest_excluded`)."""
        self.cfg: Chunking = profile.chunking
        self.exclude_pages = frozenset(exclude_pages)
        self.exclude_sections = tuple(s.strip() for s in exclude_sections if s.strip())
        self.count = count or estimate_tokens
        self.head_tokens = head_tokens
        self.code_patterns = profile.code_patterns
        self.param_patterns = [re.compile(re.escape(p) + rx + r"$") for p, rx in profile.param_text_patterns.items()]
        self.symbol_prefixes = [p for p in profile.param_prefixes if not p.isalpha()]
        self.caption_keywords = profile.caption_keywords
        self.elements = list(elements)
        self.by_id = {e.element_id: e for e in self.elements}
        self.tables = tables
        self.excluded: Counter[str] = Counter()
        self.heading_only: list[str] = []

    # 1. luồng phần tử ------------------------------------------------------------------------------
    def exclusion(self, e: NormalizedElement) -> str | None:
        if e.content_layer == "furniture":
            return "furniture"
        if e.normalized_type in EXCLUDED_TYPES:
            return EXCLUDED_TYPES[e.normalized_type]
        if e.duplicate_of is not None:
            return "duplicate_image"
        if e.normalized_type == "table_segment" and (e.table_ref is None or e.table_ref.logical_table_id
                                                     not in self.tables):
            return "table_missing"
        if e.pdf_page_index in self.exclude_pages or any(
                title.startswith(prefix) for title in e.section_path for prefix in self.exclude_sections):
            return "manifest_excluded"
        return None

    def _flow(self) -> list[NormalizedElement | TableItem]:
        kept = [e for e in self.elements if self.exclusion(e) is None]
        kept_ids = {e.element_id for e in kept}
        owned = {e.caption_element_id: e for e in kept
                 if e.caption_element_id and e.caption_element_id in kept_ids
                 and (e.normalized_type in VISUAL or e.normalized_type == "table_segment")}
        for e in self.elements:
            reason = self.exclusion(e)
            if reason is not None:
                self.excluded[reason] += 1
        flow: list[NormalizedElement | TableItem] = []
        seen_tables: set[str] = set()
        for e in kept:
            if e.element_id in owned:
                continue
            if e.normalized_type == "table_segment":
                assert e.table_ref is not None
                tid = e.table_ref.logical_table_id
                if tid in seen_tables:
                    continue
                seen_tables.add(tid)
                caption = self.by_id.get(e.caption_element_id) if e.caption_element_id else None
                flow.append(TableItem(self.tables[tid], e, caption))
                continue
            flow.append(e)
            if e.normalized_type in VISUAL and e.caption_element_id in owned:
                flow.append(self.by_id[e.caption_element_id])   # caption ngay sau hình sở hữu nó
        return flow

    # 2–3. mục, khối --------------------------------------------------------------------------------
    @staticmethod
    def _path(item: NormalizedElement | TableItem) -> tuple[str, ...]:
        e = item.first if isinstance(item, TableItem) else item
        return tuple(e.section_path)

    def _sections(self, flow: list[NormalizedElement | TableItem]) -> list[tuple[tuple[str, ...], list[Block]]]:
        sections: list[tuple[tuple[str, ...], list[NormalizedElement | TableItem]]] = []
        for item in flow:
            path = self._path(item)
            if sections and sections[-1][0] == path:
                sections[-1][1].append(item)
            else:
                sections.append((path, [item]))
        out = []
        for path, items in sections:
            blocks: list[Block] = []
            for item in items:
                if isinstance(item, TableItem):
                    blocks.append(Block(label=item.first.label_heading, table=item))
                elif (blocks and blocks[-1].table is None and blocks[-1].label == item.label_heading
                      and not (item.normalized_type == "heading" and blocks[-1].elements)):
                    blocks[-1].elements.append(item)
                else:
                    blocks.append(Block(label=item.label_heading, elements=[item]))
            out.append((path, self._merge_title_blocks(blocks)))
        return out

    @staticmethod
    def _title_only(block: Block) -> bool:
        return block.table is None and all(e.normalized_type in TITLE_TYPES for e in block.elements)

    def _table_lead(self, block: Block) -> bool:
        """Heading/label heading + một dòng dẫn ngắn kết thúc bằng ":" (vd. "1.1 Overview / Specification:")."""
        if block.table is not None or not block.elements:
            return False
        *titles, last = block.elements
        text = (last.text or "").strip()
        return (all(e.normalized_type in TITLE_TYPES for e in titles) and last.normalized_type == "text"
                and text.endswith(":") and len(text) <= self.cfg.table_lead_max)

    @staticmethod
    def _title_figure(block: Block) -> bool:
        """Chỉ có heading/label heading và hình không caption: không mang nội dung riêng."""
        types = {e.normalized_type for e in block.elements}
        return (block.table is None and bool(types & TITLE_TYPES) and bool(types & VISUAL)
                and types <= TITLE_TYPES | VISUAL)

    def _merge_title_blocks(self, blocks: list[Block]) -> list[Block]:
        """R-04: khối chỉ có heading/label heading gộp vào khối sau (bảng: thành dòng dẫn), cuối mục thì vào
        khối trước. Khối tiêu đề + hình không caption (I-37) gộp vào khối sau cùng mục, hết khối thì vào khối
        trước; đứng trước bảng hoặc là nội dung duy nhất của mục thì giữ nguyên là khối hình."""
        merged = self._merge_titles(blocks)
        out: list[Block] = []
        i = 0
        while i < len(merged):
            j = i
            while j < len(merged) and self._title_figure(merged[j]):
                j += 1
            run = merged[i:j]
            if not run:
                out.append(merged[i])
                i += 1
                continue
            elements = [e for b in run for e in b.elements]
            if j < len(merged) and merged[j].table is None:
                merged[j].elements = elements + merged[j].elements
            elif j == len(merged) and out and out[-1].table is None:
                out[-1].elements.extend(elements)
            else:
                out.extend(run)
            i = j
        return out

    def _merge_titles(self, blocks: list[Block]) -> list[Block]:
        out: list[Block] = []
        pending: list[NormalizedElement] = []
        for index, block in enumerate(blocks):
            before_table = index + 1 < len(blocks) and blocks[index + 1].table is not None
            if self._title_only(block) or (before_table and self._table_lead(block)):
                pending.extend(block.elements)
                continue
            if pending:
                if block.table is not None:
                    block.lead = pending + block.lead
                else:
                    block.elements = pending + block.elements
                pending = []
            out.append(block)
        if pending:
            if out and out[-1].table is None:
                out[-1].elements.extend(pending)
            elif out:
                out[-1].lead.extend(pending)
            else:
                self.heading_only.extend(e.element_id for e in pending)
        return out

    # 4. phân loại ----------------------------------------------------------------------------------
    def _is_caption_text(self, e: NormalizedElement) -> bool:
        text = (e.text or "").lstrip()
        return any(text.startswith(k) for k in self.caption_keywords)

    def _is_step(self, e: NormalizedElement) -> bool:
        if e.normalized_type == "caption" and self._is_caption_text(e):
            return False
        return e.normalized_type in TEXT_TYPES | {"caption"} and _any(self.cfg.step_patterns, e.text)

    def _is_step_label(self, e: NormalizedElement) -> bool:
        """Label heading dạng bước ("Step 1:") cũng là một bước của khối (I-35)."""
        return e.normalized_type == "label_heading" and _any(self.cfg.step_patterns, e.text)

    def _text_chars(self, elements: Sequence[NormalizedElement]) -> int:
        return sum(len(e.text or "") for e in elements if e.normalized_type in TEXT_TYPES)

    def _classify(self, block: Block) -> str:
        els = block.elements
        if any(r.role == "definition" for e in els for r in e.param_refs):
            return "parameter"
        steps = sum(1 for e in els if self._is_step(e) or self._is_step_label(e))
        top_items = sum(1 for e in els if e.normalized_type == "list_item"
                        and (e.list_info is None or e.list_info.depth == 0))
        if steps >= 2 or (_any(self.cfg.procedure_title_patterns, block.label) and top_items >= 2):
            return "procedure"
        # khung chữ (T-20 `text_frame`) không phải hình: không là asset (I-44) nên không làm khối thành chunk hình
        if (any(e.normalized_type in VISUAL and "text_frame" not in e.flags for e in els)
                and self._text_chars(els) <= self.cfg.figure_text_max):
            return "figure"
        return "overview"

    def _step_block(self, block: Block) -> bool:
        return block.table is None and _any(self.cfg.step_patterns, block.label)

    def _is_lead(self, e: NormalizedElement) -> bool:
        """Câu dẫn ngắn của thủ tục (I-42): text thường, không phải bước, ≤ `procedure_lead_max`."""
        text = (e.text or "").strip()
        return (e.normalized_type == "text" and not self._is_step(e)
                and 0 < len(text) <= self.cfg.procedure_lead_max)

    def _step_number(self, group: list[NormalizedElement]) -> int | None:
        first = next((e for e in group if self._is_step(e) or self._is_step_label(e)), None)
        match = re.search(r"\d+", first.text or "") if first is not None else None
        return int(match.group()) if match else None

    def _split_restarts(self, groups: list[list[NormalizedElement]]) -> list[list[list[NormalizedElement]]]:
        """I-42 (C2 R-02): chuỗi khối bước đánh số lại từ đầu ("Step 1" sau "Step 2") là thủ tục mới. Câu dẫn ngắn
        cuối khối bước trước (và hình/caption ngay trước nó, cùng trang với câu dẫn nhưng khác trang mở bước trước)
        thuộc thủ tục mới."""
        procs: list[list[list[NormalizedElement]]] = []
        last: int | None = None
        for group in groups:
            number = self._step_number(group)
            if procs and number is not None and last is not None and number <= last:
                prev = procs[-1][-1]
                k = len(prev)
                if k > 2 and self._is_lead(prev[-1]):
                    k -= 1
                    page = prev[-1].pdf_page_index
                    while (k > 2 and prev[k - 1].normalized_type in VISUAL | {"caption"}
                           and prev[k - 1].pdf_page_index == page and prev[0].pdf_page_index != page):
                        k -= 1
                procs[-1][-1], lead = prev[:k], prev[k:]
                procs.append([lead + group])
            elif procs:
                procs[-1].append(group)
            else:
                procs.append([group])
            last = number if number is not None else last
        return procs

    # 5. tách ---------------------------------------------------------------------------------------
    @staticmethod
    def _pack(groups: list[list[NormalizedElement]], limit: int) -> list[list[NormalizedElement]]:
        packs: list[list[NormalizedElement]] = []
        for group in groups:
            if packs and _length(packs[-1] + group) <= limit:
                packs[-1] = packs[-1] + group
            else:
                packs.append(list(group))
        return packs

    def _unit(self, chunk_type: str, path: tuple[str, ...], label: str | None,
              elements: list[NormalizedElement], flags: Sequence[str] = (),
              title: str | None = None) -> Unit:
        lines = ([title] if title else []) + _lines(elements)
        return Unit(chunk_type, path, label, elements, lines, list(flags))

    def _split_groups(self, elements: list[NormalizedElement], starts: set[str]) -> list[list[NormalizedElement]]:
        groups: list[list[NormalizedElement]] = []
        for e in elements:
            if e.element_id in starts and groups and any(x.element_id in starts for x in groups[-1]):
                groups.append([e])
            elif groups:
                groups[-1].append(e)
            else:
                groups.append([e])
        return groups

    def _parameter_units(self, path: tuple[str, ...], block: Block) -> list[Unit]:
        starts = {e.element_id for e in block.elements
                  if any(r.role == "definition" for r in e.param_refs)
                  and (e.list_info is None or e.list_info.parent_element_id is None)}
        packs = self._pack(self._split_groups(block.elements, starts), self.cfg.child_soft_max)
        return [self._unit("parameter", path, block.label, p) for p in packs]

    def _procedure_units(self, path: tuple[str, ...], label: str | None,
                         groups: list[list[NormalizedElement]]) -> list[Unit]:
        elements = [e for g in groups for e in g]
        if _length(elements) <= self.cfg.parent_max:
            return [self._unit("procedure", path, label, elements)]
        title_text = label or (element_line(elements[0]) or "")
        reserve = len(title_text) + 40
        packs: list[list[list[NormalizedElement]]] = []
        for group in groups:
            if packs and _length([e for g in packs[-1] for e in g] + group) <= self.cfg.parent_max - reserve:
                packs[-1].append(group)
            else:
                packs.append([group])
        units, step_no, n = [], 0, len(packs)
        for i, pack in enumerate(packs, start=1):
            first_step = step_no + 1
            step_no += len(pack)
            title = None if i == 1 else f"{title_text} (phần {i}/{n}, bước {first_step}–{step_no})"
            units.append(self._unit("procedure", path, label, [e for g in pack for e in g],
                                    ["procedure_split"], title))
        return units

    def _block_units(self, path: tuple[str, ...], block: Block, kind: str) -> list[Unit]:
        if kind == "parameter":
            return self._parameter_units(path, block)
        if kind == "procedure":
            starts = {e.element_id for e in block.elements
                      if self._is_step(e) or self._is_step_label(e)
                      or (e.normalized_type == "list_item" and (e.list_info is None or e.list_info.depth == 0))}
            return self._procedure_units(path, block.label, self._split_groups(block.elements, starts))
        if _length(block.elements) <= self.cfg.parent_max:
            return [self._unit(kind, path, block.label, block.elements)]
        parts = self._block_parts(path, block, kind)
        if parts is not None:
            return parts
        packs = self._pack([[e] for e in block.elements], self.cfg.parent_max)
        return [self._unit(kind, path, block.label, p, ["block_split"]) for p in packs]

    def _part_groups(self, elements: list[NormalizedElement]) -> list[list[NormalizedElement]] | None:
        """Nhóm theo đầu phần (`block_part_patterns`, I-39). Đầu phần liền nhau ("Case 1:" rồi "Example 1:") là một
        đầu nhóm; hình đứng ngay trước đầu phần đi theo nhóm đó. Nhóm đầu là phần dẫn nếu khối không mở bằng đầu
        phần. Không có đầu phần nào → None."""
        if not self.cfg.block_part_patterns:
            return None
        starts: list[int] = []
        prev = False
        for i, e in enumerate(elements):
            hit = e.normalized_type not in VISUAL and _any(self.cfg.block_part_patterns, (e.text or "").strip())
            if hit and not prev:
                j = i
                while j > 0 and elements[j - 1].normalized_type in VISUAL and (not starts or j - 1 > starts[-1]):
                    j -= 1
                starts.append(j)
            prev = hit
        if not starts:
            return None
        bounds = ([0] if starts[0] > 0 else []) + starts + [len(elements)]
        return [elements[a:b] for a, b in zip(bounds, bounds[1:])]

    def _code_cost(self, text: str) -> int:
        """Token mã I/O của `text` thêm vào dòng "Từ khóa:" (cùng điều kiện với `fields.Assembler._io_codes`;
        mã parameter tính riêng)."""
        codes = {t for t in _CODE_TOKEN.findall(text)
                 if any(re.search(p, t) for p in self.code_patterns)
                 and not any(p.match(t) for p in self.param_patterns)
                 and not any(t.startswith(pfx) for pfx in self.symbol_prefixes)}
        return sum(self.count(t) + 2 for t in codes)

    def _block_parts(self, path: tuple[str, ...], block: Block, kind: str) -> list[Unit] | None:
        """Khối dài có đầu phần (I-39, C2 R-12): chia ở ranh giới nhóm, mỗi phần ≤ `parent_max` ký tự và `embed_text`
        ≤ `embed_max_tokens` − `embed_enrich_reserve`; phần 2…n mở bằng tiêu đề "(phần i/n)" + phần dẫn chung
        (≤ `block_lead_max`). Nhóm một mình vượt giới hạn → chia theo phần tử trong nhóm."""
        groups = self._part_groups(block.elements)
        if groups is None:
            return None
        has_lead = not _any(self.cfg.block_part_patterns,
                            next((e.text or "" for e in groups[0] if e.normalized_type not in VISUAL), ""))
        lead = groups[0] if has_lead else []
        if lead and lead[0].normalized_type in TITLE_TYPES:
            title_text, rest = element_line(lead[0]) or "", _lines(lead[1:])
        else:
            title_text, rest = block.label or (path[-1] if path else ""), _lines(lead)
        repeat = rest if len("\n".join(rest)) <= self.cfg.block_lead_max else []
        crumbs = " › ".join([*path, block.label] if block.label else path)
        fixed = self.head_tokens + self.count(crumbs) + self.count(path[-1] if path else "") + _HEAD_SLACK
        title_cost = self.count("\n".join([f"{title_text} (phần 9/9)", *repeat])) + 1
        title_chars = len("\n".join([f"{title_text} (phần 9/9)", *repeat])) + 1
        budget = self.cfg.embed_max_tokens - self.cfg.embed_enrich_reserve
        char_limit = self.cfg.parent_max - title_chars

        def cost(elements: list[NormalizedElement]) -> tuple[int, int]:
            text = "\n".join(_lines(elements))
            params = {r.label for e in elements for r in e.param_refs}     # mã parameter vào "Từ khóa:"
            return (self.count(text) + 1 + self._code_cost(text) + sum(self.count(p) + 2 for p in params),
                    len(text) + 1)

        atoms: list[list[NormalizedElement]] = []
        oversize: set[int] = set()              # atom thuộc nhóm một mình quá dài, đã chia theo phần tử
        origin: list[int] = []                  # nhóm gốc của mỗi atom
        for g, group in enumerate(groups):
            tokens, chars = cost(group)
            if chars > char_limit or fixed + title_cost + tokens > budget:
                pieces: list[list[NormalizedElement]] = []
                for e in group:                    # chia theo phần tử; hình dính với phần tử ngay sau
                    if pieces and all(x.normalized_type in VISUAL for x in pieces[-1]):
                        pieces[-1].append(e)
                    else:
                        pieces.append([e])
                oversize.update(range(len(atoms), len(atoms) + len(pieces)))
                atoms.extend(pieces)
                origin.extend([g] * len(pieces))
            else:
                atoms.append(group)
                origin.append(g)
        costs = [cost(a) for a in atoms]

        def joinable(i: int, j: int) -> bool:
            """Mảnh của nhóm quá dài chỉ gói với mảnh cùng nhóm, không trộn với nhóm khác."""
            return origin[i] == origin[j] or (i not in oversize and j not in oversize)

        def pack(limit: int) -> list[list[int]]:
            parts: list[list[int]] = []
            tokens = chars = 0
            for i, (a_tokens, a_chars) in enumerate(costs):
                if (parts and joinable(parts[-1][-1], i)
                        and tokens + a_tokens <= limit and chars + a_chars <= char_limit):
                    parts[-1].append(i)
                    tokens, chars = tokens + a_tokens, chars + a_chars
                else:
                    parts.append([i])
                    tokens, chars = fixed + title_cost + a_tokens, title_chars + a_chars
            return parts

        n_parts = len(pack(budget))
        low, high = 1, budget                  # giới hạn nhỏ nhất vẫn cho cùng số phần → các phần cân nhau
        while low < high:
            mid = (low + high) // 2
            if len(pack(mid)) <= n_parts:
                high = mid
            else:
                low = mid + 1
        parts = pack(high)
        units = []
        for i, idx in enumerate(parts, start=1):
            elements = [e for k in idx for e in atoms[k]]
            title = None if i == 1 else "\n".join([f"{title_text} (phần {i}/{len(parts)})", *repeat])
            flags = ["block_split"] + (["block_part_oversize"] if oversize.intersection(idx) else [])
            units.append(self._unit(kind, path, block.label, elements, flags, title))
        return units

    @staticmethod
    def _group_row(table: LogicalTable, row: Row) -> bool:
        """Dòng nhóm: bảng nhiều cột, dòng chỉ có một ô có chữ và không mang mã parameter ("X axis")."""
        return (len(table.columns) > 1 and row.param_ref is None
                and sum(1 for c in row.cells if c.text.strip()) == 1)

    def _row_cost(self, table: LogicalTable, row: Row) -> int:
        """Token một dòng chiếm trong `embed_text`: dòng bảng + phần của nó trong dòng "Từ khóa:"."""
        line = row_line(table, row)
        cost = self.count(line) + 1
        if row.param_ref is not None:
            cost += self.count(row.param_ref.label) + 2
        # Mã I/O vào từ khóa theo cùng điều kiện với `fields.Assembler._io_codes` (mã parameter đã tính ở trên).
        return cost + self._code_cost(line)

    def _table_parts(self, table: LogicalTable, rows: list[Row], first: list[str], repeat: str, head: list[str],
                     fixed: int) -> list[tuple[list[Row], Row | None]]:
        """Chia dòng thành các phần (contract C2 §6, I-38): mỗi phần ≤ `parent_max` ký tự và `embed_text` của nó
        ≤ `embed_max_tokens` − `embed_enrich_reserve`; chỉ chia ở ranh giới dòng; dòng nhóm đi cùng dòng sau nó và
        được lặp lại ở phần sau khi nhóm bị chia; chi phí các phần được cân bằng (không còn phần đuôi một dòng).
        Trả về [(dòng của phần, dòng nhóm lặp lại ở đầu phần hoặc None)]."""
        atoms: list[list[Row]] = []
        for row in rows:                       # dòng nhóm dính với dòng ngay sau
            if atoms and self._group_row(table, atoms[-1][-1]):
                atoms[-1].append(row)
            else:
                atoms.append([row])
        lines = {r.row_id: row_line(table, r) for r in rows}
        costs = {r.row_id: self._row_cost(table, r) for r in rows}
        head_chars = len("\n".join(head)) + 1 if head else 0
        head_tokens = self.count("\n".join(head)) + 1 if head else 0
        char_limit = self.cfg.parent_max - len(repeat) - 20

        def pack(limit: int) -> list[tuple[list[Row], Row | None]]:
            parts: list[tuple[list[Row], Row | None]] = []
            tokens = chars = 0
            group: Row | None = None           # dòng nhóm đang mở
            for atom in atoms:
                a_tokens = sum(costs[r.row_id] for r in atom)
                a_chars = sum(len(lines[r.row_id]) + 1 for r in atom)
                if parts and tokens + a_tokens <= limit and chars + a_chars <= char_limit:
                    parts[-1][0].extend(atom)
                    tokens, chars = tokens + a_tokens, chars + a_chars
                else:
                    title = first if not parts else [f"{repeat} (phần 9/9)"]
                    carried = group if parts and not self._group_row(table, atom[0]) else None
                    tokens = (fixed + self.count("\n".join(title)) + head_tokens + a_tokens
                              + (costs[carried.row_id] if carried else 0))
                    chars = (len("\n".join(title)) + 1 + head_chars + a_chars
                             + (len(lines[carried.row_id]) + 1 if carried else 0))
                    parts.append((list(atom), carried))
                for row in atom:
                    if self._group_row(table, row):
                        group = row
            return parts

        budget = self.cfg.embed_max_tokens - self.cfg.embed_enrich_reserve
        parts = pack(budget)
        low, high = 1, budget                  # giới hạn nhỏ nhất vẫn cho cùng số phần → các phần cân nhau
        while low < high:
            mid = (low + high) // 2
            if len(pack(mid)) <= len(parts):
                high = mid
            else:
                low = mid + 1
        return pack(high)

    def _table_units(self, path: tuple[str, ...], block: Block) -> list[Unit]:
        item = block.table
        assert item is not None
        table = item.table
        header = header_line(table)
        rows = data_rows(table) if header else [r for r in table.rows if not r.repeated_header]
        head = [header, separator_line(table)] if header else []
        lead_lines = _lines(block.lead)
        caption_line = (item.caption.text or "").strip() if item.caption else ""
        intro = lead_lines + ([caption_line] if caption_line else [])
        kind = "parameter" if ("param_table" in table.flags or any(r.param_ref for r in table.rows)) else "table"
        repeat = caption_line or (lead_lines[-1] if lead_lines else (path[-1] if path else ""))
        # Phần cố định của `embed_text` ngoài nội dung bảng: dòng model · tài liệu · mục, "Từ khóa:" + thuật ngữ mục.
        crumbs = " › ".join([*path, block.label] if block.label else path)
        fixed = self.head_tokens + self.count(crumbs) + self.count(path[-1] if path else "") + _HEAD_SLACK
        parts = self._table_parts(table, rows, intro, repeat, head, fixed)
        units = []
        n = len(parts)
        segment_elements = {s.element_id: s for s in table.segments}
        for i, (part, group) in enumerate(parts, start=1):
            title_lines = intro if i == 1 else [f"{repeat} (phần {i}/{n})"]
            lines = (title_lines + head + ([row_line(table, group)] if group is not None else [])
                     + [row_line(table, r) for r in part])
            seg_ids = {table.segments[r.segment].element_id for r in part if r.segment < len(table.segments)}
            elements = (list(block.lead) + ([item.caption] if item.caption else []) if i == 1 else [])
            elements += [self.by_id[s] for s in segment_elements if s in seg_ids and s in self.by_id]
            pages = {table.segments[r.segment].pdf_page_index for r in part if r.segment < len(table.segments)}
            flags = (["table_part"] if n > 1 else []) + ([] if header else ["table_no_header"])
            units.append(Unit(kind, path, block.label, elements, lines, flags, table,
                              [r.row_id for r in part], pages))
        if not parts:   # bảng không có dòng dữ liệu
            units.append(Unit(kind, path, block.label, list(block.lead) + ([item.caption] if item.caption else [])
                              + [item.first], intro + head, ["table_empty"], table, [], {item.first.pdf_page_index}))
        return units

    def _section_units(self, path: tuple[str, ...], blocks: list[Block]) -> list[Unit]:
        kinds = [None if b.table else self._classify(b) for b in blocks]
        units: list[Unit] = []
        i = 0
        while i < len(blocks):
            block = blocks[i]
            if block.table is not None:
                units.extend(self._table_units(path, block))
                i += 1
                continue
            # khối thủ tục không nhãn bước (bước đầu là text thường) ngay trước chuỗi khối bước → cùng một thủ tục
            j = i + 1
            if kinds[i] == "procedure" and not self._step_block(block) and any(self._is_step(e)
                                                                              for e in block.elements):
                while j < len(blocks) and kinds[j] != "parameter" and self._step_block(blocks[j]):
                    j += 1
            if j - i >= 2:
                starts = {e.element_id for e in block.elements if self._is_step(e)}
                groups = self._split_groups(block.elements, starts) + [b.elements for b in blocks[i + 1:j]]
                units.extend(self._procedure_units(path, block.label, groups))
                i = j
                continue
            # chuỗi khối bước ("Stage 1:", "Stage 2:" …) → một thủ tục
            j = i
            while j < len(blocks) and kinds[j] != "parameter" and self._step_block(blocks[j]):
                j += 1
            if j - i >= 2:
                groups = [b.elements for b in blocks[i:j]]
                label = blocks[i].label
                prev = units[-1] if units else None
                # khối dẫn ngắn ngay trước: có label heading, hoặc kết thúc bằng câu dẫn ngắn (I-42: tiêu đề + hình
                # + "Determine … using 4 points …")
                if (prev is not None and prev.table is None and prev.chunk_type in ("overview", "figure")
                        and self._text_chars(prev.elements) <= self.cfg.figure_text_max
                        and (prev.label is not None or self._is_lead(prev.elements[-1]))
                        and i > 0 and blocks[i - 1].table is None):
                    units.pop()
                    groups[0] = prev.elements + groups[0]
                    label = prev.label or label
                for proc_groups in self._split_restarts(groups):
                    units.extend(self._procedure_units(path, label, proc_groups))
                i = j
                continue
            units.extend(self._block_units(path, block, kinds[i] or "overview"))
            i += 1
        return self._attach_empty(self._merge_overview(self._merge_figure_notes(units)))

    def _merge_figure_notes(self, units: list[Unit]) -> list[Unit]:
        """I-45 (C2 R-14): đoạn/ghi chú ngắn (`overview`) ngay sau chunk hình cùng mục gộp vào chunk hình khi tổng chữ
        ≤ `figure_text_max` (F54 2.2: Figure 6 nguồn cấp + "Note: …" là một ý, không tách thành hai chunk vụn)."""
        out: list[Unit] = []
        for unit in units:
            prev = out[-1] if out else None
            if (prev is not None and prev.chunk_type == "figure" and unit.chunk_type == "overview"
                    and prev.table is None and unit.table is None
                    and "block_split" not in prev.flags and "block_split" not in unit.flags
                    and self._text_chars(prev.elements + unit.elements) <= self.cfg.figure_text_max):
                out[-1] = Unit("figure", prev.section_path, prev.label, prev.elements + unit.elements,
                               prev.lines + unit.lines, sorted(set(prev.flags + unit.flags)))
            else:
                out.append(unit)
        return out

    def _merge_overview(self, units: list[Unit]) -> list[Unit]:
        out: list[Unit] = []
        for unit in units:
            prev = out[-1] if out else None
            if (prev is not None and prev.chunk_type == "overview" and unit.chunk_type == "overview"
                    and prev.table is None and unit.table is None
                    and "block_split" not in prev.flags and "block_split" not in unit.flags   # I-39: giữ phần
                    and len(prev.content) + 1 + len(unit.content) <= self.cfg.child_soft_max):
                out[-1] = Unit("overview", prev.section_path, prev.label, prev.elements + unit.elements,
                               prev.lines + unit.lines, sorted(set(prev.flags + unit.flags)))
            else:
                out.append(unit)
        return out

    @staticmethod
    def _attach_empty(units: list[Unit]) -> list[Unit]:
        """Đơn vị không có chữ (chỉ hình): gắn hình vào đơn vị trước (hoặc sau) cùng mục."""
        out: list[Unit] = []
        orphans: list[NormalizedElement] = []
        for unit in units:
            if not unit.content.strip() and unit.table is None:
                if out:
                    out[-1].elements.extend(unit.elements)
                    out[-1].flags = sorted(set(out[-1].flags) | {"assets_attached_to_neighbor"})
                else:
                    orphans.extend(unit.elements)
                continue
            if orphans:
                unit.elements = orphans + unit.elements
                unit.flags = sorted(set(unit.flags) | {"assets_attached_to_neighbor"})
                orphans = []
            out.append(unit)
        return out

    # 6. loại ngữ nghĩa -----------------------------------------------------------------------------
    def _retype(self, unit: Unit) -> None:
        target = "table" if unit.table is not None else unit.chunk_type
        if target not in ("figure", "overview", "table"):
            return
        captions = [e.text or "" for e in unit.elements if e.normalized_type == "caption"]
        title = " | ".join([unit.section_path[-1] if unit.section_path else "", unit.label or "", *captions])
        for rule in self.cfg.chunk_type_rules:
            if target not in rule.applies_to:
                continue
            if (rule.title and re.search(rule.title, title)) or (rule.content and re.search(rule.content,
                                                                                            unit.content)):
                unit.chunk_type = rule.chunk_type
                return

    # 7. cửa sổ cha ---------------------------------------------------------------------------------
    def _windows(self, path: tuple[str, ...], units: list[Unit]) -> list[Window]:
        windows: list[Window] = []
        for unit in units:
            if unit.table is not None:
                windows.append(Window(path, [unit]))
                continue
            last = windows[-1] if windows else None
            if (last is not None and last.units[-1].table is None
                    and len("\n\n".join([u.content for u in last.units] + [unit.content])) <= self.cfg.parent_max):
                last.units.append(unit)
            else:
                windows.append(Window(path, [unit]))
        return windows

    def plan(self) -> ChunkPlan:
        windows: list[Window] = []
        for path, blocks in self._sections(self._flow()):
            units = self._section_units(path, blocks)
            for unit in units:
                self._retype(unit)
            windows.extend(self._windows(path, units))
        return ChunkPlan(windows, self.excluded, self.heading_only)
