


"""Sinh Chunk từ KnowledgeRecord đã duyệt, theo chiến lược riêng cho từng knowledge_type.

Bất biến:
  1. Record vừa ngân sách → đúng 1 chunk (section='full').
  2. Không bao giờ cắt giữa: các bước cùng phase, các bước có depends_on, một cặp nguyên nhân–xử lý.
  3. Mọi chunk đều mang header: tiêu đề, phạm vi model, điều kiện, điều kiện tiên quyết,
     và các cảnh báo an toàn liên quan (DANGER hoặc cảnh báo không gắn bước → lặp ở MỌI chunk).
  4. Đơn vị không thể chia vượt ngân sách → giữ nguyên (thà dài còn hơn sai) và đánh dấu oversize.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas.common import ApplicabilityScope
from ..schemas.content import (ParameterConfigContent, ProcedureContent, SafetyWarning, Severity,
                               SpecFactContent, TroubleshootingContent, WiringContent)
from ..schemas.derived import CHUNK_BUILDER_VERSION, Chunk, ChunkFilters
from ..schemas.knowledge_record import KnowledgeRecord
from ..schemas.registry import RegistrySnapshot
from .embedding_text_builder import build_embedding_text

DEFAULT_MAX_CHARS = 1800


@dataclass
class _Draft:
    section: str
    body: str
    steps: set[int] | None = None      # bước thuộc chunk (để chọn cảnh báo)
    oversize: bool = False


# ---------------- render ----------------
def _render_step(s) -> str:
    out = f"{s.step_no}. {s.action}"
    if s.expected_result:
        out += f" → Kết quả mong đợi: {s.expected_result}"
    return out


def _render_cause(i: int, c) -> str:
    lines = [f"Nguyên nhân {i + 1}: {c.cause}"]
    lines += [f"  - Kiểm tra: {x}" for x in c.diagnostic_checks]
    lines += [f"  - Xử lý: {x}" for x in c.resolution_steps]
    return "\n".join(lines)


def _full_body(ct) -> str:
    if isinstance(ct, ProcedureContent):
        body = "\n".join(_render_step(s) for s in ct.steps)
        return body + (f"\nKiểm tra hoàn tất: {ct.completion_check}" if ct.completion_check else "")
    if isinstance(ct, ParameterConfigContent):
        rows = [f"- {s.parameter_id} = {s.value}{' ' + s.unit if s.unit else ''}"
                f"{f' (khi {s.condition})' if s.condition else ''}" for s in ct.settings]
        if ct.apply_method:
            rows.append(f"Áp dụng: {ct.apply_method}")
        rows += [f"Lưu ý: {x}" for x in ct.side_effects]
        return "\n".join(rows)
    if isinstance(ct, WiringContent):
        rows = [f"- {w.from_connector}{':' + w.from_pin if w.from_pin else ''} → {w.to_target}"
                f"{':' + w.to_pin if w.to_pin else ''}{f' [{w.signal}]' if w.signal else ''}"
                f"{f' ({w.note})' if w.note else ''}" for w in ct.connections]
        rows += [f"Kiểm tra: {v}" for v in ct.verification]
        return "\n".join(rows)
    if isinstance(ct, TroubleshootingContent):
        return "\n".join(_render_cause(i, c) for i, c in enumerate(ct.causes))
    if isinstance(ct, SpecFactContent):
        return "\n".join(f"- {f.spec_attribute}: {f.value}{' ' + f.unit if f.unit else ''}"
                         f"{f' ({f.condition})' if f.condition else ''}" for f in ct.facts)
    raise TypeError(type(ct))


# ---------------- tách theo loại ----------------
def _procedure_units(ct: ProcedureContent) -> list[tuple[int, int]]:
    """Gộp các khoảng bước không được tách: cùng phase hoặc có depends_on. Trả về [(lo, hi)]."""
    spans = [(min([s.step_no, *s.depends_on]), s.step_no) for s in ct.steps]
    phases: dict[str, list[int]] = {}
    for s in ct.steps:
        if s.phase:
            phases.setdefault(s.phase, []).append(s.step_no)
    spans += [(min(v), max(v)) for v in phases.values()]
    spans.sort()
    merged: list[list[int]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    # bảo đảm phủ kín 1..n theo thứ tự
    return [(lo, hi) for lo, hi in merged]


def _pack(units: list[_Draft], max_chars: int) -> list[_Draft]:
    out: list[_Draft] = []
    for u in units:
        if out and len(out[-1].body) + len(u.body) + 1 <= max_chars:
            last = out[-1]
            last.body += "\n" + u.body
            last.section = _merge_section(last.section, u.section)
            if last.steps is not None and u.steps is not None:
                last.steps |= u.steps
        else:
            u.oversize = len(u.body) > max_chars
            out.append(u)
    return out


def _merge_section(a: str, b: str) -> str:
    ka, va = a.split(":", 1)
    _, vb = b.split(":", 1)
    if ka == "steps":
        return f"steps:{va.split('-')[0]}-{vb.split('-')[-1]}"
    return f"{ka}:{va}+{vb}"


def _split(ct, max_chars: int) -> list[_Draft]:
    if isinstance(ct, ProcedureContent):
        by_no = {s.step_no: s for s in ct.steps}
        units = [_Draft(f"steps:{lo}-{hi}", "\n".join(_render_step(by_no[n]) for n in range(lo, hi + 1)),
                        steps=set(range(lo, hi + 1))) for lo, hi in _procedure_units(ct)]
        packed = _pack(units, max_chars)
        if ct.completion_check:
            packed[-1].body += f"\nKiểm tra hoàn tất: {ct.completion_check}"
        return packed
    if isinstance(ct, TroubleshootingContent):
        return [_Draft(f"cause:{i + 1}", _render_cause(i, c)) for i, c in enumerate(ct.causes)]
    if isinstance(ct, WiringContent):
        groups: dict[str, list] = {}
        for w in ct.connections:
            groups.setdefault(w.from_connector, []).append(w)
        units = [_Draft(f"connector:{k}", _full_body(ct.model_copy(update={"connections": v, "verification": []})))
                 for k, v in groups.items()]
        return _pack(units, max_chars)
    # parameter_config / spec_fact: thường gọn; nếu dài thì tách theo từng dòng giá trị
    rows = _full_body(ct).split("\n")
    return _pack([_Draft(f"rows:{i}", r) for i, r in enumerate(rows)], max_chars)


# ---------------- header ----------------
def _models_for_filter(record: KnowledgeRecord, reg: RegistrySnapshot) -> list[str]:
    a = record.applicability
    if a.scope == ApplicabilityScope.MODEL_FAMILY:
        return sorted(reg.models_of_family(a.model_family or "") - set(a.excluded_models))
    return sorted(a.product_models)


def _scope_line(record: KnowledgeRecord, models: list[str]) -> str:
    a = record.applicability
    if a.scope == ApplicabilityScope.UNDETERMINED:
        s = "Phạm vi: CHƯA XÁC ĐỊNH model — chỉ tham khảo"
    elif a.scope == ApplicabilityScope.ALL_MODELS:
        s = "Phạm vi: mọi model" + (f" trừ {', '.join(a.excluded_models)}" if a.excluded_models else "")
    else:
        s = f"Phạm vi: chỉ áp dụng cho {', '.join(models)}"
    if a.firmware:
        s += f"; firmware {a.firmware}"
    if a.conditions:
        s += f"; điều kiện: {'; '.join(a.conditions)}"
    return s


def _warnings_for(ct, steps: set[int] | None) -> list[SafetyWarning]:
    ws: list[SafetyWarning] = getattr(ct, "safety_warnings", [])
    return [w for w in ws if w.severity == Severity.DANGER or not w.applies_to_steps
            or steps is None or set(w.applies_to_steps) & steps]


def _header(record: KnowledgeRecord, models: list[str], steps: set[int] | None, part: str) -> str:
    ct = record.content
    lines = [f"{record.title}{part}", _scope_line(record, models)]
    if isinstance(ct, TroubleshootingContent):
        codes = f" [{', '.join(ct.symptom.alarm_codes)}]" if ct.symptom.alarm_codes else ""
        lines.append(f"Triệu chứng{codes}: {ct.symptom.description}")
    pre = getattr(ct, "prerequisites", [])
    if pre:
        lines.append("Điều kiện tiên quyết: " + "; ".join(p.text for p in pre))
    for w in _warnings_for(ct, steps):
        lines.append(f"⚠ {w.severity.value.upper()}: {w.text}")
    return "\n".join(lines)


# ---------------- entrypoint ----------------
def build_chunks(record: KnowledgeRecord, reg: RegistrySnapshot,
                 max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    ct = record.content
    full = _full_body(ct)
    drafts = [_Draft("full", full)] if len(full) <= max_chars else _split(ct, max_chars)

    models = _models_for_filter(record, reg)
    c, a = record.classification, record.applicability
    filters = ChunkFilters(
        knowledge_type=ct.kind, intents=c.intents, topic=c.topic, scope=a.scope, product_models=models,
        excluded_models=a.excluded_models, control_interface=c.control_interface,
        spec_attribute=c.spec_attribute, connector_ids=c.connector_ids, parameter_ids=c.parameter_ids,
        alarm_codes=c.alarm_codes, registry_version=record.provenance.registry_version)

    n, chash = len(drafts), record.content_hash()
    ids = [Chunk.make_id(record.revision_id, d.section) for d in drafts]
    chunks = []
    for i, d in enumerate(drafts):
        part = "" if n == 1 else f" (phần {i + 1}/{n})"
        display = _header(record, models, d.steps, part) + "\n" + d.body
        emb = build_embedding_text(record, d.body, models, reg)
        chunks.append(Chunk(
            chunk_id=ids[i], record_id=record.record_id, revision_id=record.revision_id,
            record_version=record.versioning.version, record_content_hash=chash,
            builder_version=CHUNK_BUILDER_VERSION, chunk_index=i, chunk_count=n, section=d.section,
            display_text=display, embedding_text=emb, embedding_text_hash=Chunk.hash_text(emb),
            filters=filters, prev_chunk_id=ids[i - 1] if i else None,
            next_chunk_id=ids[i + 1] if i + 1 < n else None))
    return chunks