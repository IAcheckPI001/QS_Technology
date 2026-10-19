"""Sinh embedding_text cho một chunk. Hàm thuần: cùng input → cùng output → hash ổn định.

Khác display_text: embedding_text tối ưu cho tìm kiếm (mở rộng alias từ registry, nêu rõ loại
tri thức và mã), bỏ đi phần không mang ngữ nghĩa truy vấn (evidence, basis, ID nội bộ).
"""
from __future__ import annotations

from ..schemas.knowledge_record import KnowledgeRecord
from ..schemas.registry import RegistrySnapshot

TYPE_LABEL_VI = {
    "wiring": "Hướng dẫn đấu dây",
    "procedure": "Quy trình thao tác",
    "parameter_config": "Cấu hình tham số",
    "troubleshooting": "Xử lý lỗi",
    "spec_fact": "Thông số kỹ thuật",
}


def _with_aliases(reg: RegistrySnapshot, fld: str, codes: list[str]) -> str:
    parts = []
    for c in codes:
        al = reg.aliases_of(fld, c)
        parts.append(f"{c} ({', '.join(al)})" if al else c)
    return ", ".join(parts)


def build_embedding_text(record: KnowledgeRecord, section_body: str, models: list[str],
                         reg: RegistrySnapshot) -> str:
    c = record.classification
    lines = [f"{TYPE_LABEL_VI[record.content.kind]}: {record.title}"]
    lines.append(f"Model: {_with_aliases(reg, 'product_models', models)}" if models
                 else "Model: chưa xác định")
    for label, fld, codes in (("Mã lỗi", "alarm_codes", c.alarm_codes),
                              ("Tham số", "parameter_ids", c.parameter_ids),
                              ("Cổng kết nối", "connector_ids", c.connector_ids),
                              ("Giao tiếp", "control_interface", c.control_interface)):
        if codes:
            lines.append(f"{label}: {_with_aliases(reg, fld, codes)}")
    lines.append(record.summary)
    lines.append(section_body)
    return "\n".join(lines)
