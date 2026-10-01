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
def score(p: dict, ref: str) -> list[int]:
    if p.get("selfOwn") or (p.get("married") and p.get("spouseOwn")):
        a = 0
    else:
        thirty = add_years(p["birth"], 30)
        start = thirty
        if p.get("married") and p.get("marriedOn") and p["marriedOn"] < thirty:
            start = p["marriedOn"]
        if p.get("homeSoldOn") and p["homeSoldOn"] > start:
            start = p["homeSoldOn"]
        if ref < start:
            a = 0
        else:
            y = months(start, ref) // 12
            a = 2 if y < 1 else min(32, 2 + 2 * y)
    b = min(35, 5 + 5 * p["dependents"])
    m = months(p["acctSince"], ref)
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
                "win5y": False, "recentWin": False, "birth": "1990-03-01", "dependents": 2, "kidsMinor": 1, "youngestBirth": "2025-06-01",
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
    for pct, dual in [(130, False), (131, False), (140, True), (141, True)]:
        p = dict(town_base)
        y = (amt(3, pct) * 12) // 10000 if pct in (130, 140) else (amt(3, pct - 1) * 12) // 10000 + 1
        p.update(hhIncomeYear=y, income=(y // 2 if dual else y), spouseIncome=(y - y // 2 if dual else 0))
        add(id=f"town-{i:02d}", fn="town", listing="2026820010-055.8800B", profile=p, expect={"소득": "ok" if pct in (130, 140) else "fail"},
            basis="2026820010 '우선·일반공급 130%(본인 및 배우자가 모두 소득이 있는 경우 140%)'"); i += 1
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
                      ({"hhHomes": "1", "selfOwn": True}, "fail")]:
        p = dict(pub_base, **over)
        add(id=f"home-{i:02d}", fn="home", listing="2026000414-059.8400A", profile=p, expect={"s": exp},
            basis="주택공급에 관한 규칙 제2조제4호·제53조제6호, 2026000414 '무주택세대구성원'"); i += 1
    for lid, over in [("2026000453-059.9742A", {"hhHomes": "1"}), ("2026000443-059.9986A", {"hhHomes": "1"})]:
        p = dict(pub_base, **over)   # 민영 일반공급: 1순위는 유주택 세대도 가능 (제28조①1호, 규제지역 2주택 이상만 제외) → 무주택 항목 자체는 '가능'
        add(id=f"home-{i:02d}", fn="home", listing=lid, profile=p, expect={"s": "ok"},
            basis=f"{lid.split('-')[0]} 민영 1순위 — 유주택 세대도 신청(추첨제), 규칙 제28조①1호"); i += 1

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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)}건 → {OUT}")


if __name__ == "__main__":
    main()
