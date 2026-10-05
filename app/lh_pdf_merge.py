"""LH 임대 공고문을 여러 도구로 읽은 결과 합치기 (기능 lh_pdf_multi, 2026-10-05 사용자 '임대/청년주택도 pdf를 잘못읽는 경우가 많으니,
일반분양처럼 pdf 읽는 방법을 여러가지로 해서 보완').

도구: pypdf(evidence/lh/<id>.txt, 기준) · pypdfium2(evidence/lh/pdfium/<id>.txt) · pdfplumber(evidence/lh/plumber/<id>.txt).
같은 읽기 규칙(app/lh_terms)을 도구마다 돌리고, 값마다 아래처럼 합친다. 일반분양 notice_pdf.merge_alt 와 같은 원칙(모르면 확인 필요)에
도구가 셋이라 다수결을 더했다.

 - 공고 단위 값(local·regions·account·income_add_per)·계층 칸(무주택·소득%·총자산·자동차·나이 …):
   읽은 도구가 모두 같으면 그 값 / 기준 도구가 못 읽었으면 다른 도구 값(보완) / 서로 다르면 과반(2개 이상) 값, 과반이 없으면 비워서
   화면이 '공고문 확인'으로 묻게 하고 conflicts 에 남긴다 (틀린 값으로 판정하지 않는다).
 - 문장이 있는지 보는 값(relaxed·homeless_relaxed·homeless_max1): 글자 순서가 흐트러지면 문장을 놓치기만 하고 없는 문장이 생기지는 않으므로
   한 도구라도 찾으면 참. 서로 다르면 notes 에 남긴다.
 - 소득 100% 금액표: 앱 고정값(도시근로자 URBAN_2025 · 2026 기준 중위소득 MEDIAN_2026)과 같은 도구 값을 쓴다. 맞는 도구가 없으면 기준 도구 값
   (수집이 [검증·공고문 불일치]로 남김).
 - 계층 목록: 과반 도구가 찾은 계층. 기준 도구만 읽혔으면 그대로.
 - 임대조건(보증금·월세): 표를 한 도구에서 통째로. 기준 도구가 못 읽었거나, 다른 도구가 기준의 금액 줄을 모두 포함하며 더 읽었을 때만 그 도구.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from app.lh_terms import MEDIAN_2026, URBAN_2025, parse_lh_rents, parse_lh_terms

TOOLS = ("pypdf", "pdfium", "plumber")
NOTICE_KEYS = ("local", "regions", "account", "income_add_per")
PHRASE_KEYS = ("relaxed", "homeless_relaxed", "homeless_max1", "prewed_ok")
UNION_KEYS = ("unknown_groups",)   # 모르는 계층: 한 도구라도 찾으면 넣는다 (판정하지 않고 '일부 계층 판정 못 함'으로 알리는 쪽이 안전)
GROUP_SKIP = ("key", "name")


def _canon(v):
    """비교용 (local 은 인용문을 빼고 이름·시도·시군만)"""
    if isinstance(v, dict) and "quote" in v:
        return {k: x for k, x in v.items() if k != "quote"}
    return v


def _vote(vals: dict) -> tuple[object, str]:
    """vals: 도구 → 값(None 은 못 읽음). → (고른 값, 상태) 상태: same·fill·majority·conflict·none"""
    got = {t: v for t, v in vals.items() if v is not None}
    if not got:
        return None, "none"
    keys = [repr(_canon(v)) for v in got.values()]
    if len(set(keys)) == 1:
        v = next(iter(got.values()))
        return v, "fill" if vals.get("pypdf") is None else "same"
    top, n = Counter(keys).most_common(1)[0]
    if n >= 2:
        return next(v for v in got.values() if repr(_canon(v)) == top), "majority"
    return None, "conflict"


def income_table_from_cells(tables: list) -> Optional[dict]:
    """pdfplumber 칸 단위 표에서 소득 100% 금액표 (머리글 칸 '~100%' 또는 '100%' 의 열, 행 머리 'N인'). 30% 열이 있으면 ÷0.3 과 1% 안일 때만."""
    for tb in tables or []:
        rows = tb.get("rows") or []
        col = c30 = None
        for r in rows:
            cells = [c.replace(" ", "") for c in r]
            if "~100%" in cells or "100%" in cells:
                col = cells.index("~100%") if "~100%" in cells else cells.index("100%")
                c30 = cells.index("~30%") if "~30%" in cells else None
                break
        if col is None:
            continue
        out = {}
        for r in rows:
            m = re.fullmatch(r"([1-8])인", (r[0] or "").replace(" ", "")) if r else None
            if not m or len(r) <= col:
                continue
            v = re.fullmatch(r"\d{1,3}(?:,\d{3})+", r[col].replace(" ", ""))
            if not v:
                continue
            val = int(v.group(0).replace(",", ""))
            if c30 is not None and len(r) > c30 and re.fullmatch(r"[\d,]+", r[c30].replace(" ", "")):
                if abs(int(r[c30].replace(",", "").replace(" ", "")) / 0.3 - val) > val * 0.01:
                    continue
            out[m.group(1)] = val
        if out:
            return out
    return None


def _table_ok(basis: Optional[str], tb: Optional[dict]) -> bool:
    if not tb:
        return False
    ref = MEDIAN_2026 if basis == "기준 중위소득" else URBAN_2025
    return all(ref.get(int(k)) == v for k, v in tb.items())


def merge_terms(parsed: dict, cell_table: Optional[dict] = None) -> tuple[dict, list[str], list[str]]:
    """parsed: 도구 → parse_lh_terms 결과, cell_table: pdfplumber 칸 단위 표에서 읽은 소득 100% 표.
    → (합친 terms, notes(보완 기록), conflicts(사람이 원문을 봐야 함))"""
    base = parsed.get("pypdf") or next(iter(parsed.values()))
    if len(parsed) < 2 and not cell_table:
        return base, [], []
    out = dict(base)
    notes: list[str] = []
    conflicts: list[str] = []
    for k in PHRASE_KEYS:
        vs = {t: p.get(k) for t, p in parsed.items()}
        if k not in base and not any(k in p for p in parsed.values()):
            continue
        if any(vs.values()):
            out[k] = True
            if not all(vs.values()):
                notes.append(f"{k}: {', '.join(t for t, v in vs.items() if v)} 만 찾음 → 참")
    for k in UNION_KEYS:
        if any(k in p for p in parsed.values()):
            out[k] = list(dict.fromkeys(x for p in parsed.values() for x in (p.get(k) or [])))
    for k in NOTICE_KEYS:
        vs = {t: p.get(k) for t, p in parsed.items()}
        v, st = _vote(vs)
        if st in ("fill", "majority"):
            notes.append(f"{k}: {st} {', '.join(f'{t}={_canon(x)!r}' for t, x in vs.items())}")
        if st == "conflict":
            conflicts.append(f"{k} 값이 읽기 도구마다 달라요: " + ", ".join(f"{t}={_canon(x)!r}" for t, x in vs.items()))
        if v is not None or st == "conflict":
            out[k] = v
    # 소득 100% 금액표: 고정값과 맞는 도구
    basis = base.get("income_basis")
    tbs = {t: p.get("income_table_100") for t, p in parsed.items()}
    if cell_table and base.get("income_table_100") is not None:   # 표를 읽는 공고 유형(행복주택·통합공공임대)일 때만
        tbs["plumber_cells"] = {k: v for k, v in cell_table.items() if k in base["income_table_100"]} or cell_table
    good = [t for t in (*TOOLS, "plumber_cells") if t in tbs and _table_ok(basis, tbs[t])]
    if good and not _table_ok(basis, base.get("income_table_100")):
        out["income_table_100"] = tbs[good[0]]
        notes.append(f"income_table_100: {good[0]} 값이 앱 고정값과 같아 씀 (pypdf={base.get('income_table_100')})")
    # 계층
    gsets = {t: {g["key"]: g for g in p.get("groups") or []} for t, p in parsed.items()}
    have = [t for t in gsets if gsets[t]]
    if have:
        cnt = Counter(k for t in have for k in gsets[t])
        need = 2 if len(have) >= 2 else 1
        keys = [k for k in (list(gsets.get("pypdf", {})) + [k for t in have for k in gsets[t]]) if cnt[k] >= need]
        keys = list(dict.fromkeys(keys)) or list(gsets.get("pypdf") or gsets[have[0]])
        groups = []
        for key in keys:
            src = {t: gsets[t].get(key) for t in parsed}
            g0 = dict(next(g for g in (src.get("pypdf"), *src.values()) if g))
            fields = {f for g in src.values() if g for f in g} - set(GROUP_SKIP)
            for f in sorted(fields):
                vs = {t: (g.get(f) if g else None) for t, g in src.items()}
                v, st = _vote(vs)
                if st in ("fill", "majority"):
                    notes.append(f"{key}.{f}: {st} {', '.join(f'{t}={x!r}' for t, x in vs.items())}")
                if st == "conflict":
                    conflicts.append(f"{key} {f} 값이 읽기 도구마다 달라요: " + ", ".join(f"{t}={x!r}" for t, x in vs.items()))
                g0[f] = v
            groups.append(g0)
        if [g["key"] for g in groups] != list(gsets.get("pypdf", {})):
            notes.append(f"계층: pypdf {list(gsets.get('pypdf', {}))} → {[g['key'] for g in groups]}")
        out["groups"] = groups
    return out, notes, conflicts


def merge_rents(rows_by_tool: dict) -> tuple[list[dict], list[str], list[str]]:
    """임대조건 표는 한 도구의 줄을 통째로 쓴다(줄 단위로 섞으면 도구마다 다른 주택형·구분 이름 때문에 다른 줄끼리 짝지어질 수 있다).
    줄마다 '계 = 계약금 + 잔금' 검사를 통과한 것만 나오므로, 기준 도구(pypdf)가 못 읽었거나 다른 도구가 기준의 금액 줄을 모두 포함하면서
    더 많이 읽었을 때만 그 도구 표를 쓴다. 금액 줄이 서로 다르면 notes 에 남긴다."""
    base = rows_by_tool.get("pypdf") or []
    if len(rows_by_tool) < 2:
        return base, [], []
    pairs = {t: {(r["deposit"], r["rent"]) for r in rows} for t, rows in rows_by_tool.items()}
    notes: list[str] = []
    pick = "pypdf"
    if not base:
        pick = next((t for t in ("pdfium", "plumber") if rows_by_tool.get(t)), "pypdf")
        if pick != "pypdf":
            notes.append(f"임대조건: pypdf 못 읽음 → {pick} {len(rows_by_tool[pick])}줄")
    else:
        sup = [t for t in ("pdfium", "plumber") if t in pairs and pairs[t] > pairs["pypdf"]]
        if sup:
            pick = max(sup, key=lambda t: len(pairs[t]))
            notes.append(f"임대조건: {pick} 가 pypdf 금액 줄을 모두 포함하고 {len(pairs[pick] - pairs['pypdf'])}줄 더 읽음 → {pick}")
    for t in pairs:
        if t != pick and pairs[t] and pairs[t] != pairs[pick] and not pairs[t] < pairs[pick]:
            notes.append(f"임대조건: {t} 금액 줄이 {pick} 와 다름 ({len(pairs[t] - pairs[pick])}줄) — {pick} 표를 씀")
    return list(rows_by_tool.get(pick) or []), notes, []


def read_all(texts: dict, kind: str, name: str, region: Optional[str], unit_types: list[str], judge: bool, tables: Optional[list] = None) -> dict:
    """texts: 도구 → 글(못 읽었으면 빠짐), tables: pdfplumber 칸 단위 표. → {"terms", "rents", "notes", "conflicts", "tools"}"""
    texts = {t: x for t, x in texts.items() if x and len(x) >= 500}
    res = {"tools": list(texts), "notes": [], "conflicts": [], "terms": None, "rents": []}
    if not texts:
        return res
    if judge:
        parsed = {}
        for t, x in texts.items():
            try:
                parsed[t] = parse_lh_terms(x, kind, name, region)
            except Exception:
                pass
        if parsed:
            res["terms"], n, c = merge_terms(parsed, income_table_from_cells(tables or []))
            res["notes"] += n
            res["conflicts"] += c
    rows = {}
    for t, x in texts.items():
        try:
            rows[t] = parse_lh_rents(x, unit_types)
        except Exception:
            pass
    if rows:
        res["rents"], n, c = merge_rents(rows)
        res["notes"] += n
        res["conflicts"] += c
    return res
