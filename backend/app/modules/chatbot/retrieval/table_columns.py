"""Cắt cột model không được hỏi khỏi bảng markdown trong chunk (câu so sánh).

Bảng chọn model của catalog có một cột cho mỗi model (F54 | F86 | F10T | ASTRO-10S). Khi so sánh
hai model, các cột thừa làm LLM gán nhầm cột (kiểm thật 2026-11-20: giá trị cột F54 bị ghi cho F86).
Cột được coi là cột model khi tiêu đề chỉ ra đúng một model của registry (mã hoặc alias, vd
"ASTRO-10S" → 10S); cột khác (tên thuộc tính, đơn vị) luôn giữ. Bảng không có cột nào của model
được hỏi thì giữ nguyên. Hàm thuần, áp được cho mọi tài liệu (không dựa vào tên tài liệu).
"""

from collections.abc import Callable, Collection

HeaderModels = Callable[[str], list[str]]


def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _column_model(cell: str, header_models: HeaderModels) -> str | None:
    models = header_models(cell)
    if len(models) == 1:
        return models[0]
    exact = [model for model in models if model.casefold() == cell.replace(" ", "").casefold()]
    return exact[0] if len(exact) == 1 else None


def _trim_table(lines: list[str], keep: Collection[str], header_models: HeaderModels) -> list[str]:
    header = _cells(lines[0])
    models = [_column_model(cell, header_models) for cell in header]
    if not any(model in keep for model in models if model):
        return lines
    keep_index = [index for index, model in enumerate(models) if model is None or model in keep]
    if len(keep_index) == len(header):
        return lines
    trimmed = []
    for line in lines:
        cells = _cells(line)
        if len(cells) != len(header):
            return lines                 # bảng lệch số cột: không đoán, giữ nguyên
        trimmed.append("| " + " | ".join(cells[index] for index in keep_index) + " |")
    return trimmed


def trim_model_columns(content: str, keep: Collection[str], header_models: HeaderModels) -> str:
    """Bỏ cột của model không thuộc `keep` trong mọi bảng markdown của `content`."""
    if "|" not in content or not keep:
        return content
    out: list[str] = []
    table: list[str] = []

    def flush() -> None:
        if len(table) >= 2:
            out.extend(_trim_table(table, keep, header_models))
        else:
            out.extend(table)
        table.clear()

    for line in content.split("\n"):
        if line.lstrip().startswith("|"):
            table.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


__all__ = ["trim_model_columns"]
