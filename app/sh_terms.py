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

URBAN_2025 = {1: 3813363, 2: 5866270, 3: 8168429, 4: 8802202, 5: 9326985, 6: 9906263}   # docs/index.html RENT_URBAN_2025 와 같은 값 (공고문 표로 확인)


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


def _row_ok(t: str, label: str, pct: int, n: int = 6) -> list[str]:
    """'기준 105% 4,004,031원 6,159,584원 …'(1~6인) 줄이 도시근로자 2025 × pct 와 같은지"""
    m = re.search(re.escape(label) + rf" ?{pct}% " + " ".join([r"([\d,]+)원"] * n), t)
    if not m:
        return [f"{pct}% 줄 없음"]
    return [f"{pct}% {k}인 {v} ≠ {round(URBAN_2025[k] * pct / 100)}" for k, v in zip(range(1, n + 1), m.groups())
            if abs(_num(v) - round(URBAN_2025[k] * pct / 100)) > 1]


def parse_jeonse(text: str) -> dict | None:
    """SH 장기전세주택 (기능 sh_jeonse, 2026-10-07 제51차 공고문으로 확인).
    '입주자 모집 공고일 현재 서울특별시에 거주하는 성년자인 무주택세대구성원' · 소득은 신청주택 면적별(60㎡ 이하: 건설형 1·2순위 70%, 3·4순위·매입형 105%(맞벌이 140%) /
    60㎡ 초과 150%(맞벌이 200%)) · 출산가구 +10/20%p(맞벌이와 중복 없음) · 총자산·자동차(출산가구 표 금액).
    자격(어느 순위로든 신청 가능)은 면적 묶음의 가장 넓은 소득 기준으로 본다 — 60㎡ 이하 105%, 60㎡ 초과 150%. 순위(70%·청약저축 회차·거주 자치구)는 안내만."""
    t = _flat(text)
    if "장기전세" not in t or "무주택세대구성원" not in t:
        return None
    if re.search(r"미리\s?내\s?집|장기전세주택\s?(Ⅱ|II|2)", t[:3000]):   # 미리내집(장기전세Ⅱ)은 신혼·출산 가구 대상이라 기준이 다르다 — 읽지 않음
        return None
    issues: list[str] = []
    loc = re.search(r"현재 서울특별시에 거주하는 성년자인 무주택세대구성원", t)
    if not loc:
        issues.append("서울 거주·무주택세대구성원 문장 못 찾음")
    extra = re.search(r"([가-힣]+지구)는 ([가-힣]+시) 거주자 포함", t)
    small = re.search(r"60㎡ 이하 \(건설형 3·4순위, 매입형\)(.{0,600}?)60㎡ 초과", t)
    big = re.search(r"60㎡ 초과 가구원수별(.{0,700}?)(?:★|➜)", t)
    pcts = {}
    for name, seg in (("small", small), ("big", big)):
        if not seg:
            issues.append(f"{name} 소득표 못 찾음")
            continue
        sg = seg.group(0)
        b0 = re.search(r"기준 (\d+)%", sg)
        d0 = re.search(r"맞벌이인 경우 (\d+)%", sg)
        if not b0 or not d0:
            issues.append(f"{name} 기준·맞벌이 % 못 읽음")
            continue
        base, dual = int(b0.group(1)), int(d0.group(1))
        issues += _row_ok(sg, "기준", base)
        bad_d = _row_ok(sg, "맞벌이인 경우", dual, 5)   # 맞벌이 줄은 2~6인 (1인 칸 없음)
        if bad_d and "줄 없음" not in bad_d[0]:
            # 맞벌이 표는 2인부터라 1~5 로 맞춘 비교를 2~6 으로 다시
            m = re.search(rf"맞벌이인 경우 ?{dual}% " + " ".join([r"([\d,]+)원"] * 5), sg)
            bad_d = [f"맞벌이 {dual}% {k}인 {v}" for k, v in zip(range(2, 7), m.groups()) if abs(_num(v) - round(URBAN_2025[k] * dual / 100)) > 1] if m else ["맞벌이 줄 없음"]
        issues += bad_d
        pcts[name] = (base, dual)
    nostack = bool(re.search(r"출생자녀에 따른 가산과 중복적용되지 않음", t))
    if not nostack:
        issues.append("맞벌이·출산가구 가산 중복 여부 문장 못 찾음")
    am = re.search(r"가액 합산: ?([\d,]+)만원 이하 ① [^:]{0,60}: ?([\d,]+)만원 이하 ② [^:]{0,60}: ?([\d,]+)만원 이하", t)
    cm = re.search(r"보건복지부장관이 정하는 금액: ?([\d,]+)만원 이하 ① [^:]{0,60}: ?([\d,]+)만원 이하 ② [^:]{0,60}: ?([\d,]+)만원 이하", t)
    if not am:
        issues.append("총자산 기준 못 읽음")
    if not cm:
        issues.append("자동차 기준 못 읽음")
    inc_ok = not [i for i in issues if "%" in i or "소득표" in i or "중복" in i]
    common = dict(homeless="household" if loc else None,
                  asset_manwon=_num(am.group(1)) if am else None, car_manwon=_num(cm.group(1)) if cm else None)
    if am:
        common["asset_bonus"] = {"10": _num(am.group(2)), "20": _num(am.group(3))}
    if cm:
        common["car_bonus"] = {"10": _num(cm.group(2)), "20": _num(cm.group(3))}
    groups = []
    for key, gk, name, area in (("small", "일반·60이하", "전용 60㎡ 이하", {"area_max": 60}), ("big", "일반·60초과", "전용 60㎡ 초과", {"area_min": 60})):
        base, dual = pcts.get(key, (None, None))
        ok = inc_ok and base is not None
        groups.append(dict(key=gk, name=name, **area, income_pct={"1": base, "2": base, "3+": base} if ok else None,
                           dual_add=(dual - base) if ok else None, **common))
    res = {"sh": True, "kind": "장기전세", "income_basis": "도시근로자 월평균소득", "birth_bonus": "table", "income_birth": True,
           "relaxed": False, "homeless_relaxed": False, "groups": groups, "issues": issues}
    if loc:
        res["local"] = {"sido": "서울", "sigun": None, "name": "서울특별시"}
        if extra:
            res["local"]["extra"] = f"{extra.group(1)}는 {extra.group(2)} 거주자 포함"
    if small:   # 순위 안내 (판정에는 쓰지 않음)
        r1 = re.search(r"60㎡ 이하 \(건설형 1·2순위\).{0,120}?기준 (\d+)%", t)
        res["rank_note"] = (f"건설형 60㎡ 이하는 소득 {r1.group(1)}% 이하면 1·2순위, {pcts.get('small', ('?',))[0]}% 이하면 3·4순위 · "
                            "순위 안에서는 청약저축 납입 회차(24회·6회)로, 매입형 50㎡ 미만은 거주 자치구로 정해요") if r1 else None
    return res


def jeonse_schedule(text: str, posted: str | None) -> list[dict]:
    """장기전세 일정표 '1순위 접수기간 ’26.09.14.(월) ~09.15.(화) 2순위 접수기간 ’26.09.16.(수) 3·4순위 접수기간 ’26.09.17.(목)' → 순위별 접수일.
    (일반 접수 기간 읽기는 앞의 우편접수 안내 때문에 이 표를 읽지 않는다 — tests/golden/sh_rental.json 309467)"""
    t = _flat(text)
    out = []
    for m in re.finditer(r"(\d(?:·\d)?순위) 접수기간 [‘'’](\d\d)\.(\d\d)\.(\d\d)\.\(.\)(?: ?~ ?(\d\d)\.(\d\d)\.\(.\))?", t):
        a = _date(m.group(2), m.group(3), m.group(4))
        b = _date(m.group(2), m.group(5), m.group(6)) if m.group(5) else a
        if posted and not (posted <= a <= b) or any(o["rank"] == m.group(1) for o in out):
            continue
        out.append({"rank": m.group(1), "apply_start": a, "apply_end": b})
    return out


def parse_sh_terms(text: str, kind: str) -> dict | None:
    if kind == "신혼·신생아 매입임대":
        return parse_newlywed(text)
    if kind == "청년 매입임대":
        return parse_youth(text)
    if kind == "장기전세":
        return parse_jeonse(text)
    return None
