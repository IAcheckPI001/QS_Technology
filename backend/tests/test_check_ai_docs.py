from pathlib import Path

from scripts.check_ai_docs import check, rule_paths

STATE_OK = "# Trạng thái\n\nCập nhật: 2026-11-11\n"
LOG_OK = "# Nhật ký\n\n## 2026-11-11 · b · loại: thay đổi\n\n## 2026-11-10 · a · loại: thay đổi\n"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    _write(tmp_path, "AGENTS.md", "# A\n\n[x](docs/ai/flows/x/README.md)\n")
    _write(tmp_path, "docs/ai/flows/x/README.md", "# X\n\n[state](STATE.md)\n")
    _write(tmp_path, "docs/ai/flows/x/STATE.md", STATE_OK)
    _write(tmp_path, "docs/ai/flows/x/LOG.md", LOG_OK)
    _write(tmp_path, "docs/ai/flows/_template/README.md", "# Mẫu, không phải luồng: không cần STATE/LOG\n")
    _write(tmp_path, "backend/app/a.py", "")
    _write(tmp_path, ".claude/rules/x.md", '---\npaths:\n  - "backend/app/**"\n---\n\n# X\n')
    return tmp_path


def _messages(root: Path) -> list[str]:
    return [str(p) for p in check(root)]


def test_valid_repo_passes(tmp_path):
    assert _messages(_repo(tmp_path)) == []


def test_broken_link_is_reported_but_links_in_code_are_ignored(tmp_path):
    root = _repo(tmp_path)
    _write(root, "docs/ai/note.md", "[ok](flows/x/STATE.md) [bad](nope.md#a) `[code](nope2.md)`\n```\n[f](nope3.md)\n```\n")
    assert _messages(root) == ["docs/ai/note.md: liên kết hỏng: nope.md#a"]


def test_external_and_anchor_links_are_skipped(tmp_path):
    root = _repo(tmp_path)
    _write(root, "docs/ai/note.md", "[w](https://example.com) [a](#top) [m](mailto:x@y.z)\n")
    assert _messages(root) == []


def test_worktrees_are_not_checked(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".claude/worktrees/w/docs/ai/bad.md", "[bad](nope.md)\n")
    assert _messages(root) == []


def test_flow_missing_file_and_limits(tmp_path):
    root = _repo(tmp_path)
    (root / "docs/ai/flows/x/LOG.md").unlink()
    _write(root, "docs/ai/flows/x/STATE.md", "# S\n" + "x\n" * 80)
    _write(root, "docs/ai/flows/x/README.md", "x\n" * 201)
    assert sorted(_messages(root)) == [
        "docs/ai/flows/x/README.md: 201 dòng, giới hạn 200",
        "docs/ai/flows/x/STATE.md: 81 dòng, giới hạn 80",
        "docs/ai/flows/x/STATE.md: thiếu dòng 'Cập nhật: YYYY-MM-DD'",
        "docs/ai/flows/x: thiếu LOG.md",
    ]


def test_log_must_be_newest_first(tmp_path):
    root = _repo(tmp_path)
    _write(root, "docs/ai/flows/x/LOG.md", "## 2026-11-09 · a · loại: x\n\n## 2026-11-11 · b · loại: x\n")
    assert _messages(root) == [
        "docs/ai/flows/x/LOG.md: mục 2026-11-11 nằm dưới mục cũ hơn 2026-11-09: mục mới nhất phải ở trên",
    ]


def test_agents_limit_and_missing(tmp_path):
    root = _repo(tmp_path)
    _write(root, "AGENTS.md", "x\n" * 121)
    assert _messages(root) == ["AGENTS.md: 121 dòng, giới hạn 120"]
    (root / "AGENTS.md").unlink()
    assert _messages(root) == ["AGENTS.md: không tồn tại"]


def test_rule_paths_must_match(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".claude/rules/y.md", '---\npaths:\n  - "backend/nope/**"\n---\n')
    _write(root, ".claude/rules/z.md", "# no frontmatter\n")
    assert sorted(_messages(root)) == [
        ".claude/rules/y.md: paths không khớp file nào: backend/nope/**",
        ".claude/rules/z.md: không có frontmatter paths:",
    ]


def test_rule_paths_parses_only_paths_key():
    text = '---\nother:\n  - "a"\npaths:\n  - "b/**"\n  - "c.py"\n---\n  - "d"\n'
    assert rule_paths(text) == ["b/**", "c.py"]


def test_current_repository_docs_pass():
    root = Path(__file__).resolve().parents[2]
    assert [str(p) for p in check(root)] == []
