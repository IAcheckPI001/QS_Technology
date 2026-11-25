"""Bảng chấm tay câu trả lời (CSV) và tổng hợp kết quả chấm. Kế hoạch: docs/ai/reports/website_qa_retrieval_eval_plan_2026-11-25.md §9.

`run_generation_eval.py` ghi `grading.csv` (một dòng mỗi câu trả lời, kèm cờ kiểm tự động); người chấm điền các cột
cuối (`dung`, `loi`, `so_khang_dinh`, `khang_dinh_co_nguon`, `ghi_chu`), rồi chạy:
    .\\venv\\Scripts\\python.exe evals\\grading.py summarize <grading.csv>

Không có LLM-judge: toàn bộ nhãn do người điền.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Bảng phân loại lỗi (mã dùng trong cột `loi`, nhiều mã cách nhau bằng `;`).
ERROR_CODES = {
    "bia": "bịa: khẳng định không có trong chunk nào",
    "trich_sai": "trích sai chỗ: [S#] trỏ chunk không chứa ý đó",
    "nham_model": "nhầm model/cột: lấy thông tin của model này gán cho model khác",
    "nham_so": "nhầm số hoặc đơn vị",
    "thieu": "thiếu ý/bước/cổng so với fact vàng",
    "thua": "thừa: trả lời điều không được hỏi hoặc ngoài tài liệu",
    "khong_noi_khong_biet": "không nói 'không biết' khi chunk không có dữ liệu, hoặc từ chối nhầm",
    "khac": "lỗi khác (ghi trong ghi_chu)",
}

AUTO_COLUMNS = ["run_id", "case_id", "split", "source", "mode", "run", "question", "route", "answer", "sources",
                "facts_missing", "auto_flags", "needs_review", "sample"]
HUMAN_COLUMNS = ["dung", "loi", "so_khang_dinh", "khang_dinh_co_nguon", "ghi_chu"]
COLUMNS = AUTO_COLUMNS + HUMAN_COLUMNS


def write_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    """Ghi bảng chấm (UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})


def read_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _num(value: str | None) -> float | None:
    try:
        return float(str(value).replace(",", ".")) if str(value or "").strip() else None
    except ValueError:
        return None


def validate_sheet(rows: list[dict[str, str]]) -> list[str]:
    """Lỗi nhập liệu của người chấm (mã lỗi lạ, `dung` ngoài 0/0,5/1, khẳng định có nguồn > tổng)."""
    problems = []
    for r in rows:
        tag = f"{r.get('case_id')}/{r.get('mode')}/{r.get('run')}"
        dung = _num(r.get("dung"))
        if r.get("dung", "").strip() and dung not in (0.0, 0.5, 1.0):
            problems.append(f"{tag}: dung phải là 0, 0.5 hoặc 1")
        for code in filter(None, (c.strip() for c in (r.get("loi") or "").split(";"))):
            if code not in ERROR_CODES:
                problems.append(f"{tag}: mã lỗi lạ '{code}'")
        total, ok = _num(r.get("so_khang_dinh")), _num(r.get("khang_dinh_co_nguon"))
        if total is not None and ok is not None and ok > total:
            problems.append(f"{tag}: khang_dinh_co_nguon > so_khang_dinh")
        if dung == 1.0 and (r.get("loi") or "").strip():
            problems.append(f"{tag}: dung=1 nhưng có mã lỗi")
    return problems


def summarize_grading(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Theo `mode` (oracle/real): số câu đã chấm, tỉ lệ đúng, tỉ lệ khẳng định có nguồn, số lỗi theo loại, và số liệu
    của kiểm tự động (fact recall tính trên mọi dòng, kể cả chưa chấm tay)."""
    out: dict[str, dict[str, Any]] = {}
    for mode in sorted({r["mode"] for r in rows}):
        mrows = [r for r in rows if r["mode"] == mode]
        graded = [r for r in mrows if _num(r.get("dung")) is not None]
        claims = [(_num(r.get("so_khang_dinh")), _num(r.get("khang_dinh_co_nguon"))) for r in graded]
        claims = [(t, o) for t, o in claims if t is not None and o is not None]
        errors = Counter(code.strip() for r in graded for code in (r.get("loi") or "").split(";") if code.strip())
        out[mode] = {
            "n": len(mrows), "da_cham": len(graded),
            "dung": round(sum(_num(r["dung"]) or 0 for r in graded) / len(graded), 3) if graded else None,
            "khang_dinh_co_nguon": round(sum(o for _, o in claims) / sum(t for t, _ in claims), 3)
            if claims and sum(t for t, _ in claims) else None,
            "loi": dict(errors.most_common()),
            "needs_review": sum(1 for r in mrows if r.get("needs_review") in ("1", "True", "true")),
        }
    return out


def attribute_errors(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    """Ghép cặp oracle/real theo (câu, lần): lỗi do bước sinh hay do tra cứu/ngữ cảnh. Chỉ xét dòng đã chấm `dung`.

    - `loi_sinh`: sai cả khi đưa đúng chunk (oracle sai) → sửa prompt/định dạng chunk/model sinh.
    - `loi_ngu_canh`: oracle đúng nhưng real sai → sửa tra cứu (chunk thiếu, nhiễu).
    - `dung_ca_hai`, `chi_real_dung` (hiếm: nghi oracle thiếu chunk hoặc may mắn).
    """
    by_key: dict[tuple[str, str], dict[str, float]] = {}
    for r in rows:
        d = _num(r.get("dung"))
        if d is not None:
            by_key.setdefault((r["case_id"], r.get("run", "1")), {})[r["mode"]] = d
    out: dict[str, list[str]] = {"loi_sinh": [], "loi_ngu_canh": [], "dung_ca_hai": [], "chi_real_dung": []}
    for (case_id, run), modes in sorted(by_key.items()):
        if "oracle" not in modes or "real" not in modes:
            continue
        o, r = modes["oracle"] >= 1.0, modes["real"] >= 1.0
        key = "dung_ca_hai" if o and r else "loi_ngu_canh" if o else "chi_real_dung" if r else "loi_sinh"
        out[key].append(case_id)
    return out


def render_summary(rows: list[dict[str, str]]) -> str:
    lines = ["# Tổng hợp chấm tay", ""]
    problems = validate_sheet(rows)
    if problems:
        lines += ["## Lỗi nhập liệu", *[f"- {p}" for p in problems], ""]
    lines += ["| Chế độ | n | đã chấm | đúng | khẳng định có nguồn | cờ cần xem |", "|---|---|---|---|---|---|"]
    summary = summarize_grading(rows)
    for mode, s in summary.items():
        lines.append(f"| {mode} | {s['n']} | {s['da_cham']} | {s['dung']} | {s['khang_dinh_co_nguon']} | {s['needs_review']} |")
    lines += ["", "## Lỗi theo loại", ""]
    for mode, s in summary.items():
        lines.append(f"- {mode}: " + (", ".join(f"{k}={v}" for k, v in s["loi"].items()) or "chưa có"))
    attr = attribute_errors(rows)
    lines += ["", "## Nguồn gốc lỗi (ghép oracle ↔ real)", ""]
    lines += [f"- {k}: {len(v)} ({', '.join(v)})" for k, v in attr.items()]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if len(argv) != 3 or argv[1] != "summarize":
        print("dùng: grading.py summarize <grading.csv>")
        return 2
    print(render_summary(read_sheet(Path(argv[2]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
