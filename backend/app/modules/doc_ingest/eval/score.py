"""B3 — chấm điểm một thư mục chạy theo bộ nhãn tay mẫu (2026-11-09).

Tách số liệu trang có text layer và trang OCR (theo S0). Cổng đạt (B4) chỉ áp cho trang có
text layer; trang OCR chỉ báo cáo (đã có `ocr_required` chặn chunk).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.modules.doc_ingest.eval.labels import DocLabels, EvalReport, GateCheck, GroupScore, LabelPage, Metric
from app.modules.doc_ingest.schemas.normalized import LogicalTable, NormalizedElement
from app.modules.doc_ingest.schemas.run import RunReport

_BODY_TYPES = frozenset({"text", "list_item", "heading", "label_heading", "caption", "warning"})

# B4: ngưỡng cổng trên trang có text layer
T12_PRECISION_MIN = 0.99
T12_RECALL_MIN = 0.95
ROLE_ACCURACY_MIN = 0.95
CONTENT_MIN = 0.95
OCR_SHARE_MAX = 0.5      # tài liệu chủ yếu OCR: chưa đủ điều kiện (V-01 không đo được, ocr_required chặn chunk)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def _finish(m: Metric) -> Metric:
    return m.model_copy(update={"precision": _ratio(m.tp, m.tp + m.fp), "recall": _ratio(m.tp, m.tp + m.fn)})


class RunData:
    def __init__(self, run_dir: Path) -> None:
        self.report = RunReport.model_validate_json((run_dir / "run_report.json").read_text(encoding="utf-8"))
        norm = run_dir / "normalized"
        self.elements = [NormalizedElement.model_validate_json(line)
                         for line in (norm / "elements.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.tables = [LogicalTable.model_validate_json(line)
                       for line in (norm / "tables.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.by_id = {e.element_id: e for e in self.elements}
        pages = self.report.s0.pages if self.report.s0 is not None else []
        self.ocr_pages = {p.page for p in pages if p.ocr}

    def page_elements(self, page: int) -> list[NormalizedElement]:
        return [e for e in self.elements if e.pdf_page_index == page]

    def table_notes(self, page: int) -> list[str]:
        notes = []
        for table in self.tables:
            for row in table.rows:
                if table.segments[row.segment].pdf_page_index == page:
                    notes += [c.note for c in row.applicability_candidates]
        return notes

    def table_text(self, page: int) -> list[str]:
        return [c.text for t in self.tables for r in t.rows if t.segments[r.segment].pdf_page_index == page
                for c in r.cells if c.text]


def _score_page(data: RunData, label: LabelPage, group: GroupScore, details: dict[str, list[str]],
                role_hits: list[int]) -> None:
    page = label.page
    elements = data.page_elements(page)
    body = [e for e in elements if e.content_layer == "body" and e.normalized_type in _BODY_TYPES]

    # T-12: so theo (prefix, codes, kind); vai trò so trên các cặp khớp
    predicted = Counter((r.prefix, tuple(r.codes), r.kind) for e in body for r in e.param_refs)
    predicted_roles = Counter((r.prefix, tuple(r.codes), r.kind, r.role) for e in body for r in e.param_refs)
    gold = Counter((g.prefix, g.all_codes(), g.kind) for g in label.param_refs)
    gold_roles = Counter((g.prefix, g.all_codes(), g.kind, g.role) for g in label.param_refs)
    tp = sum((predicted & gold).values())
    group.t12.tp += tp
    group.t12.fp += sum((predicted - gold).values())
    group.t12.fn += sum((gold - predicted).values())
    role_hits[0] += sum((predicted_roles & gold_roles).values())
    role_hits[1] += tp
    labels = {(g.prefix, g.all_codes(), g.kind): g.label for g in label.param_refs}
    details["t12_fp"] += [f"p{page} {p}{list(c)[:3]}{'…' if len(c) > 3 else ''} ({k})"
                          for (p, c, k) in (predicted - gold).elements()]
    details["t12_fn"] += [f"p{page} {labels[key]}" for key in (gold - predicted).elements()]
    for key in (predicted_roles - gold_roles).elements():
        if (key[0], key[1], key[2]) in gold:
            details["t12_role"].append(f"p{page} {labels[(key[0], key[1], key[2])]}: dự đoán {key[3]}")

    # T-08: mục con theo đầu text
    items = [e for e in elements if e.list_info is not None]
    for rel in label.list_children:
        child = next((e for e in items if _norm(e.text or "").startswith(_norm(rel.child))), None)
        info = child.list_info if child is not None else None
        parent = data.by_id.get(info.parent_element_id) if info and info.parent_element_id else None
        if parent is not None and _norm(parent.text or "").startswith(_norm(rel.parent)):
            group.t08_correct += 1
        elif parent is None:
            group.t08_missing += 1
            details["t08"].append(f"p{page} '{rel.child}': không có cha (mong đợi '{rel.parent}')")
        else:
            group.t08_wrong += 1
            details["t08"].append(f"p{page} '{rel.child}': cha '{(parent.text or '')[:40]}' (mong đợi '{rel.parent}')")

    # T-13: cụm áp dụng trên text và bảng của trang
    notes = [_norm(c.note) for e in body for c in e.applicability_candidates] + [_norm(n) for n in data.table_notes(page)]
    used: set[int] = set()
    for want in label.applicability:
        hit = next((i for i, n in enumerate(notes) if i not in used and (_norm(want) in n or n in _norm(want))), None)
        if hit is None:
            group.t13.fn += 1
            details["t13_fn"].append(f"p{page} {want}")
        else:
            used.add(hit)
            group.t13.tp += 1
    group.t13.fp += len(notes) - len(used)

    # Nội dung thân: câu mẫu phải nằm trong text thân hoặc ô bảng (không tính chữ trong hình)
    haystack = _norm(" ".join([e.text or "" for e in body] + data.table_text(page)))
    for snippet in label.body_snippets:
        group.content_total += 1
        if _norm(snippet) in haystack:
            group.content_found += 1
        else:
            details["content_missing"].append(f"p{page} {snippet[:60]}")


def score_run(run_dir: Path, labels: DocLabels) -> EvalReport:
    data = RunData(run_dir)
    groups = {"text_layer": GroupScore(), "ocr": GroupScore()}
    roles = {"text_layer": [0, 0], "ocr": [0, 0]}
    details: dict[str, list[str]] = {k: [] for k in ("t12_fp", "t12_fn", "t12_role", "t08", "t13_fn", "content_missing")}
    selected = set(data.report.pages_selected)
    for page_label in labels.pages:
        if page_label.page not in selected:
            continue
        key = "ocr" if page_label.page in data.ocr_pages else "text_layer"
        groups[key].pages.append(page_label.page)
        _score_page(data, page_label, groups[key], details, roles[key])
    for key, group in groups.items():
        group.t12 = _finish(group.t12)
        group.t13 = _finish(group.t13)
        group.t12_role_accuracy = _ratio(*roles[key])
    s0_pages = data.report.s0.pages if data.report.s0 is not None else []
    ocr_share = _ratio(sum(1 for p in s0_pages if p.ocr), len(s0_pages))
    gate = _gate(groups["text_layer"], ocr_share)
    decided = [c.passed for c in gate if c.passed is not None]
    return EvalReport(doc_id=labels.doc_id, run_id=data.report.run_id, labels_verified=labels.verified,
                      provisional=not labels.verified, groups=groups, gate=gate,
                      gate_passed=all(decided) if decided else None,
                      details={k: v for k, v in details.items() if v})


def _check(name: str, value: float | int | None, threshold: str, ok: bool | None) -> GateCheck:
    return GateCheck(name=name, value=value, threshold=threshold, passed=None if value is None else ok)


def _gate(g: GroupScore, ocr_share: float | None) -> list[GateCheck]:
    t08_total = g.t08_correct + g.t08_wrong + g.t08_missing
    content = _ratio(g.content_found, g.content_total)
    return [
        _check("Tỷ lệ trang OCR của tài liệu", ocr_share, f"<= {OCR_SHARE_MAX}",
               ocr_share is not None and ocr_share <= OCR_SHARE_MAX),
        _check("T-12 precision", g.t12.precision, f">= {T12_PRECISION_MIN}",
               g.t12.precision is not None and g.t12.precision >= T12_PRECISION_MIN),
        _check("T-12 recall", g.t12.recall, f">= {T12_RECALL_MIN}",
               g.t12.recall is not None and g.t12.recall >= T12_RECALL_MIN),
        _check("T-12 vai trò đúng", g.t12_role_accuracy, f">= {ROLE_ACCURACY_MIN}",
               g.t12_role_accuracy is not None and g.t12_role_accuracy >= ROLE_ACCURACY_MIN),
        _check("T-08 cha sai", g.t08_wrong if t08_total else None, "= 0", g.t08_wrong == 0),
        _check("T-13 recall", g.t13.recall, "= 1.0", g.t13.recall == 1.0),
        _check("Nội dung thân giữ lại", content, f">= {CONTENT_MIN}", content is not None and content >= CONTENT_MIN),
    ]


def load_labels(path: Path) -> DocLabels:
    return DocLabels.model_validate(json.loads(path.read_text(encoding="utf-8")))
