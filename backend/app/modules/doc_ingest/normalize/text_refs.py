"""T-12, T-13 trên text và T-08 v1.1 (contract T-12, T-13, T-08; sửa 2026-11-09).

Chạy sau T-08. Phạm vi: phần tử body có text (đoạn, list, heading, caption, footnote);
không quét furniture, chữ trong hình (`figure_text`), mục lục, bảng (bảng có luật riêng ở
`normalize/tables.py`). Chỉ gắn **ứng viên** (mã + vị trí + vai trò, cụm điều kiện áp dụng);
fact được trích ở BL-17.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.doc_ingest.normalize.docling_reader import RawItem
from app.modules.doc_ingest.normalize.lists import ListRun
from app.modules.doc_ingest.normalize.recorder import Recorder
from app.modules.doc_ingest.schemas.normalized import ApplicabilityCandidate
from app.modules.doc_ingest.schemas.profile import Profile
from app.modules.doc_ingest.technical_refs.applicability import detect_applicability
from app.modules.doc_ingest.technical_refs.params import TextParamRef, find_param_refs

_TEXT_LABELS = frozenset({"text", "list_item", "section_header", "title", "caption", "footnote"})


@dataclass
class TextRefRun:
    param_refs: dict[str, list[TextParamRef]] = field(default_factory=dict)
    applicability: dict[str, list[ApplicabilityCandidate]] = field(default_factory=dict)
    near_miss: Counter[str] = field(default_factory=Counter)
    unparseable: int = 0
    list_mismatch: int = 0


def _in_scope(item: RawItem, skip: frozenset[str]) -> bool:
    if item.is_furniture or item.element_id in skip or not item.text or item.label not in _TEXT_LABELS:
        return False
    # Phần tử con của picture/table: chỉ caption được quét (chữ OCR, nhãn T-18 là figure_text).
    return item.parent_id is None or item.label == "caption"


def annotate_text(items: Sequence[RawItem], lists: ListRun, profile: Profile, rec: Recorder,
                  skip: frozenset[str] = frozenset()) -> TextRefRun:
    run = TextRefRun()
    max_len = profile.thresholds.max_range_len
    for item in items:
        if not _in_scope(item, skip):
            continue
        scan = find_param_refs(item.text, profile.param_prefixes, profile.param_text_patterns, max_len)
        run.near_miss.update(scan.near_miss)
        if scan.refs:
            run.param_refs[item.element_id] = scan.refs
            rec.add_log("T-12", item.element_id, "mã parameter trong text",
                        after={"refs": [f"{r.label} ({r.role})" for r in scan.refs]})
        for label, error in scan.errors:
            run.unparseable += 1
            rec.add_review(item.element_id, "param_unparseable", f"{label!r}: {error}")
        for label in scan.too_long:
            rec.add_review(item.element_id, "range_too_long", label)
        for match in detect_applicability(item.text, profile):
            run.applicability.setdefault(item.element_id, []).append(match.candidate)
            rec.add_review(item.element_id, "applicability_note", match.candidate.note)
            if match.unmatched:
                rec.add_review(item.element_id, "applicability_model_unmatched",
                               f"condition {match.candidate.condition_text!r} matches no model "
                               "or interface in the registry",
                               suggested_action="confirm which models the condition covers")
    _list_mismatch(lists, run, rec)
    return run


def _list_mismatch(lists: ListRun, run: TextRefRun, rec: Recorder) -> None:
    """T-08 v1.1: cha định nghĩa mã (`M1951:`), con là định nghĩa/giá trị của mã khác cùng
    prefix (`o M1950 = 0`) → `list_param_mismatch`. Không đoán mã nào đúng (F54 trang 96 là
    lỗi soạn thảo của chính tài liệu)."""
    for element_id, info in lists.info.items():
        parent = info.parent_element_id
        if parent is None:
            continue
        defined = [r for r in run.param_refs.get(parent, []) if r.role == "definition"]
        own = [r for r in run.param_refs.get(element_id, []) if r.role in ("definition", "value_option")]
        for child_ref in own:
            same_prefix = [d for d in defined if d.prefix == child_ref.prefix]
            if same_prefix and not any(set(d.codes) & set(child_ref.codes) for d in same_prefix):
                run.list_mismatch += 1
                rec.add_review(element_id, "list_param_mismatch",
                               f"list con nói về {child_ref.label} nhưng cha định nghĩa "
                               f"{', '.join(d.label for d in same_prefix)}", target=parent,
                               suggested_action="Xác nhận mã đúng (lỗi soạn thảo của tài liệu?)")
                break
