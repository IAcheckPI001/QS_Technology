"""Kiểm cấu trúc tài liệu cho AI agent (AGENTS.md, docs/ai/, .claude/rules/).

Chỉ dùng thư viện chuẩn, không cần venv. Kiểm:
- liên kết tương đối trong file Markdown trỏ tới file/thư mục có thật;
- mỗi luồng trong `docs/ai/flows/` (trừ `_template`) có đủ README.md, STATE.md, LOG.md;
- giới hạn dòng: AGENTS.md ≤ 120, README.md ≤ 200, STATE.md ≤ 80 của luồng;
- STATE.md có dòng `Cập nhật: YYYY-MM-DD`;
- mục trong LOG.md (`## YYYY-MM-DD · …`) xếp mới nhất ở trên;
- mỗi đường dẫn trong frontmatter `paths:` của `.claude/rules/*.md` khớp ít nhất một file.

Chạy từ thư mục backend (hoặc truyền gốc repo):

    .\\venv\\Scripts\\python.exe scripts\\check_ai_docs.py [gốc repo]

Exit code 1 khi có lỗi; mỗi lỗi in một dòng `đường/dẫn: mô tả`.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

AGENTS_MAX_LINES = 120
README_MAX_LINES = 200
STATE_MAX_LINES = 80
FLOW_FILES = ("README.md", "STATE.md", "LOG.md")

# Thư mục không phải tài liệu chuẩn: bản sao repo, output sinh tự động.
SKIP_PARTS = frozenset({".claude/worktrees", "docs/ai/doc_ingest_spike", "node_modules"})

_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_UPDATED = re.compile(r"^Cập nhật: \d{4}-\d{2}-\d{2}\b", re.MULTILINE)
_LOG_ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2}) ·", re.MULTILINE)
_RULE_PATH = re.compile(r'^\s+-\s+"([^"]+)"\s*$')


@dataclass(frozen=True)
class Problem:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _skipped(root: Path, path: Path) -> bool:
    rel = _rel(root, path)
    return any(rel == part or rel.startswith(part + "/") for part in SKIP_PARTS)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> int:
    return len(_read(path).splitlines())


def _without_code(text: str) -> str:
    """Bỏ khối code rào và code inline để không kiểm liên kết nằm trong ví dụ."""
    kept: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept)


def markdown_files(root: Path) -> list[Path]:
    files = [root / name for name in ("AGENTS.md", "CLAUDE.md") if (root / name).is_file()]
    for base in (root / "docs" / "ai", root / ".claude" / "rules", root / ".github"):
        if base.is_dir():
            files.extend(p for p in sorted(base.rglob("*.md")) if not _skipped(root, p))
    return files


def check_links(root: Path, path: Path) -> list[Problem]:
    problems = []
    for target in _LINK.findall(_without_code(_read(path))):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
            continue
        file_part = unquote(target.split("#", 1)[0])
        if file_part and not (path.parent / file_part).exists():
            problems.append(Problem(_rel(root, path), f"liên kết hỏng: {target}"))
    return problems


def check_flow(root: Path, flow_dir: Path) -> list[Problem]:
    problems = []
    rel = _rel(root, flow_dir)
    for name in FLOW_FILES:
        if not (flow_dir / name).is_file():
            problems.append(Problem(rel, f"thiếu {name}"))
    readme, state, log = (flow_dir / name for name in FLOW_FILES)
    if readme.is_file() and (n := _lines(readme)) > README_MAX_LINES:
        problems.append(Problem(_rel(root, readme), f"{n} dòng, giới hạn {README_MAX_LINES}"))
    if state.is_file():
        if (n := _lines(state)) > STATE_MAX_LINES:
            problems.append(Problem(_rel(root, state), f"{n} dòng, giới hạn {STATE_MAX_LINES}"))
        if not _UPDATED.search(_read(state)):
            problems.append(Problem(_rel(root, state), "thiếu dòng 'Cập nhật: YYYY-MM-DD'"))
    if log.is_file():
        dates = _LOG_ENTRY.findall(_without_code(_read(log)))
        for newer, older in zip(dates, dates[1:]):
            if newer < older:
                problems.append(Problem(
                    _rel(root, log), f"mục {older} nằm dưới mục cũ hơn {newer}: mục mới nhất phải ở trên",
                ))
                break
    return problems


def rule_paths(text: str) -> list[str]:
    """Đường dẫn trong frontmatter `paths:` của một rule."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    paths: list[str] = []
    in_paths = False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if re.match(r"^\S", line):
            in_paths = line.strip() == "paths:"
            continue
        if in_paths and (match := _RULE_PATH.match(line)):
            paths.append(match.group(1))
    return paths


def check_rules(root: Path) -> list[Problem]:
    problems = []
    rules_dir = root / ".claude" / "rules"
    if not rules_dir.is_dir():
        return problems
    for rule in sorted(rules_dir.glob("*.md")):
        paths = rule_paths(_read(rule))
        if not paths:
            problems.append(Problem(_rel(root, rule), "không có frontmatter paths:"))
        for pattern in paths:
            if not any(p for p in root.glob(pattern) if not _skipped(root, p)):
                problems.append(Problem(_rel(root, rule), f"paths không khớp file nào: {pattern}"))
    return problems


def check(root: Path) -> list[Problem]:
    problems: list[Problem] = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        problems.append(Problem("AGENTS.md", "không tồn tại"))
    elif (n := _lines(agents)) > AGENTS_MAX_LINES:
        problems.append(Problem("AGENTS.md", f"{n} dòng, giới hạn {AGENTS_MAX_LINES}"))
    for path in markdown_files(root):
        problems.extend(check_links(root, path))
    flows = root / "docs" / "ai" / "flows"
    if flows.is_dir():
        for flow_dir in sorted(p for p in flows.iterdir() if p.is_dir() and not p.name.startswith("_")):
            problems.extend(check_flow(root, flow_dir))
    problems.extend(check_rules(root))
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[2]
    problems = check(root)
    for problem in problems:
        print(problem)
    print(f"check_ai_docs: {len(problems)} lỗi" if problems else "check_ai_docs: đạt")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
