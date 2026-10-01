"""공고문 원문 ↔ 앱 수치 대조 (기능: notice_crosscheck). 매 수집마다 실행한다.

화면 판정에 쓰는 고정 수치(docs/index.html 의 SP_INCOME_2025·SP_ASSET·ACCOUNT_DEPOSIT·출산가구 완화 자산값)와
청약홈 분양가가 각 모집공고문 원문 숫자와 같은지 본다. 원문 숫자는 notice_pdf.notice_facts 가 공고문을 읽을 때 뽑아 둔다.
다르면 그 공고의 주택형 전체에 '공고문 대조' 확인 필요를 붙이고 실행 기록에 [검증·공고문 불일치] 로 남긴다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "docs" / "index.html"


def app_constants(path: Path = INDEX) -> dict:
    s = path.read_text(encoding="utf-8")
    inc = [int(x) for x in re.search(r"const SP_INCOME_2025 = \[([\d, ]+)\]", s).group(1).split(",")]
    asset = {k: int(v) for k, v in re.findall(r"(minyoung|public|car): (\d+)", re.search(r"const SP_ASSET = \{([^}]+)\}", s).group(1))}
    dep_raw = re.search(r"const ACCOUNT_DEPOSIT = (\{[^;]+\});", s).group(1)
    dep = json.loads(re.sub(r"(\w+):", r'"\1":', dep_raw))
    m = re.search(r"addK === 20 \? (\d+) : addK === 10 \? (\d+) : SP_ASSET\.public\) : SP_ASSET\.minyoung, carLim = addK === 20 \? (\d+) : addK === 10 \? (\d+)", s)
    relax = {"부동산": [int(m.group(2)), int(m.group(1))], "자동차": [int(m.group(4)), int(m.group(3))]} if m else None
    return {"income": inc, "asset": asset, "deposit": dep, "relax": relax}


def notice_problems(facts: dict, C: dict) -> list[str]:
    """공고문 하나의 원문 숫자 ↔ 앱 고정 수치 차이 목록 (빈 목록이면 일치)."""
    out = []
    base = C["income"]
    for pct, nums in sorted((facts.get("income_rows") or {}).items(), key=lambda kv: int(kv[0])):
        want = [int(b * int(pct) // 100 + (1 if (b * int(pct)) % 100 >= 50 else 0)) for b in base]   # 화면(Math.round)과 같은 반올림
        if nums != want:
            out.append(f"소득 기준 {pct}%: 공고문 {nums} ≠ 앱 {want}")
    order = {"85": 0, "102": 1, "135": 2, "all": 3}
    for k, row in (facts.get("deposit_rows") or {}).items():
        for g in ("seoul_busan", "metro", "other"):
            if row.get(g) != C["deposit"][g][order[k]]:
                out.append(f"예치금 {k + '㎡ 이하' if k != 'all' else '모든 면적'} {g}: 공고문 {row.get(g)}만원 ≠ 앱 {C['deposit'][g][order[k]]}만원"
                           + (" (표 머리글을 못 읽어 순서를 추정)" if row.get("order_guess") else ""))
    a = facts.get("asset_thousand") or {}
    rel = C.get("relax") or {"부동산": [], "자동차": []}
    ok_re = {C["asset"]["public"] * 10} | {v * 10 for v in rel["부동산"]}
    ok_car = {C["asset"]["car"] * 10} | {v * 10 for v in rel["자동차"]}
    for v in a.get("부동산") or []:
        if v not in ok_re:
            out.append(f"공공 부동산 기준: 공고문 {v:,}천원 — 앱 기준({', '.join(f'{x:,}' for x in sorted(ok_re))}천원)에 없음")
    if a.get("부동산") and C["asset"]["public"] * 10 not in a["부동산"]:
        out.append(f"공공 부동산 기준: 앱 {C['asset']['public'] * 10:,}천원이 공고문에 없음")
    for v in a.get("자동차") or []:
        if v not in ok_car:
            out.append(f"공공 자동차 기준: 공고문 {v:,}천원 — 앱 기준({', '.join(f'{x:,}' for x in sorted(ok_car))}천원)에 없음")
    for v in a.get("부동산_만원") or []:
        if v != C["asset"]["minyoung"]:
            out.append(f"민영 부동산 기준: 공고문 {v:,}만원 ≠ 앱 {C['asset']['minyoung']:,}만원")
    return out


def run(listings: list, facts_by_notice: dict, C: dict | None = None) -> list[str]:
    """대조 결과를 주택형 checks 에 붙이고 실행 기록 줄을 돌려준다."""
    C = C or app_constants()
    if not C.get("relax"):
        log_relax = ["[검증·공고문 불일치] 앱 코드에서 출산가구 완화 자산값을 읽지 못했어요 (crosscheck.app_constants 정규식 확인)"]
    else:
        log_relax = []
    log, n_notice, n_rows, n_price, n_price_ok = [], 0, 0, 0, 0
    bad_notice = {}
    for nid, facts in facts_by_notice.items():
        if not facts:
            continue
        n_notice += 1
        n_rows += len(facts.get("income_rows") or {}) + len(facts.get("deposit_rows") or {})
        probs = notice_problems(facts, C)
        if probs:
            bad_notice[nid] = probs
    for L in listings:
        nid = L.id.split("-")[0]
        facts = facts_by_notice.get(nid)
        if not facts:
            continue
        ty = L.id.split("-", 1)[1].strip()
        seen = (facts.get("price_seen") or {}).get(ty)
        if seen is not None:
            n_price += 1
            n_price_ok += bool(seen)
            if not seen:
                L.checks = (L.checks or []) + ["공고문 대조: 청약홈 분양가가 모집공고문 공급금액 표에서 확인되지 않아요"]
                log.append(f"[검증·공고문 불일치] {L.name} {L.unit}: 분양가 {L.price}억이 공고문에 없음")
        if nid in bad_notice:
            L.checks = (L.checks or []) + ["공고문 대조: 이 공고문의 소득·자산·예치금 기준이 앱 기준과 달라요 — " + bad_notice[nid][0]]
    for nid, probs in bad_notice.items():
        name = next((L.name for L in listings if L.id.startswith(nid)), nid)
        for p in probs:
            log.append(f"[검증·공고문 불일치] {name} ({nid}): {p}")
    log[:0] = log_relax
    log.insert(0, f"[검증·공고문] 공고문 {n_notice}건 대조 · 기준표 {n_rows}줄 · 분양가 {n_price_ok}/{n_price} 일치 · 불일치 공고 {len(bad_notice)}건")
    return log
