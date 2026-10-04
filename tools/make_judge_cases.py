"""판정 검증 사례 만들기 (기능: judge_cases) → tests/judge/cases.json

화면의 판정 엔진(docs/index.html)과 **따로** 공고문·법령 표를 그대로 옮긴 계산(이 파일의 oracle)으로 기대값을 정한다.
같은 출처를 서로 다른 코드로 두 번 구현해 결과를 맞춰 보는 방식이라, 한쪽 코드가 틀리면 사례가 깨진다.

출처 (모두 evidence/notices 원문에서 직접 확인한 표):
  - 가점: 2026000103 「가점 산정기준 [별표1]의 2 나목」 무주택기간·부양가족·입주자저축 가입기간 표, 배우자 통장 50%·최대 3점
  - 소득 기준 금액: 2026000414 <표4>·<표5> '도시근로자 가구당 월평균소득액' 3인 이하 7,533,763원 … 8인 11,064,819원 (100%), 9인 이상 1인당 579,278원
  - 공공 특별공급 단계: 2026000414 신생아(100/120·140/150·140/200) 신혼부부·생애최초(100/120·130/140·130/200) 다자녀(120/130·120/200) 노부모(120/130·120/200)
  - 출산가구 완화: 2026000409·414 1명 +10%p, 2명 이상 +20%p, 부동산 237,050·258,600천원, 자동차 49,960·54,510천원
  - 민영 특별공급 단계: 2026000453 신혼부부 100%(맞벌이 120%, 1인 100% 이하)·140%(160%, 1인 140% 이하)·추첨(부동산 3억3,100만원), 생애최초·신생아 130%·160%
  - 예치금: 2026000453 '전용 85㎡ 이하 300·250·200만원' (특별시·부산 / 그 밖의 광역시 / 그 외)
  - 공공 일반공급 60㎡ 이하: 2026000414 '100% 이하(맞벌이 200%)', 2단계 '100%(맞벌이 140%)', 부동산 215,500천원·자동차 45,420천원
  - 신혼희망타운: 2026820010 130%(맞벌이 140%), 총자산 362,000천원(출산 397,000·431,000천원)
  - 공공임대 일반공급: 2026000307 <표4> 가구원수별 금액(1인 4,576,036 · 2인 6,452,897/11,732,540 · 3인 8,168,429/16,336,858 …), 총자산 362,000천원(출산 397,000천원)
  - 거주지: 2026000453 '경기도 광명시 2년 이상 계속 거주자 → 기타지역(수도권)', 2026000414 '인천광역시 → 기타지역(수도권)'
실행: python -m tools.make_judge_cases   (사례를 바꾸면 다시 만들고, tools/judge_check.mjs 로 화면 엔진과 대조)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "judge" / "cases.json"

BASE100 = [7533763, 8802202, 9326985, 9906263, 10485541, 11064819]   # 2026000414 <표4> 100% (3인 이하~8인)


def amt(n: int, pct: int) -> int:
    b = BASE100[0] if n <= 3 else BASE100[n - 3] if n <= 8 else BASE100[5] + 579278 * (n - 8)
    return (b * pct + 50) // 100   # 공고문 표와 같은 반올림


def months(a: str, b: str) -> int:
    y1, m1, d1 = map(int, a.split("-")); y2, m2, d2 = map(int, b.split("-"))
    return (y2 - y1) * 12 + (m2 - m1) - (1 if d2 < d1 else 0)


def add_years(d: str, n: int) -> str:
    y, m, dd = d.split("-")
    return f"{int(y) + n}-{m}-{dd}"


# ---------- oracle: 가점 ([별표1]) ----------
def minor_months(since: str, birth: str, ref: str) -> int:
    """규칙 제10조⑥ (2024.7.1 시행): 가점 산정 시 '미성년자로서 가입한 2023년 12월 31일 이전의 기간(2년 초과 시 2년)과 2024년 1월 1일 이후의 기간의 합이
    5년을 초과하면 5년만 인정'. 성년 = 만 19세(민법). 성년 뒤 기간은 그대로. 반환: 인정 개월 수"""
    whole = months(since, ref)
    adult = add_years(birth, 19)
    if since >= adult:
        return whole
    end = min(adult, ref)
    before = max(0, months(since, min(end, "2024-01-01"))) if since < "2024-01-01" else 0
    after = max(0, months(max(since, "2024-01-01"), end)) if end > "2024-01-01" else 0
    minor = min(60, min(24, before) + after)
    if minor >= before + after:
        return whole
    return (months(adult, ref) if ref > adult else 0) + minor


def score(p: dict, ref: str) -> list:
    hh_any = p.get("hhHomes") in ("1", "2+")
    # 규칙 제53조 1·5·9호: 세대가 1채만 가졌고 그 집이 소형·저가, 20㎡ 이하, 상속 공유지분이면 무주택
    exc = p.get("hhHomes") != "2+" and p.get("ownExc") in ("small_apt", "small_villa", "tiny", "inherit")
    mine = not exc and (p.get("selfOwn") or (p.get("married") and p.get("spouseOwn")))
    other = not mine and not exc and ((p.get("household") == "parents" and p.get("parentsOwn") and not p.get("parents60")) or (hh_any and p.get("hhOwner") == "other"))
    who = not mine and not exc and hh_any and not p.get("hhOwner") and not (p.get("household") == "parents" and p.get("parentsOwn")) and not p.get("selfOwn") and not (p.get("married") and p.get("spouseOwn"))
    if mine or other:   # 별표1 가목 1) '세대원 모두 주택을 소유하지 않아야 한다' (60세 이상 직계존속 명의는 제53조제6호로 무주택)
        a = 0
    elif who:
        a = None
    else:
        thirty = add_years(p["birth"], 30)
        start = thirty
        if p.get("married") and p.get("marriedOn") and p["marriedOn"] < thirty:
            start = p["marriedOn"]
        if p.get("homeSoldOn") and p["homeSoldOn"] > start:
            start = p["homeSoldOn"]
        if p.get("married") and p.get("spouseSoldOn") and p["spouseSoldOn"] > start:   # 별표1 3) 신청자 또는 배우자
            start = p["spouseSoldOn"]
        if ref < start:
            a = 0
        else:
            y = months(start, ref) // 12
            a = 2 if y < 1 else min(32, 2 + 2 * y)
    b = min(35, 5 + 5 * p["dependents"])
    m = minor_months(p["acctSince"], p["birth"], ref) if p.get("birth") else months(p["acctSince"], ref)
    c = 1 if m < 6 else 2 if m < 12 else min(17, m // 12 + 2)
    if p.get("married") and p.get("spouseAcctSince"):
        sm = months(p["spouseAcctSince"], ref) / 2
        c = min(17, c + (1 if sm < 6 else 2 if sm < 12 else 3))
    return [a, b, c]


PUB = {"newborn": [("우선공급", 100, 120), ("일반공급", 140, 150), ("추첨", 140, 200)],
       "newlywed": [("우선공급", 100, 120), ("일반공급", 130, 140), ("추첨", 130, 200)],
       "first": [("우선공급", 100, 120), ("일반공급", 130, 140), ("추첨", 130, 200)],
       "multichild": [("우선공급 (배점순)", 120, 130), ("추첨", 120, 200)],
       "elder": [("우선공급", 120, 130), ("추첨", 120, 200)]}
MIN = {"newborn": [("우선공급", 130, None), ("일반공급", 160, None)],
       "first": [("우선공급", 130, None), ("일반공급", 160, None)],
       "newlywed": [("우선공급", 100, 120), ("일반공급", 140, 160)]}


def relax_add(p: dict) -> int | None:
    new = p.get("pregnant") is True or (p.get("youngestBirth") or "") >= "2023-03-28"
    if new:
        return 20 if (p.get("kidsMinor") or 0) >= 2 or (p.get("pregnant") is True and p.get("youngestBirth")) else 10
    if (p.get("kidsMinor") == 0 and p.get("pregnant") is False) or ((p.get("kidsMinor") or 0) > 0 and p.get("youngestBirth") and p.get("pregnant") is False):
        return 0
    return None


def relax_range(p: dict) -> tuple[int, int]:
    """[확실한 최소, 가능한 최대] 완화 %p. 공고문 「’23.3.28. 이후 출생한 자녀(태아 포함)가 1명만 있는 경우 10%p, 2명 이상(’23.3.28. 이후 출생한 자녀가 1명이고,
    ’23.3.27. 전 출생한 자녀가 있는 경우 포함)인 경우 20%p」(2026000409 13쪽). 만 19세 이상 자녀는 묻지 않으므로 +10%p 로 확인된 사람도 +20%p 일 수 있다."""
    a = relax_add(p)
    return (0, 20) if a is None else (0, 0) if a == 0 else (a, 20)


def sp_expect(pub: bool, t: str, p: dict, n: int) -> dict:
    y = p["hhIncomeYear"]
    mon = y * 10000 / 12
    dual = bool(p.get("married") and p.get("income", 0) > 0 and p.get("spouseIncome", 0) > 0)
    if pub:
        add = relax_add(p) or 0
        for nm, a, b in PUB[t]:
            if mon <= amt(n, (b if dual else a) + add):
                re_lim = {0: 21550, 10: 23705, 20: 25860}[add]
                car_lim = {0: 4542, 10: 4996, 20: 5451}[add]
                soft = relax_range(p)[1] > add   # 더 큰 완화가 가능하면 <표3> 최대(258,600천원·54,510천원) 안쪽은 '확인 필요'
                re_v, car_v = p.get("realEstate", 0), p.get("carValue", 0)
                if (re_v > re_lim and not (soft and re_v <= 25860)) or (car_v > car_lim and not (soft and car_v <= 5451)):
                    return {"s": "fail"}
                if re_v > re_lim or car_v > car_lim:
                    return {"s": "warn"}
                return {"s": "ok", "stage": nm}
        mx = PUB[t][-1][2 if dual else 1]
        if relax_range(p)[1] > add and mon <= amt(n, mx + 20):
            return {"s": "warn"}
        return {"s": "fail"}
    st = MIN[t]
    selfm, spm = p.get("income", 0) * 10000 / 12, p.get("spouseIncome", 0) * 10000 / 12
    for nm, a, b in st:
        lim = b if (dual and b) else a
        ok = mon <= amt(n, lim)
        if ok and dual and t == "newlywed":
            ok = min(selfm, spm) <= amt(n, a)
        if ok:
            return {"s": "ok", "stage": nm}
    return {"s": "ok", "stage": "추첨"} if p.get("realEstate", 0) <= 33100 else {"s": "fail"}


# 공공임대 특별공급 (2026000307 군포대야미 A-1, 기능 rental_special) — 원문을 손으로 옮긴 표. 화면 코드와 따로.
#  <표5> 가구원수별 퍼센트 금액 (1인~8인, 원). 200% 는 원문 표4 금액이 100%의 2배(3인 16,336,858 = 8,168,429 × 2)
R_T5 = {100: [3813363, 5866270, 8168429, 8802202, 9326985, 9906263, 10485541, 11064819],
        110: [4194699, 6452897, 8985272, 9682422, 10259684, 10896889, 11534095, 12171301],
        120: [4576036, 7039524, 9802115, 10562642, 11192382, 11887516, 12582649, 13277783],
        130: [4957372, 7626151, 10618958, 11442863, 12125081, 12878142, 13631203, 14384265],
        140: [5338708, 8212778, 11435801, 12323083, 13057779, 13868768, 14679757, 15490747],
        150: [5720045, 8799405, 12252644, 13203303, 13990478, 14859395, 15728312, 16597229],
        160: [6101381, 9386032, 13069486, 14083523, 14923176, 15850021, 16776866, 17703710]}
R_T5[200] = [2 * v for v in R_T5[100]]
r_amt = lambda pct, n: R_T5[pct][n - 1]
#  <표4> (표4-3) 3인 이상 [단계, 비율, 외벌이 %, 맞벌이 %] · (표4-2) 2인 [외벌이 %, 맞벌이 %]
R_SP = {"multichild": ([("우선공급 (배점순)", 90, 120, 130), ("추첨", 10, 120, 200)], None),
        "elder": ([("우선공급", 90, 120, 130), ("추첨", 10, 120, 200)], [(130, 140), (130, 200)]),
        "first": ([("우선공급", 70, 100, 120), ("일반공급", 20, 130, 140), ("추첨", 10, 130, 200)], [(110, 130), (140, 150), (140, 200)]),
        "newlywed": ([("우선공급", 70, 100, 120), ("일반공급", 20, 130, 140), ("추첨", 10, 130, 200)], [(110, 130), (140, 150), (140, 200)]),
        "newborn": ([("우선공급", 70, 100, 120), ("일반공급", 20, 140, 150), ("추첨", 10, 140, 200)], [(110, 130), (150, 160), (150, 200)])}
R_KID = {"옛자녀": {"youngestBirth": "2019-01-01"}, "신생아1": {"youngestBirth": "2025-06-01"},
         "새2명옛": {"kidsMinor": 2, "kidsOnDeed": 2, "hhSize": 4, "dependents": 3, "youngestBirth": "2019-01-01"},
         "2인": {"dependents": 1, "kidsMinor": 0, "kidsOnDeed": 0, "youngestBirth": "", "pregnant": False, "hhSize": 2}}


def rental_sp_expect(t: str, p: dict, n: int) -> dict:
    """2026000307: 단계별 소득 기준(첫 단계부터) + 총자산 362,000천원(출산 1명 397,000 · 2명 이상 431,000천원). 소득이 마지막 단계도 넘으면
    출산가구 완화(<표5>, +10·20%p) 가능성이 있으면 '확인 필요', 아니면 '불가'. 총자산은 부동산+금융+기타+자동차−부채."""
    mon = p["hhIncomeYear"] * 10000 / 12
    dual = bool(p.get("married") and p.get("income", 0) > 0 and p.get("spouseIncome", 0) > 0) and n > 1
    names = [x[0] for x in R_SP[t][0]]
    pcts = R_SP[t][1] if n == 2 else [(a, b) for _, _, a, b in R_SP[t][0]]
    stage = next((nm for nm, (a, b) in zip(names, pcts) if mon <= r_amt(b if dual else a, n)), None)
    tot = sum(p.get(k) or 0 for k in ("realEstate", "carValue", "cash", "liquid", "deposit", "townInsurance", "townFinOther", "townOtherAsset")) - (p.get("townDebt") or 0)
    ra = relax_add(p)
    if tot > 36200:
        if ra == 0 or tot > 43100:
            return {"s": "fail"}
        if not (ra and tot <= 39700):
            return {"s": "warn"}
    if stage is None:
        top = pcts[-1][1 if dual else 0]
        return {"s": "warn"} if ra != 0 and mon <= r_amt(100, n) * (top + 20) / 100 else {"s": "fail"}
    return {"s": "ok", "stage": stage}


def main() -> None:
    cases = []
    add = lambda **c: cases.append(c)

    # ---------- 1) 가점 45건 (광명 시티프라디움 2026000453, 공고일 2026-09-18) ----------
    REF = "2026-09-18"
    base = {"selfOwn": False, "married": False, "spouseOwn": False, "dependents": 0, "acctSince": "2020-01-01", "birth": "1990-01-01"}
    grid = [
        {"birth": "1996-09-19"},                                   # 만 30세 전날 → 미혼 0점
        {"birth": "1996-09-18"},                                   # 공고일에 만 30세 → 1년 미만 2점
        {"birth": "1995-09-18"},                                   # 정확히 1년 → 4점
        {"birth": "1995-09-19"},                                   # 1년 하루 모자람 → 2점
        {"birth": "1980-01-01"},                                   # 16년 → 32점(최대)
        {"birth": "1981-09-18"},                                   # 15년 → 32점
        {"birth": "1981-09-19"},                                   # 14년 → 30점
        {"birth": "1998-01-01", "married": True, "marriedOn": "2022-01-01"},   # 30세 전 혼인 → 혼인일부터 4년 → 10점
        {"birth": "1998-01-01", "married": True, "marriedOn": "2026-09-19"},   # 혼인이 공고일 뒤 → 0점
        {"birth": "1990-01-01", "married": True, "marriedOn": "2021-01-01"},   # 30세 뒤 혼인 → 30세(2020-01-01)부터 6년 → 14
        {"birth": "1985-01-01", "homeSoldOn": "2024-01-01"},       # 처분일부터 2년 → 6점
        {"birth": "1985-01-01", "homeSoldOn": "2026-01-01"},       # 처분일부터 1년 미만 → 2점
        {"birth": "1985-01-01", "selfOwn": True},                  # 지금 집 있음 → 0점
        {"birth": "1985-01-01", "married": True, "marriedOn": "2015-01-01", "spouseOwn": True},   # 배우자 집 → 0
        {"birth": "1985-01-01", "married": True, "marriedOn": "2015-01-01", "spouseOwn": False},  # 30세(2015-01-01)=혼인 → 11년 → 24
    ]
    deps = [0, 1, 2, 3, 6, 7]
    accts = ["2026-04-01", "2026-03-18", "2025-09-19", "2025-09-18", "2024-09-18", "2011-09-18", "2005-01-01"]
    i = 0
    for g in grid:
        p = dict(base, **g)
        add(id=f"score-{i:02d}", fn="score", listing="2026000453-059.9742A", profile=p, expect={"parts": score(p, REF)},
            basis="2026000103 가점 산정기준 [별표1]의 2 나목 — 무주택기간"); i += 1
    for d in deps:
        p = dict(base, dependents=d)
        add(id=f"score-{i:02d}", fn="score", listing="2026000453-059.9742A", profile=p, expect={"parts": score(p, REF)},
            basis="2026000103 가점표 — 부양가족 0명 5점, 1명마다 5점, 6명 이상 35점"); i += 1
    for a in accts:
        p = dict(base, acctSince=a)
        add(id=f"score-{i:02d}", fn="score", listing="2026000453-059.9742A", profile=p, expect={"parts": score(p, REF)},
            basis="2026000103 가점표 — 입주자저축 가입기간 6개월 미만 1점 … 15년 이상 17점"); i += 1
    for sa in ["2026-01-01", "2025-09-18", "2025-03-18", "2024-09-18", "2010-01-01"]:
        for own in ["2020-01-01", "2012-01-01"]:
            p = dict(base, married=True, marriedOn="2019-01-01", acctSince=own, spouseAcctSince=sa)
            add(id=f"score-{i:02d}", fn="score", listing="2026000453-059.9742A", profile=p, expect={"parts": score(p, REF)},
                basis="2026000103 배우자 통장 — 가입기간 50%의 점수(6개월 미만 1·1년 미만 2·1년 이상 3), 합계 최대 17점"); i += 1
    for d, a, s in [(3, "2010-01-01", None), (2, "2018-05-05", "2015-05-05"), (4, "2014-02-28", "2026-02-28")]:
        p = dict(base, birth="1984-02-29", married=True, marriedOn="2012-03-01", dependents=d, acctSince=a, spouseAcctSince=s)
        add(id=f"score-{i:02d}", fn="score", listing="2026000453-059.9742A", profile=p, expect={"parts": score(p, REF)},
            basis="2026000103 가점표 — 세 항목 합계 (윤년 생일 포함)"); i += 1

    # ---------- 2) 공공 특별공급 소득 단계 (인천계양 A6 2026000414, 3인 가구) ----------
    pub_base = {"homeSido": "인천", "homeSigun": "계양구", "sidoOwnSince": "2015-01-01", "sidoSince": "2015-01-01", "areaSince": "2015-01-01",
                "household": "head", "headSince": "2015-01-01", "selfOwn": False, "married": True, "marriedOn": "2023-05-01", "spouseOwn": False,
                "acctType": "all", "acctSince": "2014-01-01", "acctAmount": 1500, "acctCount": 30, "acctPaid": 1500, "hhHomes": "0",
                "win5y": False, "recentWin": False, "everWin": "none", "birth": "1990-03-01", "dependents": 2, "kidsMinor": 1, "youngestBirth": "2025-06-01",
                "pregnant": False, "hhSize": 3, "kidsOnDeed": 1, "eldersOnDeed": 0, "spouseIncome": 0, "realEstate": 0, "carValue": 1000,
                "hhNeverOwned": True, "taxYears5": True, "elder65": True}
    kidvars = {"신생아1": {"youngestBirth": "2025-06-01"}, "옛자녀": {"youngestBirth": "2019-01-01"}, "새2명": {"kidsMinor": 2, "kidsOnDeed": 2, "hhSize": 4},
               "모름": {"kidsMinor": None, "youngestBirth": "", "pregnant": None, "kidsOnDeed": 1}}
    i = 0
    for t in ["newborn", "newlywed", "first", "multichild", "elder"]:
        for pct in ([100, 140] if t in ("newborn", "newlywed", "first") else [120]):
            for kv in (["신생아1", "옛자녀"] if t != "multichild" else ["새2명"]):
                for side in ("le", "gt"):
                    p = dict(pub_base, **kidvars[kv])
                    if t == "multichild":
                        p.update(kidsMinor=2, kidsOnDeed=2, hhSize=4, youngestBirth="2025-06-01")
                    if t == "elder":
                        p.update(eldersOnDeed=None)   # 소득 단계만 보는 사례 — 기본 프로필의 '같은 등본 부모 0명'은 노부모 요건과 맞지 않아 모름으로 둠
                    if t == "newborn" and kv == "옛자녀":
                        continue   # 2세 미만 자녀가 없으면 신생아 대상이 아님
                    n = 1 + 1 + p["kidsOnDeed"]
                    radd = relax_add(p) or 0
                    lim = amt(n, pct + radd)
                    y = (lim * 12) // 10000 + (0 if side == "le" else 1)
                    p.update(hhIncomeYear=y, income=y)
                    add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type=t, profile=p, expect=sp_expect(True, t, p, n),
                        basis=f"2026000414 {t} 소득 단계 {pct}%(+출산 {radd}%p) {'이하' if side == 'le' else '초과(1만원)'}"); i += 1
    for kv, re_v, car in [("신생아1", 23705, 1000), ("신생아1", 23706, 1000), ("새2명", 25860, 1000), ("옛자녀", 21551, 1000),
                          ("신생아1", 0, 4996), ("신생아1", 0, 4997), ("옛자녀", 0, 4542), ("옛자녀", 0, 4543)]:
        p = dict(pub_base, **kidvars[kv], hhIncomeYear=5000, income=5000, realEstate=re_v, carValue=car)
        n = 1 + 1 + p["kidsOnDeed"]
        add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type="first", profile=p, expect=sp_expect(True, "first", p, n),
            basis="2026000414 <표2>·<표3> 부동산 215,500·237,050·258,600천원, 자동차 45,420·49,960·54,510천원"); i += 1
    for kv, pct in [("모름", 141), ("모름", 151), ("모름", 160), ("모름", 161)]:
        p = dict(pub_base, **kidvars[kv])
        n = 3
        y = (amt(n, pct) * 12) // 10000
        p.update(hhIncomeYear=y, income=y)
        add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type="first", profile=p, expect=sp_expect(True, "first", p, n),
            basis="2026000414 출산가구 완화 — 자녀 정보가 없으면 +20%p 안쪽은 '확인 필요'"); i += 1
    mxf = PUB["first"][-1][1]
    for pct in [mxf + 10, mxf + 11, mxf + 20, mxf + 21]:   # 신생아 1명(+10%p 확인)·만 19세 이상 자녀 모름 → +10~+20%p 사이는 '확인 필요', 넘으면 '불가'
        p = dict(pub_base, **kidvars["신생아1"])
        y = (amt(3, pct) * 12) // 10000 if pct in (mxf + 10, mxf + 20) else (amt(3, pct - 1) * 12) // 10000 + 1
        p.update(hhIncomeYear=y, income=y)
        add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type="first", profile=p, expect=sp_expect(True, "first", p, 3),
            basis="2026000414 13쪽 출산가구 완화 '2명 이상(’23.3.28. 이후 출생 자녀 1명이고 ’23.3.27. 전 출생 자녀가 있는 경우 포함) 20%p' — 신생아 1명은 +10%p 확정, +20%p 가능"); i += 1
    for re_v in (25860, 25861):
        p = dict(pub_base, **kidvars["신생아1"], hhIncomeYear=5000, income=5000, realEstate=re_v, carValue=1000)
        add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type="first", profile=p, expect=sp_expect(True, "first", p, 3),
            basis="2026000414 <표3> 2명 이상 부동산 258,600천원 — 신생아 1명은 그 안쪽 '확인 필요', 넘으면 '불가'"); i += 1
    for dual_pct in [119, 121, 149, 151, 199, 201]:
        p = dict(pub_base)
        lim = amt(3, dual_pct)
        y = (lim * 12) // 10000
        p.update(hhIncomeYear=y, income=y // 2, spouseIncome=y - y // 2, youngestBirth="2019-01-01")
        add(id=f"pub-{i:03d}", fn="sp", listing="2026000414-059.8400A", type="newlywed", profile=p, expect=sp_expect(True, "newlywed", p, 3),
            basis=f"2026000414 신혼부부 맞벌이 기준(120/140/200%) — 소득 {dual_pct}% 근처"); i += 1

    # ---------- 3) 민영 특별공급 소득 단계 (광명 2026000453) ----------
    min_base = dict(pub_base, homeSido="경기", homeSigun="광명시", acctCount=None, acctPaid=None, carValue=None)
    i = 0
    for t, pcts in [("newborn", [130, 160]), ("first", [130, 160]), ("newlywed", [100, 140])]:
        for pct in pcts:
            for side in ("le", "gt"):
                p = dict(min_base)
                y = (amt(3, pct) * 12) // 10000 + (0 if side == "le" else 1)
                p.update(hhIncomeYear=y, income=y)
                add(id=f"min-{i:03d}", fn="sp", listing="2026000453-059.9742A", type=t, profile=p, expect=sp_expect(False, t, p, 3),
                    basis=f"2026000453 {t} 소득구분 {pct}% {'이하' if side == 'le' else '초과'}"); i += 1
    for dual_pct, split in [(119, 0.5), (121, 0.5), (119, 0.95), (159, 0.5), (161, 0.5)]:
        p = dict(min_base)
        y = (amt(3, dual_pct) * 12) // 10000
        a = int(y * split)
        p.update(hhIncomeYear=y, income=a, spouseIncome=y - a)
        add(id=f"min-{i:03d}", fn="sp", listing="2026000453-059.9742A", type="newlywed", profile=p, expect=sp_expect(False, "newlywed", p, 3),
            basis="2026000453 신혼부부 맞벌이 120%·160%, 부부 중 1인 100%·140% 이하"); i += 1
    for re_v in [33100, 33101]:
        p = dict(min_base)
        y = (amt(3, 170) * 12) // 10000
        p.update(hhIncomeYear=y, income=y, realEstate=re_v)
        add(id=f"min-{i:03d}", fn="sp", listing="2026000453-059.9742A", type="first", profile=p, expect=sp_expect(False, "first", p, 3),
            basis="2026000453 추첨공급 '160% 초과하나 부동산가액 3억 3,100만원 이하'"); i += 1

    # ---------- 4) 청약통장 1순위 (광명 2026000453: 투기과열 24개월, 전용 59.97㎡ → 85㎡ 이하 예치금) ----------
    i = 0
    for since, sido, amount in [("2024-09-18", "경기", 200), ("2024-09-19", "경기", 200), ("2014-01-01", "경기", 199), ("2014-01-01", "서울", 299),
                                ("2014-01-01", "서울", 300), ("2014-01-01", "인천", 250), ("2014-01-01", "인천", 249), ("2014-01-01", "부산", 300),
                                ("2014-01-01", "대전", 249), ("2014-01-01", "세종", 200), ("2026-03-18", "경기", 1500), ("2014-01-01", "강원", 200)]:
        p = {"acctType": "all", "acctSince": since, "acctAmount": amount, "homeSido": sido, "household": "head"}
        need = 300 if sido in ("서울", "부산") else 250 if sido in ("인천", "대구", "광주", "대전", "울산") else 200
        add(id=f"acct-{i:02d}", fn="acct", listing="2026000453-059.9742A", profile=p,
            expect={"가입기간": "ok" if months(since, REF) >= 24 else "fail", "예치금": "ok" if amount >= need else "fail"},
            basis="2026000453 1순위 '가입기간 24개월 경과 + 지역별·면적별 예치금(85㎡ 이하 300·250·200만원)'"); i += 1

    # ---------- 5) 공공 일반공급 60㎡ 이하 소득·자산 (인천계양 A6 2026000414) ----------
    i = 0
    for pct, dual, kv in [(100, False, "옛자녀"), (101, False, "옛자녀"), (140, True, "옛자녀"), (141, True, "옛자녀"), (200, True, "옛자녀"),
                          (201, True, "옛자녀"), (109, False, "신생아1"), (111, False, "모름"),
                          (111, False, "신생아1"), (121, False, "신생아1"), (119, False, "새2명"), (121, False, "새2명")]:
        p = dict(pub_base, **kidvars[kv])
        n3 = 1 + 1 + p["kidsOnDeed"]   # 본인·배우자·같은 등본 자녀 (공고문 가구원수 산정)
        y = (amt(n3, pct) * 12) // 10000 if pct in (100, 140, 200) else (amt(n3, pct - 1) * 12) // 10000 + 1
        p.update(hhIncomeYear=y, income=(y // 2 if dual else y), spouseIncome=(y - y // 2 if dual else 0))
        mon = y * 10000 / 12
        cap, pri = (200, 140) if dual else (100, 100)
        lo, hi = relax_range(p)
        if mon <= amt(n3, cap) or (lo and mon <= amt(n3, cap + lo)):
            exp = "ok"
        elif mon > amt(n3, cap + hi):
            exp = "fail"
        else:
            exp = "warn"
        add(id=f"pubgen-{i:02d}", fn="pubgen", listing="2026000414-059.8400A", profile=p, expect={"소득": exp},
            basis="2026000414 일반공급(60㎡ 이하) '월평균소득 100% 이하(맞벌이 200%)', 출산가구 +10/20%p"); i += 1

    # ---------- 6) 신혼희망타운 소득·총자산 (인천계양 A17 2026820010) ----------
    town_base = dict(pub_base, youngestBirth="2019-01-01", cash=0, liquid=0, deposit=0, townInsurance=0, townFinOther=0, townOtherAsset=0, townDebt=0)
    i = 0
    for pct, dual in [(130, False), (131, False), (140, True), (141, True), (200, True), (201, True)]:
        p = dict(town_base)
        y = (amt(3, pct) * 12) // 10000 if pct in (130, 140, 200) else (amt(3, pct - 1) * 12) // 10000 + 1
        p.update(hhIncomeYear=y, income=(y // 2 if dual else y), spouseIncome=(y - y // 2 if dual else 0))
        cap = 200 if dual else 130
        add(id=f"town-{i:02d}", fn="town", listing="2026820010-055.8800B", profile=p, expect={"소득": "ok" if y * 10000 / 12 <= amt(3, cap) else "fail"},
            basis="2026820010 신청자격 ③ '130%(단, 본인 및 배우자가 모두 소득이 있는 경우에는 200%) 이하' (1·2단계 우선공급은 130%/140%)"); i += 1
    for re_v, cash, debt, kv, exp in [(20000, 16200, 0, "옛자녀", "ok"), (20000, 16201, 0, "옛자녀", "fail"), (30000, 10000, 3800, "옛자녀", "ok"),
                                      (30000, 9700, 0, "신생아1", "ok"), (30000, 9701, 0, "신생아1", "warn"), (0, 0, 5000, "옛자녀", "ok")]:
        p = dict(town_base, **kidvars[kv], hhIncomeYear=5000, income=5000, realEstate=re_v, cash=cash, townDebt=debt, carValue=0)
        add(id=f"town-{i:02d}", fn="town", listing="2026820010-055.8800B", profile=p, expect={"총자산": exp},
            basis="2026820010 <표3> 총자산(부동산+금융+기타+자동차−부채) 362,000천원, 출산 1명 397,000천원 (2명 이상 여부는 따로 묻지 않아 넘으면 확인 필요)"); i += 1

    # ---------- 6-2) 무주택 세대 (공공분양 인천계양 A6 2026000414 — '무주택세대구성원') ----------
    # 규칙 제2조제4호 무주택세대구성원 = 세대원 전원 무주택, 제53조제6호 60세 이상 직계존속(배우자 직계존속 포함) 소유는 무주택으로 봄.
    # 세대 주택이 있다고 했는데 본인·배우자·부모님 명의가 아니면 누구 것인지 몰라 '확인 필요'
    i = 0
    for over, exp in [({"hhHomes": "0"}, "ok"),
                      ({"hhHomes": "1"}, "warn"),
                      ({"hhHomes": "2+"}, "warn"),
                      ({"hhHomes": "1", "household": "parents", "parentsOwn": True, "parents60": True}, "ok"),
                      ({"hhHomes": "1", "household": "parents", "parentsOwn": True, "parents60": False}, "fail"),
                      ({"hhHomes": "1", "selfOwn": True}, "fail"),
                      ({"hhHomes": "1", "hhOwner": "parent60"}, "ok"),
                      ({"hhHomes": "1", "hhOwner": "other"}, "fail")]:
        p = dict(pub_base, **over)
        add(id=f"home-{i:02d}", fn="home", listing="2026000414-059.8400A", profile=p, expect={"s": exp},
            basis="주택공급에 관한 규칙 제2조제4호·제53조제6호, 2026000414 '무주택세대구성원'"); i += 1
    for lid, over in [("2026000453-059.9742A", {"hhHomes": "1"}), ("2026000443-059.9986A", {"hhHomes": "1"})]:
        p = dict(pub_base, **over)   # 민영 일반공급: 1순위는 유주택 세대도 가능 (제28조①1호, 규제지역 2주택 이상만 제외) → 무주택 항목 자체는 '가능'
        add(id=f"home-{i:02d}", fn="home", listing=lid, profile=p, expect={"s": "ok"},
            basis=f"{lid.split('-')[0]} 민영 1순위 — 유주택 세대도 신청(추첨제), 규칙 제28조①1호"); i += 1

    # ---------- 6-2b) 특별공급의 무주택 (세대 주택 명의) — 규칙 제53조 단서: 60세 이상 직계존속 예외는 노부모부양(제46조·공공 별표6 2라)에 적용 안 함 ----------
    i = 0
    for t_, over, exp in [("first", {}, "ok"), ("first", {"hhHomes": "1"}, "warn"), ("first", {"hhHomes": "1", "hhOwner": "parent60", "realEstate": 20000}, "ok"),
                          ("first", {"hhHomes": "1", "hhOwner": "other"}, "fail"), ("elder", {"hhHomes": "1", "hhOwner": "parent60", "eldersOnDeed": None}, "fail")]:
        p = dict(pub_base, **{**dict(hhIncomeYear=3000, income=3000, realEstate=0, carValue=1000, youngestBirth="2019-01-01"), **over})
        add(id=f"sphome-{i:02d}", fn="sp", listing="2026000414-059.8400A", type=t_, profile=p, expect={"s": exp},
            basis="규칙 제2조제4호 무주택세대구성원·제53조제6호(60세 이상 직계존속 소유는 무주택, 노부모부양 특별공급 제외), 2026000414 특별공급 '무주택세대구성원'"); i += 1

    # ---------- 6-3) 노부모부양 '같은 세대별 주민등록표등본에 등재되어 있는 경우에 한함' (민영 광명 2026000453) ----------
    i = 0
    for over, exp in [({"elder65": True, "eldersOnDeed": 1, "elders1y": True, "hhSize": 4}, "ok"), ({"elder65": True, "eldersOnDeed": 0}, "warn"), ({"elder65": False}, "fail")]:
        p = dict(pub_base, homeSido="경기", homeSigun="광명시", **over)
        add(id=f"elder-{i:02d}", fn="sp", listing="2026000453-059.9742A", type="elder", profile=p, expect={"s": exp},
            basis="2026000453 노부모부양 '만65세 이상의 직계존속을 3년 이상 계속하여 부양(같은 세대별 주민등록표등본에 등재되어 있는 경우에 한함)'"); i += 1

    # ---------- 6-4) 2순위 (광명 2026000453 투기과열 — 세대원은 1순위 불가) ----------
    # 2026000453 '2순위 : 예치금액과 관계없이 청약예금·청약부금·주택청약종합저축에 가입한 분', 규칙 제28조①2호 '제2순위 : 제1순위에 해당하지 아니하는 자'.
    # 통장 가입 → 2순위만(r2), 통장 정보 없음 → 확인 필요(unsure), 통장 없음 → 불가(no)
    i = 0
    for over, exp in [({"acctType": "all"}, "r2"), ({"acctType": "", "acctSince": "", "acctAmount": 0}, "unsure"), ({"acctType": "none"}, "no")]:
        p = dict(pub_base, homeSido="경기", homeSigun="광명시", household="parents", parentsOwn=False, headSince="", **over)
        add(id=f"rank2-{i:02d}", fn="bucket", listing="2026000453-059.9742A", profile=p, expect={"b": exp},
            basis="2026000453 '2순위 : 예치금액과 관계없이 청약예금·청약부금·주택청약종합저축에 가입한 분' · 투기과열 1순위 세대주 요건"); i += 1

    # ---------- 7) 거주지 (광명 2026000453 · 인천계양 A6 2026000414) ----------
    i = 0
    for lid, sido, sigun, since, exp in [
        ("2026000453-059.9742A", "경기", "광명시", "2015-01-01", ["ok", "해당지역"]),
        ("2026000453-059.9742A", "경기", "광명시", "2024-09-18", ["ok", "해당지역"]),
        ("2026000453-059.9742A", "경기", "광명시", "2024-09-19", ["ok", "기타지역"]),
        ("2026000453-059.9742A", "서울", "", "2015-01-01", ["ok", "기타지역"]),
        ("2026000453-059.9742A", "경기", "수원시", "2015-01-01", ["ok", "기타지역"]),
        ("2026000453-059.9742A", "부산", "", "2015-01-01", ["fail", "신청 불가"]),
        ("2026000414-059.8400A", "인천", "계양구", "2026-08-30", ["ok", "해당지역"]),
        ("2026000414-059.8400A", "서울", "", "2015-01-01", ["ok", "기타지역"]),
        ("2026000414-059.8400A", "경기", "부천시", "2015-01-01", ["ok", "기타지역"]),
        ("2026000414-059.8400A", "충남", "천안시", "2015-01-01", ["fail", "신청 불가"])]:
        p = {"homeSido": sido, "homeSigun": sigun, "sidoOwnSince": since, "sidoSince": since, "areaSince": since}
        add(id=f"res-{i:02d}", fn="residence", listing=lid, profile=p, expect={"s": exp[0], "v": exp[1]},
            basis="해당지역 2년 이상(광명)·인천 거주(기간 요건 없음) → 기타지역 수도권 → 그 밖은 신청 불가 (2026000453·414 신청자격)"); i += 1

    # ---------- 8) 2026-10-01 판정엔진 감사에서 고친 규칙 (경계값 포함) ----------
    REF453, REF414, REF409 = "2026-09-18", "2026-08-26", "2026-08-26"
    gw = dict(pub_base, homeSido="경기", homeSigun="광명시")
    i = 0
    def g(**c):
        nonlocal i
        add(id=f"audit-{i:03d}", **c); i += 1
    # 가점: 세대원 명의 주택 (별표1 가목 1), 미성년 가입기간 (제10조⑥)
    sb = {"selfOwn": False, "married": False, "spouseOwn": False, "dependents": 0, "acctSince": "2020-01-01", "birth": "1985-01-01", "household": "head"}
    for over in [{"hhHomes": "1", "hhOwner": "other"}, {"hhHomes": "1", "hhOwner": "parent60"}, {"household": "parents", "parentsOwn": True, "parents60": False},
                 {"household": "parents", "parentsOwn": True, "parents60": True}, {"hhHomes": "0"}]:
        pp = dict(sb, **over)
        g(fn="score", listing="2026000453-059.9742A", profile=pp, expect={"parts": score(pp, REF453)}, basis="별표1 가목 1) '입주자모집공고일 현재 세대원 모두 주택을 소유하지 않아야 한다', 제53조제6호")
    for birth, since in [("2001-03-01", "2011-01-01"), ("2007-01-01", "2010-01-01"), ("2005-05-05", "2023-01-01"), ("1990-01-01", "2005-01-01"),
                         ("2006-01-01", "2020-01-01"), ("2004-09-18", "2015-09-18"), ("2010-01-01", "2012-06-01")]:
        pp = dict(sb, birth=birth, acctSince=since)
        g(fn="score", listing="2026000453-059.9742A", profile=pp, expect={"parts": score(pp, REF453)},
          basis="규칙 제10조⑥ 미성년 가입기간: 2023.12.31 이전 2년 한도 + 2024.1.1 이후 합계 5년 한도 (성년 뒤 기간은 그대로)")
    # 재당첨 제한 (제54조① — 비규제 민영 제외)
    for lid, over, exp in [("2026000443-059.9986A", {"recentWin": True, "everWin": "yes", "win5y": True}, "ok"),
                           ("2026000453-059.9742A", {"recentWin": True, "everWin": "yes", "win5y": True}, "fail"),
                           ("2026000414-059.8400A", {"recentWin": True, "everWin": "yes", "win5y": True}, "fail"),
                           ("2026000414-059.8400A", {"everWin": None, "win5y": None, "recentWin": False}, "ok"),   # 사용자 방침(2026-10-01): 당첨 이력을 비우면 없음
                           ("2026000443-059.9986A", {"everWin": None, "recentWin": False}, "ok")]:
        g(fn="item", item="재당첨 제한 (내 이력)", listing=lid, profile=dict(gw, **over), expect={"s": exp},
          basis="규칙 제54조① '다른 분양주택(…투기과열지구 및 청약과열지역이 아닌 지역에서 공급되는 민영주택은 제외)'")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", recentWin=True, everWin="yes", win5y=True),
      expect={"s": "fail"}, basis="규칙 제54조① 재당첨 제한은 특별공급에도 적용 (2026000414 특별공급 유의사항)")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", recentWin=False, everWin="yes", win5y=False),
      expect={"s": "warn"}, basis="규칙 제55조 특별공급은 한 차례 — 예전 당첨 종류를 묻지 않아 확인 필요")
    # 공공 생애최초·노부모는 1순위 (제43조①1호·제46조) — 투기과열 변형 공고(테스트용)에서는 24회·세대주
    for over, exp in [({"acctCount": 20}, "fail"), ({"acctCount": 24}, "ok"), ({"acctCount": 24, "household": "parents", "parentsOwn": False}, "fail"), ({"acctCount": 24, "acctPaid": 599}, "fail")]:
        g(fn="sp", type="first", listing="2026000414-REG", profile=dict(pub_base, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", **over), expect={"s": exp},
          basis="규칙 제43조①1호 '제27조제1항의 1순위 무주택세대구성원 + 저축액 600만원', 제27조①1다 투기과열 24개월·24회·세대주 (공공 변형 공고)")
    # 신혼부부 (공공 2026000409 '혼인 7년 이내이거나 6세 이하 자녀', 예비신혼·한부모 / 민영 혼인 7년)
    nb = dict(pub_base, hhIncomeYear=3000, income=3000)
    for over, exp in [({"marriedOn": "2015-01-01", "youngestBirth": "2020-01-01"}, "ok"), ({"marriedOn": "2015-01-01", "youngestBirth": "2019-08-26"}, "fail"),
                      ({"marriedOn": "2015-01-01", "youngestBirth": "2019-08-27"}, "ok"), ({"marriedOn": "2019-08-26", "youngestBirth": "2010-01-01"}, "ok"),
                      ({"marriedOn": "2019-08-25", "youngestBirth": "2010-01-01"}, "fail"), ({"married": False, "marriedOn": "", "townType": "pre"}, "warn"),
                      ({"married": False, "marriedOn": "", "townType": "single", "youngestBirth": "2021-01-01"}, "ok"),
                      ({"married": False, "marriedOn": "", "townType": "single", "youngestBirth": "2015-01-01"}, "fail"),
                      ({"married": False, "marriedOn": "", "townType": "none"}, "fail"), ({"married": False, "marriedOn": "", "townType": None}, "fail")]:   # 사용자 방침: 예비신혼·한부모를 안 고르면 해당 없음
        g(fn="sp", type="newlywed", listing="2026000409-059.9200A", profile=dict(nb, **over), expect={"s": exp},
          basis="2026000409 신혼부부 '혼인기간이 7년 이내(2019.08.26.~2026.08.26.)이거나 6세 이하(만 7세 미만) 자녀', 예비신혼부부(혼인으로 구성될 세대 — 예비 배우자 정보 미입력), 한부모가족")
    for mo, exp in [("2019-09-18", "ok"), ("2019-09-17", "fail")]:
        g(fn="sp", type="newlywed", listing="2026000453-059.9742A", profile=dict(gw, marriedOn=mo, hhIncomeYear=3000, income=3000), expect={"s": exp},
          basis="2026000453 민영 신혼부부 '혼인기간 7년 이내' — 공고일 2026.09.18 기준 경계")
    # 신생아 '2세 미만(공고일 기준 2년 이내 출생)' 경계와 임신 여부 미입력
    for yb, preg, exp in [("2024-09-18", False, "ok"), ("2024-09-17", False, "fail"), ("2024-09-17", None, "fail"), ("2024-09-17", True, "ok")]:   # 사용자 방침: 임신 여부를 비우면 아니요
        g(fn="sp", type="newborn", listing="2026000453-059.9742A", profile=dict(gw, youngestBirth=yb, pregnant=preg, hhIncomeYear=3000, income=3000), expect={"s": exp},
          basis="2026000453 신생아 '입주자모집공고일 현재 2세 미만(2024.09.18. 이후 출생)' — 임신 중이면 태아로 해당")
    # 생애최초: 미혼·무자녀는 민영 추첨만(단독세대 60㎡ 이하), 공공은 불가 (제43조①③, 2026000409)
    fb = dict(gw, married=False, marriedOn="", kidsMinor=0, kidsOnDeed=0, youngestBirth="", pregnant=False, spouseIncome=0, hhIncomeYear=3000, income=3000)
    g(fn="sp", type="first", listing="2026000453-059.9742A", profile=dict(fb, household="head", hhSize=1), expect={"s": "ok", "stage": "추첨 (미혼·무자녀)"},
      basis="규칙 제43조③2나·④ 미혼·무자녀는 3호(추첨) 물량, 단독세대주 전용 60㎡ 이하 — 59.97㎡")
    g(fn="sp", type="first", listing="2026000103-084.0000A", profile=dict(fb, homeSigun="성남시", household="head", hhSize=1), expect={"s": "fail"},
      basis="규칙 제43조③ 후단 '단독세대주…에게는 주거전용면적이 60제곱미터 이하인 주택으로만' — 84㎡")
    g(fn="sp", type="first", listing="2026000103-084.0000A", profile=dict(fb, homeSigun="성남시", household="parents", parentsOwn=False, parents60=False, hhSize=3), expect={"s": "fail"},
      basis="2026000103 투기과열 생애최초 '1순위' — 규제지역 1순위는 세대주 (규칙 제28조①1다·제43조③1호)")
    g(fn="sp", type="first", listing="2026000426-084.8786A", profile=dict(fb, homeSido="충남", homeSigun="천안시", household="parents", parentsOwn=False, parents60=False, hhSize=3), expect={"s": "ok", "stage": "추첨 (미혼·무자녀)"},
      basis="규칙 제43조③ — 비규제지역, 부모님 세대의 세대원(단독세대 아님)은 면적 제한 없이 추첨 물량 (천안 84㎡)")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, married=False, marriedOn="", kidsMinor=0, kidsOnDeed=0, youngestBirth="", pregnant=False, spouseIncome=0, hhIncomeYear=3000, income=3000, hhSize=1),
      expect={"s": "fail"}, basis="2026000409·414 공공분양 '1인 가구의 경우 생애최초 특별공급 청약신청 불가', 신청자격 ③ 혼인 중이거나 미혼 자녀")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, married=False, marriedOn="", kidsMinor=0, kidsOnDeed=None, youngestBirth="", pregnant=False, spouseIncome=0, hhIncomeYear=3000, income=3000, hhSize=2),
      expect={"s": "warn"}, basis="생애최초 '미혼인 자녀(혼인 중이 아니면 같은 등본)' — 같은 등본 자녀 수를 모르면 확인 필요")
    # 통장 종류: 공공은 청약저축 그대로 가능(부칙 제7조), 민영은 청약저축 1·2순위 모두 불가
    g(fn="item", item="통장 종류 (공공분양)", listing="2026000414-059.8400A", profile=dict(pub_base, acctType="saving"), expect={"s": "none"},
      basis="규칙 부칙 제7조(2015.9.1 전 가입 청약저축은 종전 규정), 2026000409 '저축총액(주택청약종합저축 및 청약저축은 매월 최대 25만원…)'")
    g(fn="item", item="통장 종류 (공공분양)", listing="2026000414-059.8400A", profile=dict(pub_base, acctType="deposit"), expect={"s": "fail"},
      basis="2026000409 '종전 통장(청약저축·청약예금·청약부금)을 주택청약종합저축으로 전환하여 … 공고일 전일까지 전환한 경우에만' — 예금·부금")
    g(fn="bucket", listing="2026000453-059.9742A", profile=dict(gw, acctType="saving"), expect={"b": "no"},
      basis="2026000453 '2순위 : 예치금액과 관계없이 청약예금·청약부금·주택청약종합저축에 가입한 분' — 청약저축은 2순위도 아님")
    # 무주택: 세대 주택 수를 안 넣으면 공공·특별공급은 확인 필요
    g(fn="home", listing="2026000414-059.8400A", profile=dict(pub_base, hhHomes=""), expect={"s": "warn"},
      basis="규칙 제2조제4호 무주택세대구성원 — 세대원 주택 여부를 모르면 판정하지 않음")
    # 규제지역 2주택: 60세 이상 부모님 명의는 주택 수에서 뺌 (제53조제6호)
    g(fn="item", item="2주택 이상 세대 아님 (규제지역 1순위)", listing="2026000453-059.9742A", profile=dict(gw, hhHomes="2+", hhOwner="parent60"), expect={"s": "ok"},
      basis="규칙 제53조제6호 60세 이상 직계존속 소유 주택은 무주택으로 봄 — 2주택 판정에서 제외")
    # 거주: 공고일 뒤 전입
    g(fn="item", item="거주지", listing="2026000453-059.9742A", profile=dict(gw, sidoOwnSince="2026-12-01", areaSince="2026-12-01", sidoSince="2026-12-01"), expect={"s": "warn"},
      basis="2026000453 '입주자모집공고일 현재 … 거주' — 공고일 뒤 전입이면 공고일 당시 주소를 모름")
    g(fn="bucket", listing="2026000453-059.9742A", profile=dict(gw, household="parents", parentsOwn=False, parents60=True, sidoOwnSince="2026-12-01", areaSince="2026-12-01", sidoSince="2026-12-01"), expect={"b": "unsure"},
      basis="2026000453 1순위 세대주(투기과열) 미충족이어도, 공고일 당시 주소를 모르면 2순위 자격(거주 요건)도 모름 → 확인 필요")
    # 규제지역 세대주 추정은 1순위 요건 → 세대원은 2순위 (제27조①1다, 공공 변형 공고)
    g(fn="bucket", listing="2026000414-REG", profile=dict(pub_base, household="parents", parentsOwn=False, parents60=False, hhIncomeYear=5000, income=5000), expect={"b": "r2"},
      basis="규칙 제27조①1다 투기과열·청약과열 국민주택 1순위 '세대주' — 세대원은 2순위")
    # 신혼희망타운: 세대주·순위 없음 (2026820008 신청자격 ①~④), 예비신혼부부는 예비 배우자 정보가 없어 확인 필요
    tb = dict(town_base, hhIncomeYear=5000, income=5000, realEstate=0, carValue=0)
    g(fn="item", item="세대주", listing="2026820010-REG", profile=dict(tb, household="parents", parentsOwn=False, parents60=False), expect={"s": "none"},
      basis="2026820008~011 신혼희망타운 신청자격 ①~④ — 세대주 요건 없음 (공고문에서 세대주 요건을 읽지 않은 경우)")
    g(fn="item", item="세대 5년 내 당첨 없음 (규제지역 1순위)", listing="2026820010-REG", profile=dict(tb, win5y=True, everWin="yes", recentWin=False), expect={"s": "none"},
      basis="신혼희망타운은 1순위·2순위가 없다 (2026820008 입주자 선정 1·2·3단계)")
    g(fn="item", item="신청 유형 (신혼희망타운)", listing="2026820010-055.8800B", profile=dict(tb, married=False, marriedOn="", townType="pre"), expect={"s": "warn"},
      basis="2026820008 예비신혼부부 ① '혼인으로 구성할 세대원 전원이 무주택', ③·④ 소득·총자산 그 세대 기준 — 예비 배우자 정보 미입력")
    # 60세 이상 부모님 명의 집은 무주택이지만 공공 자산에는 포함 (2026000409·414 '제53조에 의거 주택으로 보지 않는 경우에도 … 자산보유기준 적용 대상')
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", hhHomes="1", hhOwner="parent60", realEstate=0), expect={"s": "warn"},
      basis="2026000414 '제53조에 의거 주택으로 보지 않는 경우에도 해당 주택과 그 주택의 부속 토지는 자산보유기준 적용 대상' — 부동산 0 입력")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", hhHomes="1", hhOwner="parent60", realEstate=30000), expect={"s": "fail"},
      basis="2026000414 <표2> 부동산 215,500천원 — 부모님(60세 이상) 집을 포함한 부동산 3억")
    # 생애최초 혼자 사는 세대는 60㎡ 이하 (세대주 여부 답과 관계없이 가구원수 1)
    g(fn="sp", type="first", listing="2026000426-084.8786A", profile=dict(fb, homeSido="충남", homeSigun="천안시", household="spouse", hhSize=1), expect={"s": "fail"},
      basis="규칙 제43조③ 후단 단독세대 — 가구원수 1명이면 전용 60㎡ 이하만 (천안 84㎡)")
    # ---------- 9) 해당하는 분만 답하는 질문 (기능: optional_inputs, 사용자 방침 2026-10-01: 비우면 해당 없음) ----------
    for over, exp in [({"selfOwn": True, "hhHomes": "1", "ownExc": "small_villa"}, "ok"), ({"selfOwn": True, "hhHomes": "1", "ownExc": "small_apt"}, "ok"),
                      ({"selfOwn": True, "hhHomes": "1", "ownExc": "tiny"}, "ok"), ({"selfOwn": True, "hhHomes": "1", "ownExc": None}, "fail"),
                      ({"selfOwn": True, "hhHomes": "2+", "ownExc": "small_apt"}, "fail"), ({"hhHomes": "1", "hhOwner": "other", "ownExc": "small_villa"}, "ok")]:
        g(fn="home", listing="2026000414-059.8400A", profile=dict(pub_base, **over), expect={"s": exp},
          basis="규칙 제53조 본문·5호·9호 '주택공급신청자가 속한 세대가 … 1호 또는 1세대만 소유하고 있는 경우' 무주택으로 봄 — 2채 이상이면 적용 안 함")
    g(fn="item", item="주택 소유 예외", listing="2026000414-059.8400A", profile=dict(pub_base, selfOwn=True, hhHomes="1", ownExc="other"), expect={"s": "warn"},
      basis="규칙 제53조 2·7·11호 등 조건이 복잡한 예외 — 판정하지 않고 확인 필요")
    g(fn="sp", type="first", listing="2026000414-059.8400A", profile=dict(pub_base, selfOwn=True, hhHomes="1", ownExc="small_villa", hhNeverOwned=False, hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01"), expect={"s": "fail"},
      basis="생애최초는 '세대에 속한 모든 자가 과거 주택을 소유한 사실이 없는 경우' (규칙 제43조①) — 무주택으로 봐도 소유 이력은 남음")
    g(fn="sp", type="newlywed", listing="2026000414-059.8400A", profile=dict(pub_base, selfOwn=True, hhHomes="1", ownExc="small_villa", hhIncomeYear=3000, income=3000, realEstate=20000), expect={"s": "ok", "stage": "우선공급"},
      basis="규칙 제53조제9호 — 공공분양 특별공급의 무주택세대구성원 판정에도 적용 (노부모부양만 제6호 제외), 부동산 2억은 215,500천원 이하")
    for over in [{"selfOwn": True, "hhHomes": "1", "ownExc": "small_villa"}, {"married": True, "marriedOn": "2015-01-01", "spouseSoldOn": "2023-05-01"},
                 {"married": True, "marriedOn": "2015-01-01", "homeSoldOn": "2024-02-01", "spouseSoldOn": "2023-05-01"}]:
        pp = dict(sb, **over)
        g(fn="score", listing="2026000453-059.9742A", profile=pp, expect={"parts": score(pp, REF453)},
          basis="별표1 가목 2)·3) 소형·저가주택은 무주택, '주택공급신청자 또는 배우자가 … 최근에 무주택자가 된 날'부터")
    for over, exp in [({"everWin": "yes", "win5y": True, "recentWin": False, "winSpecial": True}, "fail"),
                      ({"everWin": "yes", "win5y": True, "recentWin": False, "winSpecial": False}, "ok"),
                      ({"everWin": "yes", "win5y": False, "recentWin": False, "winSpecial": None}, "warn")]:
        g(fn="sp", type="first", listing="2026000443-059.9986A", profile=dict(pub_base, homeSido="부산", homeSigun="", hhIncomeYear=3000, income=3000, youngestBirth="2019-01-01", **over), expect={"s": exp},
          basis="규칙 제55조 '특별공급은 한 차례에 한정하여 1세대 1주택' — 예전 당첨이 특별공급인지 (비규제 민영이라 재당첨 제한은 해당 없음)")
    g(fn="sp", type="elder", listing="2026000453-059.9742A", profile=dict(gw, elder65=None), expect={"s": "fail"},
      basis="사용자 방침(2026-10-01): 해당하는 분만 답하는 질문은 비우면 해당 없음 — 노부모부양 요건 미충족")
    for cash, exp in [(10000, "ok"), (33000, "warn")]:
        tp = dict(town_base, hhIncomeYear=5000, income=5000, realEstate=0, carValue=0, cash=cash, townInsurance=None, townFinOther=None, townOtherAsset=None, townDebt=None)
        g(fn="town", listing="2026820010-055.8800B", profile=tp, expect={"총자산": exp},
          basis="2026820010 <표3> 총자산 362,000천원 — 비운 보험·기타 자산은 0으로 보되 합계가 기준의 90%(32,580만원)를 넘으면 확인 필요")
    g(fn="pubgen", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=5000, income=5000, realEstate=None, carValue=1000), expect={"소득": "ok"},
      basis="2026000414 일반공급 — 자산 칸을 비운 무주택자는 부동산 0 (소득 판정은 그대로)")

    # 소득: 세대 소득을 비우고 같은 등본에 부모님이 있으면 추정으로 판정하지 않음
    g(fn="pubgen", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=None, income=3000, household="parents", parentsOwn=False, parents60=True), expect={"소득": "warn"},
      basis="2026000414 '무주택세대구성원 전원(…)의 소득을 합산' — 같은 등본 부모님 소득 미입력")

    # ---------- 10) 일반공급 물량 0 주택형 (기능: gen_none, 2026-10-02 사용자 지적) ----------
    # 2026000414 인천계양 A6 공고문 공급표: 59G 일반 0·특별공급 6(신생아1·신혼1·생애최초1·다자녀1·기관 등2), 59C 총 15세대 전부 사전청약 당첨자 몫(이번 공급 0).
    # 2026930036 과천 푸르지오 라비엔오 84D 불법행위 재공급: 공급규모 '불법행위재공급 주택 2세대 [특별공급 2세대(신혼부부 1, 노부모부양 1)]', 청약홈 일반 세대수 0, 유형별 특공 세대수 없음.
    # 기대값: 일반공급이 없으면 일반공급 판정을 쓰지 않고 특별공급 판정 중 가장 좋은 것 (oracle sp_expect, 위 2) 공공 특별공급 소득 단계 표)
    def best(types, p):
        ss = [sp_expect(True, t, p, 3)["s"] for t in types]
        return "ok" if "ok" in ss else "unsure" if "warn" in ss else "no"
    g59 = ["newborn", "newlywed", "first", "multichild"]
    p = dict(pub_base, hhIncomeYear=3000, income=3000)
    g(fn="bucket", listing="2026000414-059.9700G", profile=p, expect={"b": best(g59, p)},
      basis="2026000414 공급표 59G 일반공급 0세대 — 특별공급(신생아 소득 100% 이하 우선공급)으로 신청 가능")
    p = dict(pub_base, hhIncomeYear=30000, income=30000)
    assert best(g59, p) == "no"
    g(fn="bucket", listing="2026000414-059.9700G", profile=p, expect={"b": "no"},
      basis="2026000414 공급표 59G 일반공급 0세대 — 특별공급 4유형 모두 소득 기준(<표4>·<표5> 최대 200%+완화 20%p) 초과")
    g(fn="bucket", listing="2026000414-SPELDER", profile=dict(pub_base, hhIncomeYear=3000, income=3000, elder65=False), expect={"b": "no"},
      basis="일반 0세대·노부모부양 특별공급만 있는 주택형(2026000414 59G 변형) — 규칙 제46조 '65세 이상 직계존속을 3년 이상 계속 부양' 미충족이면 신청할 공급이 없음 (일반공급 요건을 다 갖춰도)")
    g(fn="bucket", listing="2026000414-059.8300C", profile=dict(pub_base, hhIncomeYear=3000, income=3000), expect={"b": "no"},
      basis="2026000414 공급표 59C 총공급 15세대 = 사전청약 당첨자 15 → 이번 공고 공급 0세대 (일반 0·특별 0)")
    p36 = dict(pub_base, homeSido="경기", homeSigun="과천시", hhIncomeYear=3000, income=3000)
    nw = sp_expect(False, "newlywed", p36, 3)["s"]   # 민영 신혼부부 특별공급 oracle (위 3) 2026000453 표)
    g(fn="bucket", listing="2026930036-084.7450D", profile=p36, expect={"b": "ok" if nw == "ok" else "unsure"},
      basis="2026930036 공급대상 표 84D 특별공급 2세대(노부모부양 1, 신혼부부 1, 기능 resupply_special) · 과천시 거주·혼인 3년·2025년생·월소득 100% 이하 → 신혼부부 특별공급 가능 (블라인드 감사 V13 'ok')")

    # ---------- 11) 공공임대 일반공급 (군포대야미 A-1 6년 분양전환공공임대 2026000307, 공고일 2026-06-30) — 기능 rental_rules ----------
    # 원문 <표4> 금액을 이 파일에 따로 옮겨 적는다 (화면·파서 값을 쓰지 않음):
    #  (표4-1) 1인 일반공급 120% 4,576,036 · (표4-2) 2인 추첨공급 110% 6,452,897 / 맞벌이 200% 11,732,540, 우선공급1순위자 맞벌이 150% 8,799,405
    #  (표4-3) 3인 이상 추첨공급 100% 8,168,429 · 8,802,202 · … / 맞벌이 200% 16,336,858 · 17,604,404 · …
    #  <표2> 총자산 362,000천원 · <표3> 출산 1명 397,000천원
    RL = "2026000307-055.0000A"
    R_ELIG = {1: (4576036, None), 2: (6452897, 11732540), 3: (8168429, 16336858), 4: (8802202, 17604404)}
    r_base = dict(pub_base, homeSido="경기", homeSigun="군포시", acctCount=30, realEstate=0, carValue=0, cash=0, liquid=0, deposit=0,
                  townInsurance=0, townFinOther=0, townOtherAsset=0, townDebt=0)
    shape = {1: dict(married=False, marriedOn="", dependents=0, kidsMinor=0, kidsOnDeed=0, youngestBirth="", pregnant=False, hhSize=1),
             2: dict(married=True, dependents=1, kidsMinor=0, kidsOnDeed=0, youngestBirth="", pregnant=False, hhSize=2),
             3: dict(youngestBirth="2019-01-01"),
             4: dict(kidsMinor=2, kidsOnDeed=2, hhSize=4, dependents=3, youngestBirth="2019-01-01")}
    i = 0
    for n, (single, dual_amt) in R_ELIG.items():
        for dual, lim in ((False, single), (True, dual_amt)):
            if lim is None:
                continue
            le = lim * 12 // 10000                 # 만원/년 — 월평균이 기준 이하가 되는 가장 큰 값
            for y, exp in ((le, "ok"), (le + 1, "fail")):
                p = dict(r_base, **shape[n], hhIncomeYear=y, income=(y // 2 if dual else y), spouseIncome=(y - y // 2 if dual else 0))
                assert (y * 10000 / 12 <= lim) == (exp == "ok")
                add(id=f"rental-{i:02d}", fn="pubgen", listing=RL, profile=p, expect={"소득": exp},
                    basis=f"2026000307 일반공급 신청자격 ③ · <표4> {n}인{' 맞벌이' if dual else ''} 상한 월 {lim:,}원 (공공분양 '3인 이하' 표와 다름)"); i += 1
    for re_v, cash, kv, exp in [(30000, 6200, "옛자녀", "ok"), (30000, 6201, "옛자녀", "fail"), (30000, 9700, "신생아1", "ok"), (30000, 9701, "신생아1", "warn")]:
        p = dict(r_base, **kidvars[kv], hhIncomeYear=3000, income=3000, realEstate=re_v, cash=cash)
        add(id=f"rental-{i:02d}", fn="item", item="총자산 (공공임대 일반공급)", listing=RL, profile=p, expect={"s": exp},
            basis="2026000307 <표2> 총자산 362,000천원 이하 · <표3> '23.3.28 이후 출생 자녀 1명 397,000천원"); i += 1
    # 공공임대 특별공급 (기능 rental_special): 원문 <표4> 유형별 단계·퍼센트와 <표5> 가구원수별 퍼센트 금액을 이 파일에 따로 옮겨 적는다 (화면·파서 값을 쓰지 않음)
    for t, kv, n, dual in [("newlywed", "옛자녀", 3, False), ("newlywed", "옛자녀", 3, True), ("newlywed", "2인", 2, False), ("newlywed", "2인", 2, True),
                           ("newborn", "신생아1", 3, False), ("first", "옛자녀", 3, False), ("elder", "옛자녀", 3, False), ("multichild", "새2명옛", 4, False)]:
        tiers = R_SP[t][1] if n == 2 else [(a, b) for _, _, a, b in R_SP[t][0]]
        for k, (a, b) in enumerate(tiers):
            lim = r_amt(b if dual else a, n)
            for side in ("le", "gt"):
                y = lim * 12 // 10000 + (0 if side == "le" else 1)
                p = dict(r_base, **R_KID[kv], hhIncomeYear=y, income=(y // 2 if dual else y), spouseIncome=(y - y // 2 if dual else 0))
                if t == "elder":
                    p.update(eldersOnDeed=None)
                add(id=f"rental-{i:02d}", fn="sp", type=t, listing=RL, profile=p, expect=rental_sp_expect(t, p, n),
                    basis=f"2026000307 <표4> 공공임대 {t} {n}인{' 맞벌이' if dual else ''} {k + 1}단계 {b if dual else a}% 월 {lim:,}원 {'이하' if side == 'le' else '초과'} (<표5> 금액)"); i += 1
    for kv, re_v in [("옛자녀", 36200), ("옛자녀", 36201), ("신생아1", 39700), ("신생아1", 39701), ("신생아1", 43101)]:
        p = dict(r_base, **R_KID[kv], hhIncomeYear=3000, income=3000, realEstate=re_v)
        add(id=f"rental-{i:02d}", fn="sp", type="newlywed", listing=RL, profile=p, expect=rental_sp_expect("newlywed", p, 3),
            basis="2026000307 '3. 총자산보유기준 적용대상: … 신혼부부 … 특별공급' <표2> 362,000천원 · <표3> 출산 1명 397,000천원 · 2명 이상 431,000천원"); i += 1

    # ---------- 12) 경계값 보강 (2026-10-02 MASTER QA 코드 변이 검사에서 못 잡던 규칙, evidence/qa/code-mutation.json) ----------
    i = 0
    def b(**c):
        nonlocal i
        add(id=f"edge-{i:02d}", **c); i += 1
    # 공공분양 일반공급 소득·자산 기준은 '전용면적 60㎡ 이하만 적용'(2026000414 요약표) — 60.00㎡ 는 대상, 60.01㎡ 는 아님. 기준을 못 읽은 공고는 대상이면 확인 필요
    b(fn="item", item="소득·자산 (공공 일반공급)", listing="2026000414-A60", profile=dict(pub_base, hhIncomeYear=3000, income=3000), expect={"s": "warn"},
      basis="2026000414 '* 전용면적 60㎡ 이하만 적용' — 정확히 60㎡ 는 적용 대상 (기준 미확인 → 확인 필요)")
    b(fn="item", item="소득·자산 (공공 일반공급)", listing="2026000414-A6001", profile=dict(pub_base, hhIncomeYear=3000, income=3000), expect={"s": "none"},
      basis="2026000414 '* 전용면적 60㎡ 이하만 적용' — 60.01㎡ 는 소득·자산 기준 없음")
    # 민영 예치금: '전용 85㎡ 이하 300·250·200만원', '102㎡ 이하 600·400·300만원' (2026000453) — 85.00㎡ 는 첫 구간
    for lid, amount, exp in [("2026000453-A85", 200, "ok"), ("2026000453-A8501", 200, "fail"), ("2026000453-A8501", 300, "ok")]:
        b(fn="acct", listing=lid, profile={"acctType": "all", "acctSince": "2014-01-01", "acctAmount": amount, "homeSido": "경기", "household": "head"},
          expect={"가입기간": "ok", "예치금": exp}, basis="2026000453 예치금 표 — 경기(광역시 외) 85㎡ 이하 200만원, 102㎡ 이하 300만원 (85.00㎡ 는 85㎡ 이하)")
    # 투기과열지구 1순위 가입기간 24개월 (2026000453 '가입기간 24개월 경과'). 공고문에서 못 읽은 규제지역 공고(2026000414-REG)도 24개월로 본다
    for since, exp in [("2024-08-31", "ok"), ("2024-09-01", "fail"), ("2025-08-31", "fail")]:
        assert (months(since, "2026-08-31") >= 24) == (exp == "ok")
        b(fn="acct", listing="2026000414-REG", profile=dict(pub_base, acctSince=since), expect={"가입기간": exp},
          basis="주택공급규칙 제27조 투기과열지구·청약과열지역 1순위 24개월 (2026000414 변형, 공고일 2026-08-31 기준 2024-08-31 가입 = 정확히 24개월)")
    # 거주기간 기준일: '2024.09.18. 이전부터 계속 거주' (2026000453) — 기준일 당일 전입은 해당지역
    for since, v in [("2024-09-18", "해당지역 (2년 이상)"), ("2024-09-19", "기타지역")]:
        b(fn="residence", listing="2026000453-059.9742A", profile={"homeSido": "경기", "homeSigun": "광명시", "sidoOwnSince": since, "sidoSince": since, "areaSince": since},
          expect={"s": "ok", "v": v}, basis="2026000453 '경기도 광명시 2년 이상 계속 거주자 (2024.08.28. 이전부터)' 형식 — 기준일 당일 전입은 해당지역, 다음 날은 기타지역")
    # 신혼희망타운 신청 유형: 혼인 7년 이내(공고일 2026-09-30 → 2019-09-30 혼인까지), 한부모 만 6세 이하 자녀(2019-09-30 출생은 공고일에 만 7세)
    tb12 = dict(town_base, hhIncomeYear=5000, income=5000, realEstate=0, carValue=0, youngestBirth="2012-01-01")
    for mo, exp in [("2019-09-30", "ok"), ("2019-09-29", "fail"), ("2018-12-01", "fail")]:
        b(fn="item", item="신청 유형 (신혼희망타운)", listing="2026820010-055.8800B", profile=dict(tb12, married=True, marriedOn=mo), expect={"s": exp},
          basis="2026820010 신혼부부 '혼인 중인 사람으로서 혼인기간이 7년 이내' — 공고일 2026-09-30 기준 2019-09-30 혼인 = 7년 이내, 하루 전은 초과 (6세 이하 자녀 없음)")
    for yb, exp in [("2019-10-01", "ok"), ("2019-09-30", "fail")]:
        b(fn="item", item="신청 유형 (신혼희망타운)", listing="2026820010-055.8800B", profile=dict(tb12, married=False, marriedOn="", townType="single", youngestBirth=yb), expect={"s": exp},
          basis="2026820010 한부모가족 '만 6세 이하 자녀' — 2019-09-30 출생은 공고일(2026-09-30)에 만 7세라 제외, 2019-10-01 출생은 만 6세")
    # 판정 묶음: 자격은 되지만 확인할 항목(세대 소득 미입력)이 있으면 '확인 필요' — '신청 가능'으로 올리지 않는다
    b(fn="bucket", listing="2026000414-059.8400A", profile=dict(pub_base, hhIncomeYear=None, income=0, spouseIncome=0), expect={"b": "unsure"},
      basis="2026000414 60㎡ 이하 공공분양 일반공급은 세대 소득 기준이 있어 소득을 모르면 판정할 수 없음 → 확인 필요 (가짜 '가능' 금지)")

    # ---------- 13) 거주 요건은 특별공급에도 공통 (2026-10-02 사용자 지적: 과천 84D 카드 '특별공급 확인 필요' ↔ 상세 '신청 불가') ----------
    i = 0
    def v1(**c):
        nonlocal i
        add(id=f"common-{i:02d}", **c); i += 1
    v1(fn="bucket", listing="2026930036-084.7450D", profile=dict(pub_base, homeSido="서울", homeSigun="", sidoOwnSince="2015-01-01", hhIncomeYear=3000, income=3000), expect={"b": "no"},
       basis="2026930036 '본 입주자모집공고의 특별공급은 해당 주택건설지역 거주자 중 …'·'경기도 과천시 거주자' — 서울 거주자는 일반 0세대 주택형의 특별공급도 신청 불가")
    v1(fn="bucket", listing="2026000414-059.9700G", profile=dict(pub_base, homeSido="충남", homeSigun="천안시", sidoOwnSince="2015-01-01", sidoSince="2015-01-01", areaSince="2015-01-01", hhIncomeYear=3000, income=3000), expect={"b": "no"},
       basis="2026000414 '입주자모집공고일 현재 수도권 거주' — 충남 거주자는 59G(일반 0세대)의 특별공급도 신청 불가")
    v1(fn="bucket", listing="2026000414-059.9700G", profile=dict(pub_base, homeSido="", homeSigun="", hhIncomeYear=3000, income=3000), expect={"b": "unsure"},
       basis="2026000414 수도권 거주 요건 — 사는 곳을 모르면 특별공급 소득이 맞아도 '가능'으로 단정하지 않음")
    v1(fn="sp", type="newborn", listing="2026000414-059.8400A", profile=dict(pub_base, homeSido="충남", homeSigun="천안시", sidoOwnSince="2015-01-01", sidoSince="2015-01-01", areaSince="2015-01-01", hhIncomeYear=3000, income=3000), expect={"s": "fail"},
       basis="2026000414 수도권 거주 요건은 특별공급(신생아)에도 적용 — 충남 거주자는 불가")
    v1(fn="sp", type="newlywed", listing="2026000453-059.9742A", profile=dict(pub_base, homeSido="부산", homeSigun="", sidoOwnSince="2015-01-01", sidoSince="2015-01-01", areaSince="2015-01-01", hhIncomeYear=3000, income=3000), expect={"s": "fail"},
       basis="2026000453 '경기도 광명시 거주자 / 서울·경기·인천 거주자' — 부산 거주자는 민영 신혼부부 특별공급도 불가")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # ---------- 14) 판정 범위 밖 공고는 '가능'·'불가'로 확정하지 않음 (기능 judge_scope, 2026-10-02 사용자 QA '임대 → 분양' · '지원하지 않는 유형 → 가능') ----------
    # 2025000645 이천 5년 공공건설임대 임차인모집: 청약홈 RENT_SECD_NM '분양전환 가능임대', 원문 '신청자격 / 청약통장 자격요건 / 소득 또는 자산기준' 표가 있으나 이 서비스가 읽지 못함(pub_limits 없음)
    #  → 분양 규칙(국민주택 1순위 등)으로 판정하면 안 됨: 조건이 아무리 좋아도·유주택이어도 '확인 필요'.
    # 2026000307 소득·총자산 표를 못 읽은 경우(-NOLIM, 받기 실패 가정)도 같음. 표를 읽은 2026000307 은 위 11) 처럼 판정한다.
    i = 0
    good = dict(pub_base, homeSido="경기", homeSigun="이천시", sidoSince="2010-01-01", areaSince="2010-01-01", acctCount=60, acctSince="2015-01-01",
                hhIncomeYear=3000, income=3000, realEstate=0, carValue=0, cash=0, liquid=0, deposit=0, townInsurance=0, townFinOther=0, townOtherAsset=0, townDebt=0)
    # 2025000645 는 '국민주택(5년 공공건설임대)' 신청자격 표의 '소득 또는 자산기준' 칸이 모두 '-'(기준 없음)라 수집이 pub_limits {kind:'none'} 으로 읽는다 (기능 rent_noincome, 2026-10-05)
    #  → 원문 '이천시 또는 수도권(서울·경기·인천)에 거주하는 … 무주택세대구성원', 일반공급 1순위 '12개월 경과, 월납입금 12회 이상', 2순위 '가입'으로 판정. 특별공급은 판정하지 않음(확인 필요)
    i2 = 0
    for nm, pr, exp in (("조건 좋음", good, "ok"), ("유주택", dict(good, selfOwn=True, hhHomes="1", hhNeverOwned=False), "no"),
                        ("통장 없음", dict(good, acctType="none"), "no"), ("다른 지역", dict(good, homeSido="부산", homeSigun="해운대구"), "no")):
        add(id=f"rent5-{i2:02d}", fn="bucket", listing="2025000645-052.9256C", profile=pr, expect={"b": exp},
            basis=f"2025000645 국민주택(5년 공공건설임대) 신청자격 — 이천시·수도권 거주 무주택세대구성원, 1순위 12개월·12회, 소득·자산기준 없음('-') ({nm})"); i2 += 1
        add(id=f"rent5-{i2:02d}", fn="sp", type="newlywed", listing="2025000645-052.9256C", profile=pr, expect={"s": "warn"},
            basis=f"2025000645 공공임대 특별공급은 판정하지 않음 — 확인 필요 ({nm})"); i2 += 1
    for lid, why in (("2026000307-055.0000A-NOLIM", "2026000307 분양전환공공임대 — 소득·총자산 표 못 읽음"),):
        for nm, pr in (("조건 좋음", good), ("유주택", dict(good, selfOwn=True, hhHomes="1", hhNeverOwned=False)), ("통장 없음", dict(good, acctType="none")),
                       ("다른 지역", dict(good, homeSido="부산", homeSigun="해운대구"))):
            add(id=f"scope-{i:02d}", fn="bucket", listing=lid, profile=pr, expect={"b": "unsure"},
                basis=f"{why} → 분양 규칙으로 '가능'·'불가'를 확정하지 않음 ({nm}). 판정 범위 밖은 확인 필요"); i += 1
            for t in ("newlywed", "first"):
                if lid.startswith("2026000307"):
                    add(id=f"scope-{i:02d}", fn="sp", type=t, listing=lid, profile=pr, expect={"s": "warn"}, basis=f"{why} — 특별공급도 판정하지 않음 ({nm})"); i += 1

    # ---------- 15) 청년 특별공급 (기능 youth_special, 2026-10-05) ----------
    # 공공주택 특별법 시행규칙 [별표 6의6] 가목, 모집공고문 2026000313(LH 고양창릉 S-3) 신청자격 ①~④ — 금액은 원문에서 이 파일에 따로 옮겨 적는다(화면·파서 값을 쓰지 않음):
    #  <표4> '청년 특별공급 소득기준 1인 도시근로자 가구원수별 가구당 월평균소득액의 140% 5,338,708', <표2> '(청년 특별공급은 신청자 본인 276,000천원 이하 및 부모 1,035,000천원 이하)',
    #  <표3> 출산가구 '청년 특별공급의 경우, 본인 311,000천원 이하(+10%p) · 345,000천원 이하(+20%p)'. 시험 공고는 인천계양 A6(2026000414, 공고일 2026-08-31)에 이 금액을 붙인 것.
    YL, YREF, Y_INC, Y_SELF, Y_PAR, Y_SELF20 = "2026000414-YOUTH", "2026-08-31", 5338708, 27600, 103500, 34500
    y_base = dict(pub_base, married=False, marriedOn="", dependents=0, kidsMinor=0, kidsOnDeed=0, youngestBirth="", pregnant=False, hhSize=1,
                  birth="1995-05-01", selfEverOwned=False, youthAsset=10000, parentsAsset=50000, income=4000, hhIncomeYear=None, taxYears5=True)

    def youth_expect(p: dict) -> dict:
        fail = warn = False
        b = p.get("birth") or ""
        if not b:
            warn = True
        elif b > add_years(YREF, -19) or b <= add_years(YREF, -40):
            fail = True
        if p.get("married") is True:
            fail = True
        elif p.get("married") is None:
            warn = True
        if p.get("selfOwn") is True or p.get("selfEverOwned") is True:
            fail = True
        elif p.get("selfEverOwned") is None and p.get("hhNeverOwned") is not True:
            warn = True
        if months(p["acctSince"], YREF) < 6 or (p.get("acctCount") or 0) < 6:
            fail = True
        ra = relax_add(p)
        if (p.get("income") or 0) * 10000 / 12 > Y_INC:
            fail, warn = (fail, True) if ra != 0 else (True, warn)
        ya, pa = p.get("youthAsset"), p.get("parentsAsset")
        if ya is None:
            warn = True
        elif ya > Y_SELF:
            if ra != 0 and ya <= Y_SELF20:
                warn = True
            else:
                fail = True
        if pa is None:
            warn = True
        elif pa > Y_PAR:
            fail = True
        if fail:
            return {"s": "fail"}
        if warn:
            return {"s": "warn"}
        return {"s": "ok", "stage": "우선공급 (배점순)" if p.get("taxYears5") is True else "추첨"}

    i = 0
    inc_le = Y_INC * 12 // 10000
    for nm, ch in [("기본", {}), ("만 19세 되는 날", {"birth": add_years(YREF, -19)}), ("만 19세 하루 전", {"birth": "2007-09-01"}),
                   ("만 39세 마지막 날", {"birth": "1986-09-01"}), ("만 40세 되는 날", {"birth": add_years(YREF, -40)}), ("생일 모름", {"birth": ""}),
                   ("혼인 중", {"married": True, "marriedOn": "2024-01-01"}), ("혼인 모름", {"married": None}),
                   ("본인 집 있음", {"selfOwn": True}), ("본인 집 가진 적 있음", {"selfEverOwned": True}),
                   ("이력 모름", {"selfEverOwned": None, "hhNeverOwned": None}), ("이력 모름·세대 이력 없음", {"selfEverOwned": None, "hhNeverOwned": True}),
                   ("세대원(부모) 집 있음", {"household": "parents", "parentsOwn": True, "parents60": False, "hhHomes": "1", "hhOwner": "other", "hhNeverOwned": False}),
                   ("통장 5회", {"acctCount": 5}), ("통장 5개월", {"acctSince": "2026-03-01"}), ("통장 6개월", {"acctSince": "2026-02-28"}),
                   ("소득 140% 이하", {"income": inc_le}), ("소득 140% 초과", {"income": inc_le + 1}),
                   ("소득 초과·출산 완화 가능", {"income": inc_le + 1, "kidsMinor": 1, "youngestBirth": "2025-01-01", "kidsOnDeed": 1, "hhSize": 2}),
                   ("본인 자산 2억7,600만", {"youthAsset": Y_SELF}), ("본인 자산 초과", {"youthAsset": Y_SELF + 1}),
                   ("본인 자산 초과·출산 완화", {"youthAsset": Y_SELF + 1, "kidsMinor": 1, "youngestBirth": "2025-01-01", "kidsOnDeed": 1, "hhSize": 2}),
                   ("본인 자산 +20% 초과", {"youthAsset": Y_SELF20 + 1, "kidsMinor": 1, "youngestBirth": "2025-01-01", "kidsOnDeed": 1, "hhSize": 2}),
                   ("부모 자산 10억3,500만", {"parentsAsset": Y_PAR}), ("부모 자산 초과", {"parentsAsset": Y_PAR + 1}),
                   ("본인 자산 모름", {"youthAsset": None}), ("부모 자산 모름", {"parentsAsset": None}), ("소득세 5년 미만", {"taxYears5": False})]:
        p = dict(y_base, **ch)
        add(id=f"youth-{i:02d}", fn="sp", type="youth", listing=YL, profile=p, expect=youth_expect(p),
            basis=f"2026000313 청년 특별공급 신청자격 ①~④·<표2>·<표4> (공공주택 특별법 시행규칙 [별표 6의6] 가목) — {nm}"); i += 1

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)}건 → {OUT}")


if __name__ == "__main__":
    main()
