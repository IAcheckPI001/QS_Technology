"""crm-sync (sources/crm): đọc cây CRM, chọn tài liệu, so sổ nguồn, tải PDF + manifest nháp. Không cần mạng."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.modules.doc_ingest import cli
from app.modules.doc_ingest.manifest import load_manifest
from app.modules.doc_ingest.sources.crm.client import CrmError
from app.modules.doc_ingest.sources.crm.commands import run_fetch, run_plan
from app.modules.doc_ingest.sources.crm.config import load_config, registry_models
from app.modules.doc_ingest.sources.crm.diff import classify, plan
from app.modules.doc_ingest.sources.crm.lock import LockEntry, SourceLock, load_lock
from app.modules.doc_ingest.sources.crm.tree import Selected, documents, file_id, parse_version, select

FIXTURE = Path(__file__).parent / "fixtures" / "crm" / "website_tree.json"
CONFIG = load_config()


def _tree() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _docs(tree: dict | None = None):
    return documents(tree or _tree())


def _by_name(docs, name):
    return next(d for d in docs if d.name == name)


def test_version_and_file_id() -> None:
    assert parse_version("1.0") == parse_version("1") == (1,)
    assert parse_version("1.10") > parse_version("1.9")
    assert parse_version("1.0a") is None and parse_version("") is None and parse_version(None) is None
    assert file_id("/api/v1/public/company-docs/x/files/8ab7f88d-1690.pdf?exp=1&sig=2") == "8ab7f88d-1690"
    assert file_id(None) is None


def test_documents_keep_path_and_metadata() -> None:
    doc = _by_name(_docs(), "F54 - Installation Guide")
    assert doc.path == ("Bộ điều khiển", "F54") and doc.branch == "Bộ điều khiển" and doc.folder == "F54"
    assert doc.version == "1.0" and doc.language == "en" and doc.document_type == "installation"
    assert doc.connection_types == ["Pulse Train"] and doc.file_id and doc.file_size


def test_select_one_per_model_and_type_prefer_en() -> None:
    selection = select(_docs(), CONFIG, registry_models())
    ids = [s.doc_id for s in selection.selected]
    assert ids == sorted([
        "10iv-operation-en", "6ah-operation-en", "6ave-installation-vi", "6ave-operation-en",
        "f10t-installation-vi", "f10t-operation-vi", "f54-installation-en", "f54-operation-en",
        "f86-installation-en", "f86-operation-en", "qs-catalogue", "qs-company-profile"])
    # 6AVE: Installation (vi) và Operation (en) chung document_group_id nhưng khác loại → lấy cả hai
    skipped = {s.doc.name: s.reason for s in selection.skipped}
    assert set(skipped) == {"F54 - Hướng dẫn lắp đặt", "F86 - Hướng dẫn lắp đặt", "F86 - Hướng dẫn vận hành"}
    assert all("đã chọn bản en" in r for r in skipped.values())
    assert selection.out_of_scope == 1                              # tài liệu Servo
    run_only = {s.doc_id: s for s in selection.selected if s.mode == "run_only"}
    assert set(run_only) == {"qs-catalogue", "qs-company-profile"} and not run_only["qs-catalogue"].require_version


def test_select_rejects_unknown_model_and_folder_mismatch() -> None:
    tree = _tree()
    controllers = next(c for c in tree["children"] if c["name"] == "Bộ điều khiển")
    f54 = next(c for c in controllers["children"] if c["name"] == "F54")
    odd = copy.deepcopy(f54["children"][0])
    odd.update(id="x1", name="Z99 - Operation Guide")
    moved = copy.deepcopy(f54["children"][0])
    moved.update(id="x2", name="F86 - Installation Guide")               # tài liệu F86 nằm trong thư mục F54
    f54["children"] += [odd, moved]
    reasons = {s.doc.crm_id: s.reason for s in select(_docs(tree), CONFIG, registry_models()).skipped}
    assert "không nhận ra model" in reasons["x1"]
    assert "tên thư mục 'F54' khác cấu hình 'F86'" in reasons["x2"]


def _entry(doc, doc_id="f54-installation-en", **kw) -> LockEntry:
    base = dict(crm_id=doc.crm_id, doc_id=doc_id, name=doc.name, branch=doc.branch, mode="build", model="F54",
                document_type=doc.document_type, language=doc.language, version=doc.version,
                file_id=doc.file_id, sha256="0" * 64, state="fetched", pdf_path="data/x.pdf", synced_at="2026-11-19")
    base.update(kw)
    return LockEntry(**base)


@pytest.mark.parametrize(("version", "file_changed", "locked", "expected"), [
    ("1.0", False, None, "new"),
    ("1.1", True, "1.0", "updated"),
    ("1.0", True, "1.0", "anomaly"),
    ("1.0", False, "1.0", "unchanged"),
    ("1.1", False, "1.0", "version_only"),
    ("1.0", True, "1.1", "anomaly"),
    ("v1", False, "1.0", "anomaly"),
])
def test_classify_rules(version, file_changed, locked, expected) -> None:
    doc = copy.copy(_by_name(_docs(), "F54 - Installation Guide"))
    entry = _entry(doc, version=locked) if locked else None
    doc.version = version
    if file_changed:
        doc.file_id = "new-file"
    status, _ = classify(Selected(doc, "f54-installation-en", "build", True, "F54", "installation"), entry)
    assert status == expected


def test_run_only_compares_file_id_and_removed_documents() -> None:
    docs = _docs()
    cat = copy.copy(_by_name(docs, "Catalogue sản phẩm"))
    entry = _entry(cat, "qs-catalogue", mode="run_only", model=None, version="1")
    assert classify(Selected(cat, "qs-catalogue", "run_only", False), entry)[0] == "unchanged"
    cat.file_id = "changed"
    assert classify(Selected(cat, "qs-catalogue", "run_only", False), entry)[0] == "updated"
    gone = _entry(_by_name(docs, "F54 - Installation Guide"), crm_id="deleted-id")
    items = plan(select(docs, CONFIG, registry_models()), docs, SourceLock(source="x", documents=[gone]))
    assert [i.doc_id for i in items if i.status == "removed"] == ["f54-installation-en"]


PDF = b"%PDF-1.7\n" + b"x" * 100


class FakeCrm:
    """Fetcher giả: trả cây fixture (kích thước file sửa cho khớp PDF giả) và PDF giả cho mọi URL tải."""

    def __init__(self, body: bytes = PDF) -> None:
        self.tree = _tree()
        self.body = body
        self.urls: list[str] = []

        def fix(node):
            if node.get("node_type") == "document":
                node["file_size"] = len(body)
            for c in node.get("children") or []:
                fix(c)

        fix(self.tree)

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url == CONFIG.api_url:
            return json.dumps(self.tree).encode("utf-8")
        return self.body


def _plan(tmp_path: Path, fake: FakeCrm) -> Path:
    return run_plan(CONFIG, fake, tmp_path / "lock.json", tmp_path / "sync")


def test_plan_writes_report_without_signed_urls(tmp_path: Path) -> None:
    out = _plan(tmp_path, FakeCrm())
    items = json.loads((out / "plan.json").read_text(encoding="utf-8"))["items"]
    assert sum(i["status"] == "new" for i in items) == 12
    assert sum(i["status"] == "skipped" for i in items) == 3
    snapshot = (out / "tree.json").read_text(encoding="utf-8")
    assert "sig=" not in snapshot and "exp=" not in snapshot
    assert "Mới (12)" in (out / "plan.md").read_text(encoding="utf-8")


def test_fetch_downloads_writes_manifest_and_lock(tmp_path: Path) -> None:
    fake = FakeCrm()
    out = _plan(tmp_path, fake)
    lock_path, manifests = tmp_path / "lock.json", tmp_path / "manifests"
    manifests.mkdir()
    errors = run_fetch(CONFIG, fake, out, lock_path=lock_path, sources_dir=tmp_path / "src",
                       manifests_dir=manifests, today="2026-11-19")
    assert errors == []
    lock = load_lock(lock_path, CONFIG.api_url)
    assert len(lock.documents) == 12 and all(e.state == "fetched" for e in lock.documents)
    raw = lock_path.read_text(encoding="utf-8")
    assert "sig=" not in raw and "exp=" not in raw and "http" not in raw.replace(CONFIG.api_url, "")
    manifest = load_manifest(manifests / "f54-installation-en.yaml")
    assert manifest.doc_type == "installation_manual" and manifest.product_models == ["F54"]
    assert manifest.lang == "en" and manifest.doc_version == "1.0" and manifest.source is not None
    assert manifest.source.crm_id == lock.by_crm_id()[manifest.source.crm_id].crm_id
    assert manifest.storage_bucket == "f54-docs" and manifest.run_doc_ids == ["f54-installation-en"]
    op = load_manifest(manifests / "f86-operation-en.yaml")
    assert op.doc_type == "user_guide" and op.default_scopes == ["operation"] and op.scope_rules
    assert not (manifests / "qs-catalogue.yaml").exists()            # run_only: không sinh manifest
    assert all(u.startswith(CONFIG.base_url) for u in fake.urls if u != CONFIG.api_url)
    # chạy lại plan ngay sau → không còn gì mới
    again = json.loads((run_plan(CONFIG, fake, lock_path, tmp_path / "sync2") / "plan.json").read_text("utf-8"))
    assert {i["status"] for i in again["items"]} == {"unchanged", "skipped"}


def test_fetch_keeps_human_fields_on_update(tmp_path: Path) -> None:
    fake = FakeCrm()
    lock_path, manifests = tmp_path / "lock.json", tmp_path / "manifests"
    manifests.mkdir()
    run_fetch(CONFIG, fake, _plan(tmp_path, fake), lock_path=lock_path, sources_dir=tmp_path / "src",
              manifests_dir=manifests, only=["f54-installation-en"], today="2026-11-19")
    path = manifests / "f54-installation-en.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("exclude_pages: []", "exclude_pages:\n- 1\n- 2"),
                    encoding="utf-8")
    doc = next(n for n in fake.tree["children"][1]["children"][4]["children"] if n["name"] == "F54 - Installation Guide")
    doc["version"], doc["file_url"] = "1.1", doc["file_url"].replace("/files/", "/files/new-")
    out = run_plan(CONFIG, fake, lock_path, tmp_path / "sync2")
    items = {i["doc_id"]: i for i in json.loads((out / "plan.json").read_text("utf-8"))["items"]}
    assert items["f54-installation-en"]["status"] == "updated"
    run_fetch(CONFIG, fake, out, lock_path=lock_path, sources_dir=tmp_path / "src", manifests_dir=manifests,
              only=["f54-installation-en"], today="2026-11-20")
    manifest = load_manifest(path)
    assert manifest.doc_version == "1.1" and manifest.exclude_pages == [1, 2]


def test_fetch_rejects_non_pdf_and_size_mismatch(tmp_path: Path) -> None:
    html = FakeCrm(b"<html>login</html>")
    errors = run_fetch(CONFIG, html, _plan(tmp_path, html), lock_path=tmp_path / "lock.json",
                       sources_dir=tmp_path / "src", manifests_dir=tmp_path, only=["f54-installation-en"])
    assert len(errors) == 1 and "không phải PDF" in errors[0]
    assert not (tmp_path / "lock.json").exists()

    fake = FakeCrm()
    out = _plan(tmp_path / "b", fake)
    fake.body = PDF + b"extra"
    errors = run_fetch(CONFIG, fake, out, lock_path=tmp_path / "b" / "lock.json", sources_dir=tmp_path / "src",
                       manifests_dir=tmp_path, only=["f54-installation-en"])
    assert "khác file_size" in errors[0]


def test_fetch_stops_when_crm_changed_after_plan(tmp_path: Path) -> None:
    fake = FakeCrm()
    out = _plan(tmp_path, fake)
    for node in fake.tree["children"][1]["children"][4]["children"]:
        node["version"] = "2.0"
    errors = run_fetch(CONFIG, fake, out, lock_path=tmp_path / "lock.json", sources_dir=tmp_path / "src",
                       manifests_dir=tmp_path, only=["f54-installation-en"])
    assert "CRM đã đổi sau lúc plan" in errors[0]
    with pytest.raises(CrmError):
        run_fetch(CONFIG, fake, out, lock_path=tmp_path / "lock.json", sources_dir=tmp_path / "src",
                  manifests_dir=tmp_path, only=["khong-co"])


def test_cli_parses_crm_commands() -> None:
    args = cli._parser().parse_args(["crm-fetch", "--plan", "x", "--only", "a", "b"])
    assert args.command == "crm-fetch" and args.only == ["a", "b"]
    assert cli._parser().parse_args(["crm-plan"]).command == "crm-plan"
