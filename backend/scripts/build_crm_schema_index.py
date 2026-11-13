"""Sinh `app/modules/chatbot/reporting/raw/schema_index.py` từ pg_dump schema của CRM.

Đọc `CREATE TABLE public.*` (cột, kiểu, CHECK `= ANY (ARRAY[...])`), `CREATE TYPE ... AS ENUM`
và `FOREIGN KEY (...) REFERENCES` của file dump; không kết nối database hay CRM. Bỏ cột `bytea`
(Reporting API không cho truy vấn dữ liệu nhị phân).

Chạy từ thư mục backend sau khi cập nhật dump:

    .\\venv\\Scripts\\python.exe scripts\\build_crm_schema_index.py [đường dẫn dump]

Mặc định đọc `../docs/ai/tool_instruction/database-structure.sql`.
"""

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.chatbot.reporting.raw.schema import compact_type  # noqa: E402

DEFAULT_DUMP = BACKEND.parent / "docs" / "ai" / "tool_instruction" / "database-structure.sql"
OUTPUT = BACKEND / "app" / "modules" / "chatbot" / "reporting" / "raw" / "schema_index.py"

_TABLE = re.compile(r"^CREATE TABLE public\.(\w+) \($")
_COLUMN = re.compile(r'^\s+"?(\w+)"? (.+?),?$')     # tên trùng từ khoá SQL bị đặt trong ""
_ENUM = re.compile(r"^CREATE TYPE public\.(\w+) AS ENUM \($")
_ALTER = re.compile(r"^ALTER TABLE ONLY public\.(\w+)$")
_FOREIGN_KEY = re.compile(r"FOREIGN KEY \((\w+)\) REFERENCES public\.(\w+)\((\w+)\)")
_ANY_ARRAY = re.compile(r"(\w+)\)?(?:::[\w ]+)?\s*=\s*ANY\s*\(\(?ARRAY\[([^\]]*)\]")
_QUOTED = re.compile(r"'([^']*)'")
_TYPE_END = re.compile(r"\s+(?:DEFAULT|NOT NULL|NULL|GENERATED|COLLATE)\b")
_STARTED = re.compile(r"^-- Started on (.+)$")


def parse(text: str) -> tuple[dict[str, dict], str]:
    lines = text.splitlines()
    enums: dict[str, tuple[str, ...]] = {}
    started = "?"
    for index, line in enumerate(lines):
        if match := _STARTED.match(line):
            started = match.group(1).strip()
        if match := _ENUM.match(line):
            values: list[str] = []
            for item in lines[index + 1:]:
                if item.startswith(");"):
                    break
                values += _QUOTED.findall(item)
            enums[match.group(1)] = tuple(values)

    tables: dict[str, dict] = {}
    index = 0
    while index < len(lines):
        match = _TABLE.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        columns: dict[str, str] = {}
        values: dict[str, tuple[str, ...]] = {}
        index += 1
        while not lines[index].startswith(");"):
            line = lines[index]
            stripped = line.strip()
            if stripped.startswith("CONSTRAINT"):
                for column, items in _ANY_ARRAY.findall(stripped):
                    if column in columns:
                        values[column] = tuple(_QUOTED.findall(items))
            elif column := _COLUMN.match(line):
                raw_type = _TYPE_END.split(column.group(2), maxsplit=1)[0].rstrip(",").strip()
                if raw_type == "bytea":
                    index += 1          # dữ liệu nhị phân: Reporting API không cho truy vấn
                    continue
                columns[column.group(1)] = compact_type(raw_type, enums)
                enum_name = raw_type.removeprefix("public.")
                if raw_type.startswith("public.") and enum_name in enums:
                    values[column.group(1)] = enums[enum_name]
            index += 1
        tables[name] = {"columns": columns, "relations": {}, "values": values}

    for index, line in enumerate(lines):
        match = _ALTER.match(line)
        if not match or index + 1 >= len(lines):
            continue
        foreign = _FOREIGN_KEY.search(lines[index + 1])
        table = tables.get(match.group(1))
        if foreign and table is not None:
            # Kể cả khoá ngoại không trỏ vào `id` (vd iot_firmware_updates.device_id → iot_devices.device_id):
            # CRM cũng công bố chúng trong relations.
            table["relations"][foreign.group(1)] = foreign.group(2)
    return tables, started


def _wrap(items: list[str], indent: str, width: int = 100) -> str:
    """Các phần tử `"k": v` nối bằng dấu phẩy, xuống dòng khi vượt `width`."""
    lines: list[str] = []
    current = indent
    for item in items:
        piece = f"{item}, "
        if len(current) + len(piece) > width and current.strip():
            lines.append(current.rstrip())
            current = indent
        current += piece
    if current.strip():
        lines.append(current.rstrip())
    return "\n".join(lines)


def _mapping(name: str, mapping: dict[str, object]) -> str:
    if not mapping:
        return f"        {name}={{}},"
    items = [f'"{key}": {_literal(value)}' for key, value in mapping.items()]
    return f"        {name}={{\n{_wrap(items, ' ' * 12)}\n        }},"


def _literal(value: object) -> str:
    if isinstance(value, tuple):
        inner = ", ".join(f'"{item}"' for item in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    return f'"{value}"'


def render(tables: dict[str, dict], started: str, source: str) -> str:
    parts = [
        '"""Index schema CRM, SINH TỰ ĐỘNG: không sửa tay.',
        "",
        f"Nguồn: {source} (pg_dump, started on {started}).",
        "Sinh lại: `.\\\\venv\\\\Scripts\\\\python.exe scripts\\\\build_crm_schema_index.py` (thư mục backend).",
        '"""',
        "",
        "from .schema import TableIndex",
        "",
        "TABLES: dict[str, TableIndex] = {",
    ]
    for name in sorted(tables):
        table = tables[name]
        parts += [
            f'    "{name}": TableIndex(',
            _mapping("columns", table["columns"]),
            _mapping("relations", table["relations"]),
            _mapping("values", table["values"]),
            "    ),",
        ]
    parts.append("}")
    return "\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    dump = Path(argv[0]) if argv else DEFAULT_DUMP
    tables, started = parse(dump.read_text(encoding="utf-8"))
    try:
        source = dump.resolve().relative_to(BACKEND.parent).as_posix()
    except ValueError:
        source = dump.name
    OUTPUT.write_text(render(tables, started, source), encoding="utf-8")
    relations = sum(len(table["relations"]) for table in tables.values())
    with_values = sum(len(table["values"]) for table in tables.values())
    print(f"{len(tables)} bảng, {relations} khoá ngoại, {with_values} cột có giá trị liệt kê -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
