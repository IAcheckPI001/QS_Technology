"""Cấu hình crm-sync (`crm.yaml`) và danh sách model của registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.modules.doc_ingest.schemas.manifest import Scope, ScopeRule

CRM_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CRM_DIR / "crm.yaml"
LOCK_FILE = CRM_DIR / "crm_sources.lock.json"
REPO_ROOT = Path(__file__).resolve().parents[6]
SYNC_DIR = REPO_ROOT / "data" / "crm_sync"
SOURCES_DIR = REPO_ROOT / "data" / "crm_sources"
REGISTRY_SNAPSHOT = CRM_DIR.parents[1] / "profiles" / "registry_snapshot.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Branch(_Strict):
    name: str
    mode: Literal["build", "run_only"]
    require_version: bool


class ModelRule(_Strict):
    prefix: str
    model: str
    folder: str


class DocTypeRule(_Strict):
    slug: str
    doc_type: Literal["user_guide", "installation_manual"]
    default_scopes: list[Scope] = Field(min_length=1)
    scope_rules: list[ScopeRule] = Field(default_factory=list)


class CrmConfig(_Strict):
    api_url: str
    base_url: str
    user_agent: str
    timeout_s: float = 60
    profile: str
    language_priority: list[str] = Field(min_length=1)
    branches: list[Branch] = Field(min_length=1)
    models: list[ModelRule] = Field(default_factory=list)
    document_types: dict[str, DocTypeRule] = Field(default_factory=dict)
    run_only_doc_ids: dict[str, str] = Field(default_factory=dict)


def load_config(path: Path = CONFIG_FILE) -> CrmConfig:
    return CrmConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def registry_models(path: Path = REGISTRY_SNAPSHOT) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["product_models"])
