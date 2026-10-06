"""SH 임대 모집공고문에서 신청자격(계층·무주택·소득·총자산·자동차)을 읽는다 (기능 sh_judge, SH 2단계).

지금 읽는 공고 종류 (그 밖의 SH 공고는 terms=None → 화면 '판정 미지원'):
  - 신혼·신생아 매입임대 Ⅰ·Ⅱ : '세부 신청자격' 표의 유형(신생아가구·지원대상 한부모가족·신혼부부·예비신혼부부·6세 이하 자녀 한부모가족·
    6세 이하 자녀 혼인가구·(Ⅱ)혼인가구), '월평균소득의 N% 이하(배우자 소득 있는 경우 M% 이하)', '2인가구는 기준금액에 10%p 가산',
    총자산 한도와 출산가구 표(원), 자동차 한도와 출산가구 표(원, Ⅱ는 자동차 개별 기준 없음)
  - 청년 매입임대(특화형) : '만 19세 이상 만 39세 이하', '혼인 중이 아닐 것', '무주택자(본인)', 소득 100% 표(1인 20%·2인 10% 가산),
    총자산·자동차 한도

화면 판정 엔진(docs/index.html rentalJudge/rentalGroup)이 LH terms 와 같은 모양으로 읽는다. SH 만의 칸:
  born_from(신생아가구 출생일 하한), wed_from·kid6_from(혼인신고일·6세 이하 자녀 출생일 하한 — 공고문에 날짜로 적힘),
  exempt(지원대상 한부모가족: 소득·자산 검증 면제), birth_bonus('table' = 소득 가산 없음·총자산·자동차는 공고문 표 금액 / 'none' = 가산 없음),
  asset_bonus·car_bonus({'10': 만원, '20': 만원}), car_manwon 'none'(자동차 개별 기준 없음), income_household(청년도 세대 소득·자산),
  hh_home_scan(자격은 본인 무주택인데 주택 소유 조회는 세대 전원 — 세대원 집이 있으면 판정하지 않고 확인).

읽은 소득 기준표(원)는 앱의 도시근로자 2025 월평균소득(RENT_URBAN_2025) × 퍼센트와 대조해, 하나라도 다르면 소득 기준을 비운다(→ 화면 '공고문 확인').
정답: tests/golden/sh_rental.json 의 terms (공고문 원문을 직접 읽은 값).
"""
from __future__ import annotations

import re

URBAN_2025 = {1: 3813363, 2: 5866270, 3: 8168429, 4: 8802202, 5: 9326985}   # docs/index.html RENT_URBAN_2025 와 같은 값 (공고문 표로 확인)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _date(y: str, m: str, d: str) -> str:
    y = int(y)
    y = y + 2000 if y < 100 else y
    return f"{y:04d}-{int(m):02d}-{int(d):02d}"


_Q = "[‘'’`]?"


def _bonus_row(t: str, label: str) -> dict | None:
    """출산가구 표: '총자산가액 379,000,000원 이하 413,000,000원 이하 413,000,000원 이하' → {'10': 37900, '20': 41300} (만원)"""
    m = re.search(label + r" ([\d,]{9,})원 이하 ([\d,]{9,})원 이하 ([\d,]{9,})원 이하", t)
    if not m:
        return None
    a, b, c = (_num(x) for x in m.groups())
    if b != c or a % 10000 or b % 10000:
        return None
    return {"10": a // 10000, "20": b // 10000}


def _check_income_table(t: str, pct: int, dual: int | None, add2: int) -> list[str]:
    """공고문 소득 기준표의 금액이 도시근로자 2025 × 퍼센트(2인은 +가산)와 같은지. 다르면 이유 목록"""
    bad = []
    for p in [pct] + ([dual] if dual else []):
        m = re.search(rf"{p}%이하 ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)", t)
        if not m:
            bad.append(f"{p}% 줄 없음")
            continue
        for n, v in zip((2, 3, 4, 5), m.groups()):
            want = round(URBAN_2025[n] * (p + (add2 if n == 2 else 0)) / 100)
            if abs(_num(v) - want) > 1:
                bad.append(f"{p}% {n}인 {v} ≠ {want}")
    return bad


def parse_newlywed(text: str) -> dict | None:
    t = _flat(text)
    if "세부 신청자격" not in t:
        return None
    seg = t[t.index("세부 신청자격"):]
    seg = seg[: seg.index("신청순위")] if "신청순위" in seg else seg[:3000]
    issues: list[str] = []
    m = re.search(r"월평균 ?소득이 \[?전년도 도시근로자 가구원수별 가구당 월평균소득\]?의 (\d+)% ?이하 ?\(배우자 소득 있는\*? ?경우 (\d+)% ?이하\)", t)
    pct, dual = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    add2 = 10 if re.search(r"2인 ?가구는 기준금액에 10%p 가산", t) else 0
    if pct is None:
        issues.append("소득 퍼센트 못 읽음")
    else:
        issues += _check_income_table(t, pct, dual, add2)
    income_pct = None if issues else {"2": pct + add2, "3+": pct}
    dual_add = dual - pct if (dual and not issues) else None
    am = re.search(r"총자산가액 ?: ?([\d,]+)만원 이하", t)
    asset = _num(am.group(1)) if am else None
    abon = _bonus_row(t, "총자산가액")
    cm = re.search(r"자동차가액\(현재가치기준\) ?: ?([\d,]+)만원 이하", t)
    car: int | str | None = _num(cm.group(1)) if cm else None
    cbon = _bonus_row(t, "자동차가액") if cm else None
    if car is None and re.search(r"자동차가액은 총자산에 합산됨(?!.{0,5}개별)", t) and "자동차가액(현재가치기준)" not in t:
        car = "none"   # Ⅱ: 자동차는 총자산에만 합산, 개별 기준 없음
    # 날짜 하한 (공고문 표의 괄호 날짜)
    bm = re.search(r"2년 이내 출생한 자녀가 있는 가구 \(" + _Q + r"(\d{2})\. ?(\d{1,2})\. ?(\d{1,2})\. ?이후 출생", seg)
    wm = re.search(r"혼인 7년 이내\(혼인신고일이 " + _Q + r"(\d{2})\. ?(\d{1,2})\. ?(\d{1,2})\.", seg)
    km = re.findall(r"만 6세 이하 자녀[^()]{0,30}\(" + _Q + r"(\d{2})\. ?(\d{1,2})\. ?(\d{1,2})\. ?이후 출생", seg)
    kid6 = {_date(*x) for x in km}
    base = dict(homeless="household", income_pct=income_pct, dual_add=dual_add, asset_manwon=asset, car_manwon=car)
    if abon:
        base["asset_bonus"] = abon
    if cbon:
        base["car_bonus"] = cbon
    groups = []
    if "신생아가구" in seg:
        groups.append(dict(key="신생아가구", name="신생아가구", born_from=_date(*bm.groups()) if bm else None, **base))
    if re.search(r"지원대상 ?한부모가족", seg):
        groups.append(dict(key="지원대상한부모", name="지원대상 한부모가족", exempt=True, homeless="household",
                           income_pct="excluded", asset_manwon="excluded", car_manwon="excluded"))
    if "신혼부부" in seg:
        groups.append(dict(key="신혼부부·한부모", name="신혼부부·예비신혼부부·6세 이하 자녀 가구",
                           wed_from=_date(*wm.groups()) if wm else None, kid6_from=kid6.pop() if len(kid6) == 1 else None, **base))
    if re.search(r"혼인가구 기타 혼인가구", seg):
        groups.append(dict(key="혼인가구", name="혼인가구", **base))
    if not groups:
        return None
    exempt_ok = bool(re.search(r"지원대상 한부모가족\(한부모가족 증명서\)[^.]{0,20}소득[·ㆍ] ?자산 ?검증 ?불필요", t))
    if not exempt_ok:   # 면제 문장을 못 찾으면 면제로 보지 않는다 → 다른 계층과 같은 기준
        for g in groups:
            if g["key"] == "지원대상한부모":
                g.update(exempt=False, income_pct=income_pct, dual_add=dual_add, asset_manwon=asset, car_manwon=car)
    return {"sh": True, "income_basis": "도시근로자 월평균소득", "birth_bonus": "table", "prewed_ok": "예비신혼부부" in seg,
            "relaxed": False, "homeless_relaxed": False, "groups": groups, "issues": issues}


def parse_youth(text: str) -> dict | None:
    t = _flat(text)
    am = re.search(r"만 ?(\d{2})세 이상 만 ?(\d{2})세 이하인 자", t)
    if not am:
        return None
    issues: list[str] = []
    m = re.search(r"월평균소득의 100% 이하\(원\) ([\d,]+) \(20% 가산금액\) ([\d,]+) \(10% 가산금액\) ([\d,]+) ([\d,]+) ([\d,]+)", t)
    if not m:
        issues.append("소득 표 못 읽음")
    else:
        for n, v, add in zip((1, 2, 3, 4, 5), m.groups(), (20, 10, 0, 0, 0)):
            want = round(URBAN_2025[n] * (100 + add) / 100)
            if abs(_num(v) - want) > 1:
                issues.append(f"{n}인 {v} ≠ {want}")
    am2 = re.search(r"총자산가액 합산기준 ([\d,]+)만원 이하", t)
    cm = re.search(r"개별 자동차가액 ([\d,]+)만원 이하", t)
    single = bool(re.search(r"혼인 중이 아닐 것|미혼의 청년", t))
    self_home = bool(re.search(r"무주택자\(본인\)", t))
    hh = bool(re.search(r"소득 및 자산 요건은 세대구성원 모두 충족", t))
    sq = re.sub(r"\s", "", t)
    scan = bool(re.search(r"세대구성원전원을대상으로[^□]{0,60}주택소유여부를확인", sq))   # Ⅷ '세대구성원 전원을 대상으로 … 주택소유 여부를 확인' — 자격은 '무주택자(본인)'인데 조회는 세대 전원
    g = dict(key="청년", name="청년(미혼)", age_min=int(am.group(1)), age_max=int(am.group(2)),
             homeless="self" if self_home else None, income_household=hh, hh_home_scan=scan,
             income_pct=None if issues else {"1": 120, "2": 110, "3+": 100}, asset_manwon=_num(am2.group(1)) if am2 else None,
             car_manwon=_num(cm.group(1)) if cm else None)
    if not single:
        g["married_ok"] = False
        issues.append("미혼 요건 문장 못 찾음")
    if not hh:
        issues.append("세대 소득·자산 문장 못 찾음")
    return {"sh": True, "income_basis": "도시근로자 월평균소득", "birth_bonus": "none", "relaxed": False, "homeless_relaxed": False,
            "groups": [g], "issues": issues}


def parse_sh_terms(text: str, kind: str) -> dict | None:
    if kind == "신혼·신생아 매입임대":
        return parse_newlywed(text)
    if kind == "청년 매입임대":
        return parse_youth(text)
    return None
