"""Vòng đời knowledge unit và approval gate (D-08; pattern `learning_ai/review/lifecycle.py`,
viết riêng, không import chéo).

- Hai trục trạng thái: version document × unit. Chỉ phục vụ khi document `active` và unit
  `approved` (H-3).
- Unit không được duyệt khi còn mục review blocking (H-1) hoặc thiếu reviewer (H-9).
- Approval gắn `content_hash` + `evidence_hash`; chạy lại không đổi thì giữ (khớp theo id,
  id đổi thì khớp theo hash), đổi thì về `pending_review` (H-6). Hash profile không tham
  gia; `evidence_hash` không được chứa `logical_table_id`/`row_id`.
- Duyệt hàng loạt theo section chỉ nhận unit rủi ro thấp, không cờ (H-8). Không tự xuất bản.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.modules.doc_ingest.schemas.normalized import LogicalTable, ReviewItem
from app.modules.doc_ingest.schemas.review import (ApprovalRecord, DocState, KnowledgeUnit, RiskTier,
                                                   UnitState)

U = UnitState
TRANSITIONS: dict[UnitState, frozenset[UnitState]] = {
    U.DRAFT: frozenset({U.PENDING_REVIEW, U.CONFLICT}),
    U.PENDING_REVIEW: frozenset({U.APPROVED, U.REJECTED, U.DRAFT, U.CONFLICT}),
    U.APPROVED: frozenset({U.PENDING_REVIEW}),          # nội dung đổi khi chạy lại
    U.REJECTED: frozenset({U.PENDING_REVIEW}),          # parse lại sau khi sửa luật
    U.CONFLICT: frozenset({U.PENDING_REVIEW, U.REJECTED}),
}


class TransitionError(Exception):
    pass


def content_hash(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def table_unit_payload(table: LogicalTable) -> dict[str, object]:
    """Nội dung của unit bảng logic: chữ và cấu trúc, không gồm bbox/id (bbox dịch nhẹ
    khi parse lại không làm mất approval)."""
    return {
        "columns": [c.header_text for c in table.columns],
        "rows": [
            {"is_header": r.is_header, "repeated_header": r.repeated_header,
             "cells": [c.text for c in r.cells],
             "applicability_candidates": [a.model_dump(mode="json") for a in r.applicability_candidates]}
            for r in table.rows
        ],
    }


def open_blocking(review: Iterable[ReviewItem], targets: Iterable[str]) -> list[ReviewItem]:
    """Mục blocking có `target` hoặc `element_id` thuộc unit: trùng id hoặc là id con
    (`f54:t004` chứa `f54:t004:r22`)."""
    ids = tuple(targets)

    def belongs(value: str | None) -> bool:
        return value is not None and any(value == i or value.startswith(f"{i}:") for i in ids)

    return [item for item in review if item.blocking and (belongs(item.target) or belongs(item.element_id))]


def is_served(doc_state: DocState, unit_state: UnitState) -> bool:
    return doc_state == DocState.ACTIVE and unit_state == UnitState.APPROVED


def transition(unit: KnowledgeUnit, to: UnitState, *, actor: str,
               blocking: Sequence[ReviewItem] = (), mode: str = "single",
               now: datetime | None = None) -> tuple[KnowledgeUnit, ApprovalRecord | None]:
    if to not in TRANSITIONS[unit.state]:
        raise TransitionError(f"{unit.state.value} → {to.value} không hợp lệ")
    record = None
    if to == U.APPROVED:
        if not actor.strip() or actor.startswith("system:"):
            raise TransitionError("chỉ người có tên (reviewer) được duyệt unit")
        if blocking:
            raise TransitionError(f"còn {len(blocking)} mục review blocking: "
                                  + ", ".join(item.code for item in blocking))
        record = ApprovalRecord(unit_id=unit.unit_id, unit_type=unit.unit_type, reviewer=actor, approved_at=now or datetime.now(timezone.utc),
                                unit_content_hash=unit.content_hash, evidence_hash=unit.evidence_hash, mode=mode)
    return unit.model_copy(update={"state": to}), record


CarryReason = Literal["id", "hash", "hash_changed", "ambiguous", "new"]


@dataclass
class CarryOverResult:
    units: list[KnowledgeUnit]
    reasons: dict[str, CarryReason]          # unit_id -> lý do
    matched_records: dict[str, str]          # unit_id -> unit_id của bản ghi approval đã dùng


def _key(unit_type: str, content: str, evidence: str) -> tuple[str, str, str]:
    return unit_type, content, evidence


def carry_over(units: Sequence[KnowledgeUnit], previous: Iterable[ApprovalRecord]) -> CarryOverResult:
    """H-6: giữ approval của lần chạy trước khi nội dung không đổi, kể cả khi id đổi.

    1. Có bản ghi cùng `unit_id`: cùng `(unit_type, content_hash, evidence_hash)` →
       `approved` (`id`), khác → `pending_review` (`hash_changed`).
    2. Không có bản ghi cùng id: đúng một bản ghi chưa dùng cùng `(unit_type,
       content_hash, evidence_hash)` và đúng một unit cần nó → `approved` (`hash`); nhiều
       bên → `pending_review` (`ambiguous`); không có → giữ nguyên trạng thái (`new`).
    Mỗi bản ghi chỉ cấp cho một unit. Hai bảng đổi chỗ cho nhau (id hoán đổi) rơi vào
    `hash_changed`, tức về duyệt lại — hướng an toàn.
    """
    records = list(previous)
    by_id = {r.unit_id: r for r in records}
    used: set[str] = set()
    reasons: dict[str, CarryReason] = {}
    matched: dict[str, str] = {}
    states: dict[str, UnitState] = {}

    for unit in units:
        record = by_id.get(unit.unit_id)
        if record is None:
            continue
        used.add(record.unit_id)
        if _key(record.unit_type, record.unit_content_hash, record.evidence_hash) == _key(
                unit.unit_type, unit.content_hash, unit.evidence_hash):
            reasons[unit.unit_id], matched[unit.unit_id], states[unit.unit_id] = "id", record.unit_id, U.APPROVED
        else:
            reasons[unit.unit_id], states[unit.unit_id] = "hash_changed", U.PENDING_REVIEW

    need: dict[tuple[str, str, str], list[KnowledgeUnit]] = {}
    for unit in units:
        if unit.unit_id not in reasons:
            need.setdefault(_key(unit.unit_type, unit.content_hash, unit.evidence_hash), []).append(unit)
    for key, wanting in need.items():
        offers = [r for r in records if r.unit_id not in used
                  and _key(r.unit_type, r.unit_content_hash, r.evidence_hash) == key]
        if len(offers) == 1 and len(wanting) == 1:
            used.add(offers[0].unit_id)
            unit = wanting[0]
            reasons[unit.unit_id], matched[unit.unit_id], states[unit.unit_id] = "hash", offers[0].unit_id, U.APPROVED
        else:
            for unit in wanting:
                reasons[unit.unit_id] = "ambiguous" if offers else "new"
                if offers:
                    states[unit.unit_id] = U.PENDING_REVIEW

    result = [u.model_copy(update={"state": states[u.unit_id]}) if u.unit_id in states else u for u in units]
    return CarryOverResult(units=result, reasons=reasons, matched_records=matched)


@dataclass
class BulkResult:
    units: list[KnowledgeUnit]
    records: list[ApprovalRecord] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)


def bulk_approve_section(units: Sequence[KnowledgeUnit], section_prefix: Sequence[str], *, actor: str,
                         review: Sequence[ReviewItem] = (), now: datetime | None = None) -> BulkResult:
    """H-8: duyệt hàng loạt unit `pending_review` trong một section; unit rủi ro cao hoặc
    còn mục blocking bị từ chối kèm lý do."""
    prefix = list(section_prefix)
    result = BulkResult(units=[])
    for unit in units:
        in_section = unit.section_path[:len(prefix)] == prefix
        if not in_section or unit.state != U.PENDING_REVIEW:
            result.units.append(unit)
            continue
        if unit.risk_tier == RiskTier.HIGH:
            result.refused[unit.unit_id] = "high_risk"
            result.units.append(unit)
            continue
        blocking = open_blocking(review, [unit.unit_id])
        if blocking:
            result.refused[unit.unit_id] = "blocking_review_item"
            result.units.append(unit)
            continue
        approved, record = transition(unit, U.APPROVED, actor=actor, mode="bulk_section", now=now)
        assert record is not None
        result.units.append(approved)
        result.records.append(record)
    return result


def publishable(units: Sequence[KnowledgeUnit], doc_state: DocState) -> list[str]:
    """Unit được đưa vào gói xuất bản: đang phục vụ được, mọi phụ thuộc cũng phục vụ được
    (H-4), không nằm trong conflict group chưa giải quyết (H-5)."""
    by_id = {u.unit_id: u for u in units}
    open_groups = {u.conflict_group for u in units if u.conflict_group and u.state == U.CONFLICT}

    def ok(unit: KnowledgeUnit) -> bool:
        if not is_served(doc_state, unit.state) or unit.conflict_group in open_groups:
            return False
        return all(dep in by_id and is_served(doc_state, by_id[dep].state) for dep in unit.depends_on)

    return [u.unit_id for u in units if ok(u)]
