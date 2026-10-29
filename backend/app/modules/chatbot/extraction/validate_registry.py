
import re
from typing import Any
import difflib

from app.modules.chatbot.extraction.registry import (MAX_SUB_QUERIES, MAX_CANDIDATES, DOMAINS, FUZZY_CUTOFF, MODEL_POLICIES, MODEL_SPECIFIC_PATTERN, NO_TARGET_ROUTES, SCOPES, REGISTRY as R)

def _norm(s: Any) -> str:
    """Không phân biệt hoa/thường, khoảng trắng, gạch ngang/gạch dưới."""
    return re.sub(r"[\s_\-]+", "", str(s).lower())
 
 
def _build_maps() -> tuple[dict[str, str], dict[str, list[str]]]:
    alias_map = {_norm(m): m for m in R["product_models"]}
    alias_map.update({_norm(a): m for a, m in R["aliases"].items()})
    ambiguous_map = {_norm(a): c for a, c in R["ambiguous_aliases"].items()}
    return alias_map, ambiguous_map
 
 
_ALIAS, _AMBIG = _build_maps()
 
 
def _covered(domain: str) -> set[str] | None:
    cov = R["coverage"].get(domain)
    if cov is None:
        return None
    return set(cov)            # list hoặc dict đều lấy được tập model
 
 
def _covered_interfaces(domain: str, model: str) -> list[str] | None:
    cov = R["coverage"].get(domain)
    if isinstance(cov, dict):
        return cov.get(model)
    return None                # không giới hạn theo interface
 
 
def validate_registry() -> None:
    """[C9] Chạy khi import. Dùng exception để không bị tắt bởi `python -O`."""
    def check(cond: bool, msg: str) -> None:
        if not cond:
            raise RegistryError(msg)
 
    models = set(R["product_models"])
    for name, spec in R["intents"].items():
        check(spec["model_policy"] in MODEL_POLICIES, f"{name}: model_policy sai")
        check(isinstance(spec.get("allow_general", True), bool), f"{name}: allow_general phải là bool")
        all_t = spec["targets"] + spec.get("fallback_targets", []) + spec.get("degrade_to", [])
        for t in all_t:
            check(t["domain"] in DOMAINS, f"{name}: domain lạ {t}")
            check(set(t.get("scopes", [])) <= set(SCOPES), f"{name}: scope lạ {t}")
        if spec["targets"]:
            check("route" not in spec, f"{name}: intent có targets không được khai báo route")
        else:
            check(spec.get("route") in NO_TARGET_ROUTES, f"{name}: thiếu route hợp lệ")
    check(set(R["aliases"].values()) <= models, "alias trỏ tới model không tồn tại")
    for cands in R["ambiguous_aliases"].values():
        check(set(cands) <= models, "ambiguous alias trỏ tới model không tồn tại")
    check(not set(_ALIAS) & set(_AMBIG), "alias trùng với alias mơ hồ")
    for dom, cov in R["coverage"].items():
        check(dom in DOMAINS, f"coverage domain lạ: {dom}")
        if cov is not None:
            check(set(cov) <= models, f"coverage {dom} có model lạ")
        if isinstance(cov, dict):
            for m, ifs in cov.items():
                check(set(ifs) <= set(R["control_interface"]), f"coverage {dom}/{m} interface lạ")
 
def handoff_config(reason: str) -> dict:
    cfg = REGISTRY["handoff_reasons"][reason]
    return {"reason": reason, "queue": cfg["queue"], "mode": cfg["mode"]}
 
validate_registry()

def display_name(model: str) -> str:
    """ASTRO_10S -> 'Astro 10S' ; F86 -> 'F86' (dùng cho câu hỏi/nút bấm)."""
    if "_" not in model:
        return model
    fam, rest = model.split("_", 1)
    return f"{fam.capitalize()} {rest}"


def suggest_models(mention: str, limit: int = MAX_CANDIDATES) -> list[str]:
    """[C1] Gợi ý model gần đúng cho cụm không khớp (gõ sai, thiếu hậu tố...).
    Chỉ so với model cùng chữ cái đầu để tránh gợi ý vô lý (F58 -> ASTRO_*)."""
    k = _norm(mention)
    if not k:
        return []
    pool = {a: m for a, m in _ALIAS.items() if a[:1] == k[:1]}
 
    def prefix(a: str) -> int:
        n = 0
        while n < min(len(a), len(k)) and a[n] == k[n]:
            n += 1
        return n
 
    # Mã model thường sai ở ký tự cuối (F58 vs F54) -> ưu tiên trùng tiền tố, rồi mới tới độ giống
    scored = [(prefix(a), difflib.SequenceMatcher(None, k, a).ratio(), a) for a in pool]
    hits = [a for p, r, a in sorted(scored, reverse=True) if r >= FUZZY_CUTOFF]
    out: list[str] = []
    for h in hits:
        if pool[h] not in out:
            out.append(pool[h])
    return out[:limit]
 
 
def resolve_models(names: list[str]) -> tuple[list[str], list[str], list[str]]:
    """-> (models canonical, cụm mơ hồ, cụm không có trong danh mục)."""
    models: list[str] = []
    ambiguous: list[str] = []
    unknown: list[str] = []
    for n in names:
        k = _norm(n)
        if not k:
            continue
        if k in _ALIAS:
            if _ALIAS[k] not in models:
                models.append(_ALIAS[k])
        elif k in _AMBIG:
            if n not in ambiguous:
                ambiguous.append(n)
        elif n not in unknown:
            unknown.append(n)
    return models, ambiguous, unknown
 
 
def _covered_models(targets: list[dict]) -> list[str]:
    """Model có tài liệu ở ít nhất một domain đích, theo thứ tự registry (gợi ý khi thiếu model)."""
    covered: set[str] = set()
    for t in targets:
        cov = _covered(t["domain"])
        if cov is None:
            return list(R["product_models"])
        covered |= cov
    return [m for m in R["product_models"] if m in covered]


def _model_keys(model: str) -> set[str]:
    return {_norm(model)} | {_norm(a) for a, m in R["aliases"].items() if m == model}


def guard_extracted_models(raw_sub_queries: list[dict], evidence_text: str) -> list[dict]:
    """[C10] Không để LLM âm thầm đổi model (vd. người dùng gõ F84, LLM ghi F86).

    product_models là enum trong schema strict nên LLM có thể chọn model hợp lệ
    gần giống. Chỉ giữ model có mã hoặc alias xuất hiện trong câu hỏi, lịch sử
    hay last_models; model bị loại được ghi vào `dropped_models`.
    """
    evidence = _norm(evidence_text)
    guarded: list[dict] = []
    for sq in raw_sub_queries:
        kept, dropped = [], []
        for model in sq.get("product_models") or []:
            ok = model not in R["product_models"] or any(k in evidence for k in _model_keys(model))
            (kept if ok else dropped).append(model)
        guarded.append({**sq, "product_models": kept, "dropped_models": dropped} if dropped else sq)
    return guarded


def _supported(models: list[str], targets: list[dict]) -> tuple[list[str], list[str]]:
    """Chia model theo coverage của các domain đích."""
    if not targets:
        return list(models), []
    supported, unsupported = [], []
    for m in models:
        ok = any((c := _covered(t["domain"])) is None or m in c for t in targets)
        (supported if ok else unsupported).append(m)
    return supported, unsupported


# ----------------------------------------------------- resolve sub_query (code)
def resolve_sub_query(
    sq: dict,
    idx: int = 0,
    *,
    last_models: list[str] | tuple = (),
    active_model: str | None = None,
) -> dict:
    intent = sq.get("intent")
    if intent not in R["intents"]:
        return _unclear(sq.get("standalone_query") or "", idx)
    spec = R["intents"][intent]
    policy = spec["model_policy"]
    need = spec.get("min_models", 1)
    warnings: list[str] = [f"model_not_in_text:{m}" for m in sq.get("dropped_models") or []]

    # 1. Chuẩn hóa model (LLM có thể đặt alias/chuỗi lạ ở cả hai trường)
    names = list(sq.get("product_models") or []) + list(sq.get("unresolved_mentions") or [])
    models, ambiguous, unknown = resolve_models(names)
    candidates = {m: _AMBIG[_norm(m)] for m in ambiguous}
    candidates.update({m: suggest_models(m) for m in unknown})          # [C1]

    # 1b. Thiếu model ở câu cần đúng một model [C11]:
    #   câu hỏi chung (nguyên lý, khái niệm) -> trả lời tổng quan rồi hỏi model ở cuối;
    #   câu phụ thuộc model: có active_model (model của lượt gần nhất) -> kế thừa;
    #   last_models có đúng 1 model -> kế thừa model đó;
    #   last_models có >= 2 model -> xung đột ngữ cảnh, hỏi chọn trong last_models.
    # Cờ "general" của LLM chỉ được nhận khi intent cho phép và câu không nhắc mã
    # cụ thể (CN1, #4130...): LLM có thể phân loại sai, nhất là câu không phải tiếng Việt.
    general = False
    single_model_needed = policy == "required" and need == 1 and not (models or ambiguous or unknown)
    if single_model_needed:
        if (
            sq.get("model_dependency") == "general"
            and spec.get("allow_general", True)
            and not MODEL_SPECIFIC_PATTERN.search(sq.get("standalone_query") or "")
        ):
            general = True
        elif active_model or len(last_models) == 1:
            inherited = active_model or last_models[0]
            models = [inherited]
            warnings.append(f"inherited_model:{inherited}")

    # 2. product_scope_mode
    if intent == "compare.product_models":
        mode = "comparison"
    elif not spec["targets"] or intent == "lookup.company_info":
        mode = "unspecified"
    elif len(models) == 1:
        mode = "single"
    elif len(models) >= 2:
        mode = "multiple"
    else:
        mode = "unspecified"
 
    # 3. Clarification
    reason = None
    if policy != "none":
        conflict = bool(sq.get("history_conflict")) or (
            single_model_needed and not general and len(last_models) >= 2
        )
        checks = {
            "ambiguous_product_model": bool(ambiguous),
            "unknown_product_model": bool(unknown),
            "context_conflict": conflict and not models,
            "insufficient_models_for_comparison": policy == "required" and need > 1 and len(models) < need,
            "missing_product_model": policy == "required" and need == 1 and not models,
        }
        reason = next((r for r in R["clarification_order"] if checks[r]), None)
    # Gợi ý cho các lý do không gắn với mention; key = reason khớp `focus` của pending.
    if reason == "context_conflict" and last_models:
        candidates[reason] = list(last_models)
    elif reason == "insufficient_models_for_comparison":
        # Ưu tiên model đã nhắc trong phiên (mới nhất trước), rồi tới model có tài liệu.
        recent = [m for m in reversed(list(last_models)) if m not in models]
        covered = [m for m in _covered_models(spec["targets"]) if m not in models and m not in recent]
        candidates[reason] = recent + covered
    elif reason == "missing_product_model":
        candidates[reason] = [m for m in _covered_models(spec["targets"]) if m not in models]
    # [C4] Không chặn nếu vẫn còn model đã resolve để trả lời một phần;
    # câu hỏi chung vẫn trả lời được, câu hỏi lại đặt ở cuối.
    blocking = reason is not None and not models and not general
 
    # 4. Coverage + degrade  [C2]
    targets = spec["targets"]
    degraded = False
    supported, unsupported = _supported(models, targets)
    if models and not supported and spec.get("degrade_to"):
        d_sup, d_unsup = _supported(models, spec["degrade_to"])
        if d_sup:
            targets, supported, unsupported, degraded = spec["degrade_to"], d_sup, d_unsup, True
 
    # 5. Route
    if not spec["targets"]:
        route = spec["route"]                                           # [C6]
    elif blocking:
        route = "clarify"
    elif models and not supported:
        route = "no_docs"
    else:
        route = "retrieve"                 # có thể kèm clarification không chặn
 
    # 6. Warnings  [C7]
    if degraded:
        warnings.append("degraded_to_overview")
    if unsupported and supported:
        warnings.append("some_models_lack_docs")
    for t in targets:
        for m in supported:
            ifs = _covered_interfaces(t["domain"], m)
            if ifs is None:
                continue
            for ci in sq.get("control_interface") or []:
                if ci not in ifs:
                    warnings.append(f"interface_not_covered:{m}:{ci}")
 
    # 7. Retrieval chỉ tồn tại khi route=retrieve  [C3]
    retrieval = None
    if route == "retrieve":
        retrieval = {
            "product_scope_mode": mode,
            "targets": targets,
            "fallback_targets": [] if degraded else spec.get("fallback_targets", []),
            "model_filter": supported or None,          # None = cố ý không lọc
            "unsupported_models": unsupported,
            "answer_mode": "general" if general else "overview" if degraded else "full",
        }
 
    handoff = None
    if route == "handoff":
        handoff = sq.get("handoff_reason") or "human_request"
 
    return {
        "id": f"q{idx + 1}",
        "standalone_query": (sq.get("standalone_query") or "").strip(),
        "intent": intent,
        "entities": {
            "product_models": models,
            "unresolved_mentions": ambiguous + unknown,
            "control_interface": list(sq.get("control_interface") or []),
            "spec_attributes": list(sq.get("spec_attributes") or []),
        },
        "retrieval_scope": retrieval,
        "clarification": None if reason is None else {
            "reason": reason,
            "blocking": blocking,
            "mentions": ambiguous + unknown,
            "candidates": candidates,
        },
        "handoff_reason": handoff,
        "unsupported_models": unsupported,     # dùng cho câu "chưa có tài liệu cho X"
        "route": route,
        "warnings": warnings,
    }
 
 
def _unclear(query: str, idx: int = 0) -> dict:
    """[C8] Không hiểu được câu hỏi -> hỏi lại, KHÔNG gán out_of_scope."""
    return {
        "id": f"q{idx + 1}",
        "standalone_query": query.strip(),
        "intent": None,
        "entities": {"product_models": [], "unresolved_mentions": [],
                     "control_interface": [], "spec_attributes": []},
        "retrieval_scope": None,
        "clarification": {"reason": "unclear_query", "blocking": True,
                          "mentions": [], "candidates": {}},
        "handoff_reason": None,
        "unsupported_models": [],
        "route": "clarify",
        "warnings": ["llm_output_invalid"],
    }
 
 
def resolve_with_raw(
    raw: dict | None,
    *,
    last_models: list[str] | tuple = (),
    active_model: str | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Như resolve(), kèm sub_query thô của LLM theo id đã cấp (dùng để vá khi làm rõ)."""
    out, raws, seen = [], {}, set()
    for sq in ((raw or {}).get("sub_queries") or [])[:MAX_SUB_QUERIES]:
        key = (sq.get("intent"), _norm(sq.get("standalone_query", "")))
        if key in seen:
            continue
        seen.add(key)
        resolved = resolve_sub_query(
            sq, len(out), last_models=last_models, active_model=active_model,
        )
        raws[resolved["id"]] = sq
        out.append(resolved)
    return (out or [_unclear("")]), raws


def resolve(raw: dict | None) -> list[dict]:
    """Đầu vào: JSON của LLM (hoặc None nếu parse lỗi). Đầu ra: list sub_query hoàn chỉnh."""
    return resolve_with_raw(raw)[0]



_TURN_PRIORITY = ("handoff", "retrieve", "clarify", "no_docs", "chitchat", "out_of_scope")
 
 
def plan_turn(subs: list[dict]) -> dict:
    """Gộp các sub_query thành một kế hoạch duy nhất cho lượt hội thoại.

    - turn_route : route chính của lượt (handoff > retrieve > clarify > no_docs > ...)
    - answer     : id các sub_query sẽ được trả lời bằng RAG (gồm cả soft handoff có tóm tắt)
    - no_docs    : id các sub_query cần báo "chưa có tài liệu" (+ gợi ý handoff)
    - clarification : TỐI ĐA MỘT câu hỏi lại / lượt (ưu tiên câu chặn)
    - batches    : gom truy xuất cùng (domain, model_filter) -> một lần gọi retriever
    """
    routes = {s["route"] for s in subs}
    turn_route = next(r for r in _TURN_PRIORITY if r in routes)
 
    clar = [s for s in subs if s["clarification"]]
    clar.sort(key=lambda s: not s["clarification"]["blocking"])
    clarification = None
    if clar:
        clarification = {"sub_query_id": clar[0]["id"], **clar[0]["clarification"]}
 
    batches: dict[tuple, dict] = {}
    for s in subs:
        rs = s["retrieval_scope"]
        if not rs:
            continue
        for t in rs["targets"]:
            # answer_mode KHÔNG nằm trong key: cùng dữ liệu thì chỉ truy xuất một lần,
            # chế độ trả lời (full/overview) do generator đọc từ từng sub_query
            key = (t["domain"], tuple(rs["model_filter"] or ()))
            b = batches.setdefault(key, {
                "domain": t["domain"], "scopes": [], "model_filter": rs["model_filter"],
                "sub_query_ids": [],
            })
            for sc in t.get("scopes", []):
                if sc not in b["scopes"]:
                    b["scopes"].append(sc)
            if s["id"] not in b["sub_query_ids"]:
                b["sub_query_ids"].append(s["id"])
 
    return {
        "turn_route": turn_route,
        "answer": [s["id"] for s in subs if s["route"] == "retrieve"],
        "no_docs": [s["id"] for s in subs if s["route"] == "no_docs"],
        "direct": [s["id"] for s in subs if s["route"] in ("chitchat", "out_of_scope")],
        "handoff_reason": next((s["handoff_reason"] for s in subs if s["handoff_reason"]), None),
        "clarification": clarification,
        "batches": list(batches.values()),
        "sub_queries": subs
    }

# CHANGELOG v3.0 -> v3.1
#   Output sub_query: thêm id, entities.unresolved_mentions, clarification.blocking,
#   retrieval_scope.answer_mode; retrieval_scope = None khi route != retrieve;
#   clarification = None khi không cần; model_filter None thay cho [];
#   route "direct" tách thành "chitchat" / "out_of_scope".
#   Downstream cần đọc plan_turn() thay vì tự duyệt list sub_query.
 