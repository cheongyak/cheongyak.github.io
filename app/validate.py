"""수집 결과 자동 검증.

매 실행마다 모든 공고를 검사하고, 걸린 항목은
  - 공고의 `checks` 에 남겨 화면에 '데이터 확인 필요'로 보여주고
  - 실행 기록(docs/run-log.txt)에 [검증] 줄로 남긴다.
또 사람이 모집공고문 원문으로 확인한 정답(tests/golden/notices.json)과 비교해 다르면 [검증·정답 불일치]로 남긴다.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import rules as R
from .engine import grade
from .geo import in_korea
from .models import Listing

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "notices.json"


def listing_checks(L: Listing, today: date) -> list[str]:
    out: list[str] = []
    # 날짜 순서: 공고일 ≤ 접수 시작 ≤ 접수 마감 ≤ 당첨자 발표 ≤ 계약
    seq = [("공고일", L.notice), ("접수 시작", L.special_apply or L.apply), ("접수 마감", L.apply_end),
           ("발표", L.winner), ("계약", L.contract)]
    seq = [(k, v) for k, v in seq if v]
    for (k1, v1), (k2, v2) in zip(seq, seq[1:]):
        if v1 > v2:
            out.append(f"날짜 순서가 이상해요 ({k1} {v1} > {k2} {v2})")
    for c in getattr(L, "notice_conflicts", None) or []:   # 공고문 안 두 곳의 값이 다름 (notice_pdf.parse_notice conflicts)
        out.append("공고문 안에서 값이 서로 달라요 — " + c)
    # 공공분양 전용 60㎡ 이하 일반공급은 소득·자산 기준이 있다. 공고문에서 못 읽으면 화면은 '확인 필요'로 둔다 (기능: pub_general_limits)
    if getattr(L, "rental", False) and not getattr(L, "pub_limits", None):   # 공공임대는 면적과 관계없이 소득·총자산 기준이 있다 (기능: rental_rules)
        out.append("공공임대 일반공급 소득·총자산 기준을 공고문에서 읽지 못했어요 (화면은 확인 필요)")
    elif L.house_dtl == "국민" and L.category == "general" and "신혼희망타운" not in L.name and (L.area or 0) <= 60 and not getattr(L, "pub_limits", None):
        out.append("공공분양 60㎡ 이하 일반공급 소득·자산 기준을 공고문에서 읽지 못했어요 (화면은 확인 필요)")
    sc = getattr(L, "schedule", None) or {}   # 공고문 접수 일정과 청약홈 날짜가 다르면 알린다 (기능: notice_schedule)
    if sc.get("special") and L.special_apply and sc["special"][0] != L.special_apply:
        out.append(f"특별공급 접수일이 청약홈({L.special_apply})과 공고문({sc['special'][0]})에서 달라요")
    if sc.get("general") and L.apply_end and sc["general"][1] != L.apply_end:
        out.append(f"접수 마감일이 청약홈({L.apply_end})과 공고문 일반공급({sc['general'][1]})에서 달라요")
    sr = getattr(L, "score_ratio", None) or {}   # 민영 가점제·추첨제 비율 표를 못 읽으면 알린다 (기능: region_first_score)
    if L.house_dtl == "민영" and sr.get("unknown"):
        out.append("가점제·추첨제 비율 표를 공고문에서 읽지 못했어요 (화면은 비율 없이 안내)")
    if L.balance and L.contract and L.balance < L.contract:
        out.append(f"잔금일({L.balance})이 계약일({L.contract})보다 빨라요")
    # 금액
    if not (0.5 <= L.price <= 100):
        out.append(f"분양가 {L.price}억이 범위를 벗어나요")
    if L.ext and not (0 < L.ext < L.price * 0.1):
        out.append(f"확장비 {L.ext}억이 분양가 대비 이상해요")
    # 규제·의무
    if L.residence_duty and not (L.capital and L.price_cap):
        out.append("실거주 의무가 수도권 분양가상한제 주택이 아닌데 붙어 있어요")
    if L.regulated and "세대주 요건" not in L.from_notice and L.need_head:
        out.append("세대주 요건을 공고문에서 확인하지 못해 규제지역 기준으로 추정했어요")
    if "재당첨 제한" not in L.from_notice and (L.regulated or L.price_cap):
        # 비규제·상한제 미적용 주택은 재당첨 제한 대상이 아니라 추정해도 틀릴 여지가 작다
        out.append("재당첨 제한 기간을 공고문에서 확인하지 못해 추정했어요")
    # 시세
    g = grade(L)
    if g["grade"] != "unknown":
        if L.mkt_count < 3:
            out.append(f"시세 근거 거래가 {L.mkt_count}건뿐이에요")
        if g["rate"] is not None and (g["rate"] > 1.0 or g["rate"] < -0.5):
            out.append(f"마진율 {g['rate']:.0%}는 이례적이에요. 시세 근거를 확인하세요")
        oldest = (today - timedelta(days=31 * R.MARKET_MONTHS + 31)).isoformat()
        if any((c.get("date") or "9999") < oldest for c in L.mkt_comps):
            out.append("시세 근거에 기간을 벗어난 거래가 섞여 있어요")
    if not L.sido:
        out.append("주소에서 시·도를 찾지 못했어요")
    if L.geo and not in_korea(L.geo.get("lat", 0), L.geo.get("lng", 0)):
        out.append("지도 좌표가 국내 범위를 벗어나요")
    return out


def golden_mismatches(listings: list[Listing]) -> list[str]:
    try:
        gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for L in listings:
        g = gold.get(L.id.split("-")[0])
        if not g:
            continue
        rewin = next((v for k, v in L.limits if k == "재당첨 제한"), None)
        actual = {**L.model_dump(), "rewin_years": (int(rewin[:-1]) if rewin and rewin.endswith("년") else 0 if rewin == "없음" else None)}
        for k, want in g["fields"].items():
            have = actual.get(k)
            if k in ("complex", "resale") and isinstance(want, dict):   # 전매제한 정답은 적은 칸만 비교 (기능 resale_limit)   # 단지 규모 정답은 총세대·동 수만 (수집값에는 상태·출처·원문이 더 붙는다, 기능 complex_size)
                have = {kk: (have or {}).get(kk) for kk in want}
                ok = want == have
            elif isinstance(want, float) and isinstance(have, (int, float)):
                ok = abs(want - have) < 0.0001
            else:
                ok = want == have
            if not ok:
                out.append(f"[검증·정답 불일치] {L.name} {L.unit} · {k}: 수집값 {have!r} ≠ 공고문 {want!r}")
    return out


def run_checks(listings: list[Listing], today: date) -> list[str]:
    log = []
    for L in listings:
        L.checks = listing_checks(L, today)
    flagged = [L for L in listings if L.checks]
    log.append(f"[검증] 공고 {len(listings)}건 중 {len(flagged)}건에 확인할 점이 있어요")
    for L in flagged:
        log.append(f"[검증] {L.name} {L.unit}: " + " / ".join(L.checks))
    mism = golden_mismatches(listings)
    log += mism or ["[검증·정답] 정답 데이터와 모두 일치해요 (대상 공고가 없으면 비교 생략)"]
    return log
