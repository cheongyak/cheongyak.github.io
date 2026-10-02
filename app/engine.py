"""판정 엔진: 등급(마진) · 내 자격 · 자금 · 전세 가능 여부.

웹 프로토타입의 계산과 같은 규칙이다. 한쪽을 고치면 다른 쪽도 맞춘다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from . import rules as R
from .models import Listing, PlanOptions, Profile

GRADE_NAMES = {"lotto": "로또", "consider": "고려", "flat": "마진없음", "pass": "패스", "unknown": "시세 부족"}
CONFIG_PATH = Path(__file__).resolve().parent.parent / "docs" / "config.json"


def grade_name(g: str) -> str:
    """등급 이름. 스위치 grade_skip 이 켜져 있으면 '패스' 등급을 '비추천'으로 부른다 (기준은 같음)."""
    if g == "pass":
        try:
            feats = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("features", {})
        except (OSError, ValueError):
            feats = {}
        if feats.get("grade_skip", True):
            return "비추천"
    return GRADE_NAMES[g]


def eok(manwon: float) -> float:
    return manwon / 10000


def acq_tax(base: float) -> float:
    """1주택 취득세 + 지방교육세 (전용 85㎡ 이하 가정, 억 원)."""
    if base <= 6:
        rate = 0.01
    elif base <= 9:
        rate = (base * 2 / 3 - 3) / 100
    else:
        rate = 0.03
    return base * rate * 1.1


def grade(L: Listing) -> dict:
    base = L.price + L.ext
    tax = acq_tax(base)
    cost = base + tax
    if L.mkt_low is None or L.mkt_base is None:
        return {"grade": "unknown", "name": grade_name("unknown"), "cost": cost, "tax": tax,
                "lo": None, "hi": None, "rate": None}
    lo, hi = L.mkt_low - cost, L.mkt_base - cost
    rate = lo / cost
    if lo >= R.LOTTO_ABS or rate >= R.LOTTO_RATE:
        g = "lotto"
    elif lo >= R.CONSIDER_ABS:
        g = "consider"
    elif lo >= 0:
        g = "flat"
    else:
        g = "pass"
    return {"grade": g, "name": grade_name(g), "cost": cost, "tax": tax, "lo": lo, "hi": hi, "rate": rate}


def eligibility(L: Listing, p: Profile) -> dict:
    items = []

    if L.region == "서울":
        items.append({"k": "거주지 (서울)", "s": "ok" if p.seoul else "fail", "v": "충족" if p.seoul else "미충족"})
    elif L.region in ("경기", "인천"):
        items.append({"k": "거주지 (수도권)", "s": "ok" if p.seoul else "warn", "v": "충족" if p.seoul else "확인 필요",
                      "note": "해당 지역 우선공급 대상은 아니에요" if p.seoul else ""})
    else:
        items.append({"k": f"거주지 ({L.region})", "s": "warn", "v": "확인 필요", "note": "공고문의 거주 지역 요건을 확인하세요"})

    own, note = [], ""
    if p.selfOwn:
        own.append("본인 명의 주택")
    if p.married and p.spouseOwn:
        own.append("배우자 명의 주택")
    if p.household == "parents" and p.parentsOwn:
        if p.parents60:
            note = "부모님 주택: 만 60세 이상 예외 적용"
        else:
            own.append("부모님 주택 (만 60세 미만)")
    if not p.married:
        note = (note + " · " if note else "") + "혼인신고 전: 배우자 주택 미합산"
    items.append({"k": "무주택 세대", "s": "fail" if own else "ok", "v": "미충족" if own else "충족",
                  "note": ", ".join(own) if own else note})

    if L.need_head:
        s, v = "fail", "미충족"
        hn = f"공고일 {L.notice} 기준" if L.notice else ""
        if p.household == "head":
            if L.notice and p.headSince and p.headSince > L.notice:
                hn = "공고일보다 늦게 세대주가 됐어요"
            else:
                s, v = "ok", "충족"
        items.append({"k": "세대주", "s": s, "v": v, "note": hn})

    if not L.need_account:
        items.append({"k": "청약통장", "s": "na", "v": "불필요"})
    else:
        s = {"yes": "ok", "no": "fail"}.get(p.account, "warn")
        items.append({"k": "청약통장", "s": s, "v": {"ok": "충족", "fail": "미충족", "warn": "확인 필요"}[s]})

    # 공고의 재당첨 제한(당첨되면 걸리는 기간)과 헷갈리지 않게 '내 이력'으로 부른다
    items.append({"k": "재당첨 제한 (내 이력)", "s": "fail" if p.recentWin else "ok",
                  "v": "제한 중" if p.recentWin else "해당 없음", "note": "과거 당첨으로 지금 제한 기간인지 여부"})

    if L.target == "신혼부부":
        items.append({"k": "신혼부부 전용", "s": "ok" if p.married else "fail", "v": "충족" if p.married else "미충족",
                      "note": "혼인신고 7년 이내 등 공고문 요건 확인" if p.married else "혼인신고를 한 신혼부부만 신청할 수 있어요"})
    elif L.target:
        items.append({"k": f"{L.target} 전용", "s": "warn", "v": "확인 필요", "note": "공고문의 대상 요건을 확인하세요"})

    fails = [i for i in items if i["s"] == "fail"]
    reason = fix = ""
    if fails:
        f = fails[0]
        if f["k"] == "세대주":
            reason = (f"모집공고일({L.notice}) 기준 세대주가 아니에요. 지금 바꿔도 이번 공고에는 반영되지 않아요."
                      if L.notice else "세대주가 아니에요.")
        elif f["k"].startswith("무주택"):
            reason = f"세대에 주택 소유자가 있어요 ({f['note']})."
        elif f["k"].startswith("거주"):
            reason = f"{L.region} 거주자만 신청할 수 있어요."
        elif f["k"].endswith("전용"):
            reason = f"{f['k'].replace(' 전용', '')} 대상 공급이에요. {f.get('note', '')}"
        elif f["k"] == "청약통장":
            reason = "1순위 청약통장 요건을 채우지 못했어요."
        else:
            reason = "재당첨 제한 기간이에요."
        if any(i["k"] == "세대주" for i in fails):
            fix = ("부모님이 모두 만 60세 이상이라 세대주만 본인으로 변경하면 무주택 세대주가 돼요. 다음 공고부터 적용돼요."
                   if p.household == "parents" and p.parents60
                   else "다음 공고의 모집공고일 전에 세대주가 되어 두세요. 전입신고로 세대를 만들 때는 실제로 살아야 해요.")
    return {"ok": not fails, "unsure": not fails and any(i["s"] == "warn" for i in items),
            "items": items, "reason": reason, "fix": fix}


def jeonse_check(L: Listing) -> dict:
    reasons: list[dict] = []
    status = "ok"

    def add(lvl: str, t: str):
        nonlocal status
        reasons.append({"lvl": lvl, "t": t})
        rank = {"ok": 0, "cond": 1, "check": 2, "no": 3}   # 모르는 사실이 있으면 '조건부'가 아니라 '확인 필요' (화면 jeonseCheck 와 같게, 2026-10-02)
        if rank.get(lvl, 0) > rank[status]:
            status = lvl

    if L.residence_duty is None:
        add("check", ("분양가상한제 단지라 " if L.price_cap else "") + "실거주 의무가 있는지 공고문에서 확인하지 못했어요. 거주의무가 있으면 전세를 한 번만 주거나 "
                     "못 줄 수 있어요 — " + ("공고문에 거주의무 기간이 적혀 있지 않아 공급자(사업주체)에 확인하세요." if L.duty_silent else "모집공고문의 거주의무 안내를 확인하세요."))
    elif L.residence_duty > 0:
        add("cond", f"실거주 의무 {L.residence_duty}년이 있어요. 최초 입주가능일부터 {R.DUTY_DEFERRAL_YEARS}년 안에만 "
                    "들어가 살면 돼서 전세는 한 번(2년)만 줄 수 있어요. 그때 돌려줄 보증금을 따로 마련해야 해요.")
    if L.regulated and L.capital:
        add("cond", "수도권 규제지역이라 세입자가 소유권이전 조건부 전세대출을 쓰기 어려워요. "
                    "보증금을 현금으로 낼 수 있는 세입자만 받을 수 있어서 보증금을 낮게 잡는 게 안전해요.")
    elif L.unregistered:
        add("info", "입주 직후엔 등기 전이라 세입자 전세대출 심사가 까다로울 수 있어요. 은행에 미리 확인하세요.")
    if L.regulated:
        add("info", "규제지역에서 주담대를 받으면 6개월 안에 전입해야 해요. 잔금대출과 전세를 함께 쓸 수는 없어요.")
    else:
        add("info", "비규제지역이라 전입 의무가 없어요. 다만 선순위 대출이 있으면 세입자가 꺼려서 보증금이 낮아져요.")
    if L.land_permit:
        add("info", "토지거래허가구역이지만 최초 분양계약은 허가 대상이 아니에요. 나중에 팔 때는 매수자에게 실거주 의무가 붙어요.")
    if L.jeonse_weak:
        add("cond", "전세 수요가 약한 지역이에요. 입주장에 세입자를 못 구하면 잔금을 못 치를 수 있어요.")
    if L.jeonse is None:
        add("cond", "주변 전세 거래가 부족해 보증금을 추정하지 못했어요. 직접 입력해 주세요.")
    return {"status": status, "reasons": reasons}


def loan_capacity(L: Listing, p: Profile) -> dict:
    income = eok(p.income + (p.spouseIncome if p.married else 0))
    existing = eok((p.loanMonthly + (p.spouseLoan if p.married else 0)) * 12)
    r, n = R.STRESS_RATE / 12, R.LOAN_YEARS * 12
    monthly = max(0.0, income * R.DSR - existing) / 12
    by_dsr = monthly * (1 - (1 + r) ** -n) / r
    ltv_rate = R.LTV_REGULATED if L.regulated else R.LTV_OTHER
    basis = min(L.price, L.mkt_base) if L.mkt_base else L.price
    by_ltv = basis * ltv_rate
    if L.regulated:
        mkt = L.mkt_base or L.price
        cap = next(c for limit, c in R.LOAN_CAP_REGULATED if mkt <= limit)
    elif L.capital:
        cap = R.LOAN_CAP_CAPITAL
    else:
        cap = math.inf
    loan = min(by_dsr, by_ltv, cap)
    limit_by = "DSR(소득)" if loan == by_dsr else (f"한도 {cap:g}억" if loan == cap else f"LTV {ltv_rate:.0%}")
    return {"loan": loan, "by_dsr": by_dsr, "by_ltv": by_ltv, "ltv_rate": ltv_rate,
            "cap": None if math.isinf(cap) else cap, "limit_by": limit_by}


def funding(L: Listing, p: Profile, opt: Optional[PlanOptions] = None) -> dict:
    opt = opt or PlanOptions()
    g = grade(L)
    jc = jeonse_check(L)
    mode = opt.mode or ("live" if jc["status"] == "no" else "jeonse")
    if mode == "jeonse" and jc["status"] == "no":
        mode = "live"
    total = g["cost"]
    contract_amt = (L.price + L.ext) * L.contract_rate
    available = eok(p.cash + p.liquid + p.deposit) + eok(opt.family)
    lc = loan_capacity(L, p)
    jeonse = eok(opt.jeonse) if opt.jeonse is not None else L.jeonse
    gap_live = total - lc["loan"] - available
    gap_jeonse = None if jeonse is None or jc["status"] == "no" else total - jeonse - available
    return {
        "mode": mode, "total": total, "tax": g["tax"], "available": available,
        "contract_amount": contract_amt, "contract_ok": eok(p.cash) >= contract_amt,
        "loan": lc, "jeonse": jeonse, "jeonse_check": jc,
        "gap_live": gap_live, "gap_jeonse": gap_jeonse,
        "gap": gap_jeonse if mode == "jeonse" and gap_jeonse is not None else gap_live,
    }


def judge(L: Listing, p: Optional[Profile] = None, opt: Optional[PlanOptions] = None) -> dict:
    """공고 하나에 대한 전체 판정. 프로필이 없으면 등급만 돌려준다."""
    g = grade(L)
    out = {"listing": L.model_dump(), "grade": g, "jeonse_check": jeonse_check(L)}
    if p is None:
        return out
    e = eligibility(L, p)
    f = funding(L, p, opt)
    if not e["ok"]:
        verdict = "신청 불가"
    elif g["grade"] in ("pass", "flat"):
        verdict = "자격은 되지만 마진 부족"
    elif g["grade"] == "unknown":
        verdict = "시세 확인 필요"
    elif f["gap"] > 0:
        verdict = f"자금 {f['gap']:.2f}억 부족"
    else:
        verdict = "넣어도 돼요"
    out.update({"eligibility": e, "funding": f, "verdict": verdict})
    return out
