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


def _eok(a: str, b: str | None) -> int | None:
    """'2억 5,100만' → 25100 (만원). 만 단위가 1만 이상이면(오타 '2억5,4000만') 믿지 않음"""
    m = _num(b) if b else 0
    return None if m >= 10000 else int(a) * 10000 + m


def parse_social(text: str, posted: str | None = None) -> dict | None:
    """SH 사회주택(토지임대부·토지지원) 입주자 모집 공고 (기능 sh_social, 2026-10-07).
    공고문은 운영기관마다 형식이 다르고 소득표를 지난해 값이나 다른 비율로 적은 곳이 있어(310575·310672), 아래처럼 확실한 것만 읽는다 — 나머지는 비워 '확인':
      소득: '월평균소득의 N% 이하' 한 가지 비율 + 1~3인 표가 도시근로자 2025 × N% 와 같고(천원 단위면 1천원 안), 세대 전원 소득 문장이 있을 때만
      무주택: '무주택세대구성원 … 적용' → 세대 전원, 청년 예외('직계존속이 주택을 소유해도 본인이 무주택자' · '본인 명의로 가진 주택이 아닐 경우 무주택자') → 청년은 본인
      거주: 서울 거주(비거주자도 입주 후 전입·서울 소재 직장·학교면 신청 가능하다는 문장이 있으면 서울 밖은 '확인')
      계층: 총자산 표의 '청년 N억 M만원' · '신혼부부, (고령자,) 1인가구 N억 M만원' — 고령자는 나이 기준이 없어 판정하지 않음(모르는 계층)
      자동차: 'N만원 이하 공공임대주택 자동차가액' 한 값"""
    t = _flat(text).replace("\x00", "")
    if not re.search(r"사회주택", t):
        return None
    issues: list[str] = []
    # 소득
    pcts = sorted({int(x) for x in re.findall(r"월평균 ?소득의? ?(\d{2,3})% ?이하", t)})
    income = None
    if len(pcts) != 1:
        issues.append(f"소득 비율이 하나가 아님 {pcts}")
    elif re.search(r"본인의 세전소득|입주예정자 본인", t):
        issues.append("소득을 본인 소득으로 산정 — 판정 안 함")
    elif not re.search(r"세대 ?구성원 전원의 (?:세전)?소득|세대 ?구성원 전원의 월평균소득", t):
        issues.append("세대 전원 소득 문장 못 찾음")
    else:
        pct = pcts[0]
        m = re.search(rf"{pct}% ?이하 ?([\d,]+) ?(천원|원) ?이하 ?([\d,]+) ?(?:천원|원) ?이하 ?([\d,]+) ?(?:천원|원)", t)
        if not m:
            issues.append("소득 표 못 읽음")
        else:
            unit = 1000 if m.group(2) == "천원" else 1
            bad = [f"{n}인 {v}" for n, v in zip((1, 2, 3), (m.group(1), m.group(3), m.group(4)))
                   if abs(_num(v) * unit - URBAN_2025[n] * pct / 100) >= (1000 if unit == 1000 else 2)]
            if bad:
                issues.append(f"소득 표가 도시근로자 2025 × {pct}% 와 다름: " + ", ".join(bad))
            else:
                income = {"1": pct, "2": pct, "3+": pct}
    # 무주택
    hh = bool(re.search(r"무주택 ?세대 ?구성원 (?:전부|전원)에게 적용|무주택 ?세대 ?구성원으로서", t))
    youth_self = bool(re.search(r"청년[^.]{0,30}직계존속이 주택을 소유해도 본인이 무주택자|본인 명의로 가진 주택.{0,10}아닐 경우 무주택자", t))
    if not hh and not youth_self:
        issues.append("무주택 범위(본인·세대) 못 읽음")
    # 거주
    loc = None
    if re.search(r"서울시에 거주|서울특별시에 거주|서울시에 주소지", t):
        loc = {"sido": "서울", "sigun": None, "name": "서울시"}
        if re.search(r"비거주자|예비서울시민|거주하지 않거나|거주하지 않지만|거주하지 않으나", t):
            loc["others_check"] = "서울에 살지 않아도 서울 소재 직장·학교 등 조건(입주 후 전입)으로 신청할 수 있어요"
    # 자동차
    cars = sorted({_num(x) for x in re.findall(r"([\d,]{4,6}) ?만 ?원 이하 ?공공임대주택 자동차", t)})
    car = cars[0] if len(cars) == 1 else None
    if car is None:
        issues.append(f"자동차 기준 못 읽음 {cars}")
    # 계층(총자산 표)
    groups = []
    ym = re.search(r"청 ?년 ?(\d) ?억 ?([\d,]{1,6})? ?만 ?원 이하", t)
    om = re.search(r"(신혼부부[ ,·]*(?:고령자[ ,·]*)?(?:일반 ?)?(?:1인 ?가구)?) ?(\d) ?억 ?([\d,]{1,6})? ?만 ?원 이하", t)
    age = re.search(r"만 ?19 ?세 이상 ?[~\-–] ?만 ?39 ?세 이하|만 ?19 ?~ ?39 ?세", t)
    if ym:
        a = _eok(ym.group(1), ym.group(2))
        if a is None:
            issues.append("청년 총자산 금액 이상(만 단위 1만 이상)")
        g = dict(key="청년", name="청년", age_min=19 if age else None, age_max=39 if age else None, homeless="self" if youth_self else "household" if hh else None,
                 income_pct=income, asset_manwon=a, car_manwon=car)
        if not re.search(r"청 ?년[^.]{0,40}미혼|미혼의 청년", t):
            g["married_ok"] = True   # 미혼 요건이 없으면 혼인 여부를 보지 않음
        groups.append(g)
    unknown = []
    if om:
        a = _eok(om.group(2), om.group(3))
        lab = om.group(1)
        hl = "household" if hh else None
        if "신혼부부" in lab:
            groups.append(dict(key="신혼부부", name="신혼부부(혼인 7년 이내·예비)", homeless=hl, income_pct=income, asset_manwon=a, car_manwon=car,
                               wed_years=7 if re.search(r"혼인신고일로부터(?:\(재혼 포함\))? ?7년 이내|혼인 7년 이내", t) else None,
                               prewed=bool(re.search(r"예비 ?신혼부부", t))))
        if re.search(r"1인 ?가구", lab):
            groups.append(dict(key="1인가구", name="1인 가구", homeless=hl, income_pct=income, asset_manwon=a, car_manwon=car))   # 가구원 1명만 (화면 rentalGroup)
        if "고령자" in lab:
            unknown.append("고령자")
    if not groups:
        return None
    rm = re.search(r"모집 ?공고일 ?\(? ?(20\d\d) ?[년.] ?(\d{1,2}) ?[월.] ?(\d{1,2})", t)   # 나이·혼인 기간 기준일 = 공고문의 모집 공고일 (게시일과 다를 수 있음: 310037 공고일 09-04 · 게시 09-09)
    return {"sh": True, "kind": "사회주택", "ref_date": _date(*rm.groups()) if rm else None, "income_basis": "도시근로자 월평균소득", "birth_bonus": "none", "relaxed": False, "homeless_relaxed": False,
            "local": loc, "groups": groups, "unknown_groups": unknown, "issues": issues}


def _happy_flat(text: str) -> str:
    """SH 행복주택 공고문 글을 LH 행복주택 읽기 규칙(app/lh_terms._happy_groups)이 읽는 모양으로 맞춘다:
    절 제목 '4-2 대학생 계층' → '4-2. 대학생 계층', '4-4 (예비)신혼부부 · 한부모가족 계층' → '4-4. 신혼부부·한부모가족 계층', '25,100만 원' → '25,100만원', 가운뎃점 '・ㆍ' → '·'"""
    from app.lh_terms import flat
    f = flat(text.replace("\x00", " ")).replace("・", "·").replace("ㆍ", "·")
    f = re.sub(r"(\d)\s?만\s원", r"\1만원", f)
    f = re.sub(r"\b(\d)-(\d)\s\(예비\)\s?신혼부부\s?·\s?한부모가족", r"\1-\2. 신혼부부·한부모가족", f)
    return re.sub(r"\b(\d)-(\d)\s(?=[가-힣])", r"\1-\2. ", f)


def parse_happy(text: str) -> dict | None:
    """SH 행복주택 (기능 sh_happy, 2026-10-08 사용자 'Abc 순차로' A). 행복주택은 LH 와 같은 법령(공공주택 특별법 시행규칙 별표 5의2)이라
    계층 기준은 LH 행복주택 읽기 규칙을 그대로 쓰고(대학생·청년·신혼부부·한부모·고령자·주거급여수급자), SH 공고문에서 따로 확인하는 것:
     - 소득표 100퍼센트 줄(1인 +20%p·2인 +10%p 적힌 금액)이 도시근로자 2025 × % 와 같아야 소득 기준을 씀(다르면 소득 비움 → 화면 '공고문 확인')
     - 맞벌이 '(맞벌이 신혼부부의 경우 120퍼센트 이하)' → 신혼부부·한부모 dual_add
     - 청년 계층 '사회초년생(나이에 관계없이 … 소득이 있는 업무에 종사한 기간이 총 5년 이내)' → 청년 newcomer (나이 밖이어도 '해당 없음'이 아니라 확인)
    판정 규칙은 LH 행복주택과 같게(sh 표시 없음 — 혼인 7년·6세 이하 자녀는 공고일 기준 7년)."""
    from app.lh_terms import _happy_groups, unknown_happy_groups
    f = _happy_flat(text)
    if not re.search(r"행복주택", f):
        return None
    groups, quotes = _happy_groups(f)
    if not groups:
        return None
    issues: list[str] = []
    m = re.search(r"월평균소득의\s?100퍼센트\s?공통[^\d]{0,60}?([\d,]{9}) ([\d,]{9}) ([\d,]{9}) ([\d,]{9}) ([\d,]{9})", f)
    if not m:
        issues.append("소득표(100퍼센트 줄) 못 읽음")
    else:
        for n, v, add in zip((1, 2, 3, 4, 5), m.groups(), (20, 10, 0, 0, 0)):
            want = round(URBAN_2025[n] * (100 + add) / 100)
            if abs(_num(v) - want) > 1:
                issues.append(f"소득표 {n}인 {v} ≠ 도시근로자 2025 × {100 + add}% {want:,}")
    if issues:
        for g in groups:
            if isinstance(g.get("income_pct"), dict):
                g["income_pct"] = None
    for g in groups:
        if g["key"] == "신혼부부·한부모" and isinstance(g.get("income_pct"), dict) and g.get("dual_add") is None:
            md = re.search(r"맞벌이\s?신혼부부의\s?경우\s?(\d{3})\s?퍼센트\s?이하", f)
            if md and g["income_pct"].get("3+"):
                g["dual_add"] = int(md.group(1)) - g["income_pct"]["3+"]
        if g["key"] == "청년" and re.search(r"사회초년생\)?\s?나이에\s?관계없이", f):
            g["newcomer"] = True
        for k in ("asset_manwon", "car_manwon", "income_pct", "homeless"):
            if g["key"] != "주거급여수급자" and g.get(k) is None:
                issues.append(f"{g['key']} {k} 못 읽음")
    md = re.search(r"입주자\s?모집\s?공고일\s?\(\s?(20\d\d)\.\s?(\d{1,2})\.\s?(\d{1,2})\.?\s?\)", f)   # 나이·혼인 7년의 기준일 (게시판 등록일과 다를 수 있음 — 정정 공고)
    if not md:
        issues.append("모집공고일 못 읽음")
    out = {"kind": "행복주택", "ref_date": _date(*md.groups()) if md else None, "income_basis": "도시근로자 월평균소득", "relaxed": False, "homeless_relaxed": False, "groups": groups,
           "unknown_groups": unknown_happy_groups(f), "issues": issues}
    if any(g["key"] == "신혼부부·한부모" for g in groups):
        out["prewed_ok"] = bool(re.search(r"예비\s?신혼부부", f))
    return out


def _bonus_sentence(seg: str) -> dict | None:
    """출산가구 문장: '… 이후 출생한 자녀가 1명인 경우, 39,600만원 이하 [단, … 43,100만원 이하] ※ … 2명 이상인 경우, 43,100만원 이하' → {'10': 39600, '20': 43100}"""
    m = re.search(r"이후\s?출생한\s?자녀(?:\([^)]{0,20}\))?가\s?1명인\s?경우,\s?([\d,]+)만원\s?이하\s?\[단,[^\]]{0,80}?([\d,]+)만원\s?이하\]\s?※[^※]{0,80}?2명\s?이상인\s?경우,\s?([\d,]+)만원\s?이하", seg)
    if not m:
        return None
    a, b, c = (_num(x) for x in m.groups())
    return {"10": a, "20": b} if b == c else None


def parse_youth_safe(text: str) -> dict | None:
    """SH 청년안심주택(공공임대) (기능 sh_youth_safe, 2026-10-08 사용자 'Abc 순차로' A).
    청년 계층: 만 19~39세·미혼·본인 무주택. 순위마다 소득·자산 기준이 다르다 — 1순위 수급자·차상위·보호대상 한부모(소득·자산 심사 없음),
      2순위 본인+부모 소득 100%(1인 +20%p·2인 +10%p)·본인+부모 총자산 34,500만원, 3순위 본인 소득 1인 기준 120%·본인 총자산 25,100만원·자동차 4,542만원.
      판정은 3순위(본인 기준)로 하고, 넘으면 '2·1순위면 가능할 수 있음'으로 확인(self_basis·tier_asset·tier_note). 자동차는 모든 순위 같아 넘으면 미충족.
    신혼부부 계층: 신혼부부Ⅰ(소득 70%·맞벌이 90%, 34,500만원·자동차 4,542만원)을 충족하면 Ⅱ(130%·200%, 36,200만원, 자동차는 총자산에 합산)도 충족하므로
      자격은 Ⅱ 기준으로 판정(신생아가구·보호대상 한부모·신혼부부/예비/6세 이하 자녀 가구·혼인가구), 만 19~39세 신청자.
    공고문 소득표 금액은 도시근로자 2025 × % 와 같을 때만 쓴다(다르면 그 계층 소득 비움)."""
    t = _flat(text.replace("\x00", " "))
    if not re.search(r"청년안심주택", t):
        return None
    issues: list[str] = []
    mr = re.search(r"입주자\s?모집\s?공고일\s?\(\s?(20\d\d)\.\s?(\d{1,2})\.\s?(\d{1,2})\.?\s?\)", t)
    if not mr:
        issues.append("모집공고일 못 읽음")
    groups: list[dict] = []
    # ── 청년 ──
    i, j = t.find("5-1 청년 계층"), t.find("5-2 신혼부부 계층")
    ys = t[i:j] if 0 <= i < j else ""
    if ys:
        am = re.search(r"(\d{2})세 이상 (\d{2})세 이하인 무주택자,\s?미혼", ys)
        self_home = bool(re.search(r"무주택\s?요건\s?충족은\s?본인에\s?한하며", ys))
        m3 = re.search(r"3순위 일반 - 1, 2순위에 해당하지 아니하는 사람 중 본인의 월평균소득이 전년도 도시근로자 가구원수별 가구당 월평균소득의 (\d+)% 이하", ys)
        a3 = re.search(r"본인의 자산이 행복주택\(청년\)의 자산기준을 충족 \(총자산 ([\d,]+)만원 이하, 개별 자동차 ([\d,]+)만원 이하\)", ys)
        a2 = re.search(r"본인과 부모의 자산이[^()]{0,80}국민임대 주택의 자산기준을 충족 \(총자산 ([\d,]+)만원 이하, 개별 자동차 ([\d,]+)만원 이하\)", ys)
        m2 = re.search(r"2순위 일반 - 본인과 부모의 월평균소득이 전년도 도시근로자 가구원수별 가구당 월평균소득의 (\d+)% 이하", ys)
        tb = re.search(r"1인가구\(\+20%p\) 2인가구\(\+10%p\) 3인가구[^\d]{0,60}50%이하 [\d,]+ [\d,]+ [\d,]+ 100%이하 ([\d,]+) ([\d,]+) ([\d,]+)", ys)
        inc = None
        if not (m3 and tb):
            issues.append("청년 소득 기준(3순위·소득표) 못 읽음")
        else:
            bad = [f"청년 소득표 {n}인 {v} ≠ {round(URBAN_2025[n] * (int(m3.group(1)) + ad) / 100):,}" for n, v, ad in zip((1, 2, 3), tb.groups(), (20, 10, 0))
                   if abs(_num(v) - round(URBAN_2025[n] * (int(m3.group(1)) + ad) / 100)) > 1]
            issues += bad
            inc = None if bad else {"1": int(m3.group(1)) + 20}
        if not am:
            issues.append("청년 나이·미혼 문장 못 찾음")
        if not self_home:
            issues.append("청년 무주택 범위 못 읽음")
        if not a3:
            issues.append("청년 3순위 자산 기준 못 읽음")
        if a2 and a3 and _num(a2.group(2)) != _num(a3.group(2)):
            issues.append("청년 순위별 자동차 기준이 다름")
        g = dict(key="청년", name="청년 (3순위: 본인 소득·자산 기준)", age_min=int(am.group(1)) if am else None, age_max=int(am.group(2)) if am else None,
                 homeless="self" if self_home else None, self_basis=True, birth_bonus="none", income_pct=inc,
                 asset_manwon=_num(a3.group(1)) if a3 else None, car_manwon=_num(a3.group(2)) if a3 else None)
        if a2 and m2:
            g["tier_asset"] = _num(a2.group(1))
            g["tier_note"] = (f"2순위(본인·부모 소득 합계 {m2.group(1)}% 이하·본인·부모 총자산 {_num(a2.group(1)):,}만원 이하) 또는 "
                              "1순위(생계·의료·주거급여 수급자·차상위계층 가구·보호대상 한부모가족, 소득·자산 심사 없음)면 신청할 수 있어요 (공고문 확인)")
        else:
            issues.append("청년 2순위 기준 못 읽음")
        groups.append(g)
    # ── 신혼부부 (Ⅱ 기준) ──
    i, j = t.find("■ 신혼부부Ⅱ"), t.find("■ 공통사항")
    ns = t[i:j] if 0 <= i < j else ""
    if ns:
        ag = re.search(r"(\d{2})세 이상 (\d{2})세 이하인 무주택세대\s?구성원", ns)
        mp = re.search(r"월평균\s?소득의 (\d+)% 이하\(배우자가 소득이 있는 경우 (\d+)%\)", ns)
        pct, dual = (int(mp.group(1)), int(mp.group(2))) if mp else (None, None)
        add2 = 10 if re.search(r"2인가구는 기준금액에 10%p 가산", ns) else 0
        bad = ["신혼부부Ⅱ 소득 퍼센트 못 읽음"] if pct is None else [f"신혼부부Ⅱ {x}" for x in _check_income_table(ns, pct, dual, add2)]
        issues += bad
        income_pct = None if bad else {"2": pct + add2, "3+": pct}
        am = re.search(r"총자산가액 ?: ?([\d,]+)만원 이하", ns)
        car = "none" if re.search(r"자동차가액은 총자산에 합산됨", ns) and not re.search(r"자동차가액 ?[\d,]+만원 이하", ns) else None
        bm = re.search(r"신생아 가구 ● 공고일로부터 최근 2년 이내 출산한 자녀가 있는 가구 \((20\d\d)\.(\d{2})\.(\d{2})\. 이후 태어난 자녀 및 태아\)", ns)
        wm = re.search(r"혼인 7년 이내\((20\d\d)\.\s?(\d{2})\.\s?(\d{2})\.\s?~", ns)
        km = set(re.findall(r"6세 이하 자녀[^()]{0,20}\((20\d\d)\.(\d{2})\.(\d{2})\. 이후 출생한 자녀 및 태아\)", ns))
        exempt = bool(re.search(r"보호대상 한부모가족, 차상위계층은 소득·자산\s?검증\s?불필요", ns))
        base = dict(homeless="household", income_pct=income_pct, dual_add=(dual - pct) if (dual and income_pct) else None,
                    asset_manwon=_num(am.group(1)) if am else None, car_manwon=car,
                    age_min=int(ag.group(1)) if ag else None, age_max=int(ag.group(2)) if ag else None)
        if (bo := _bonus_sentence(ns)):
            base["asset_bonus"] = bo
        if not ag:
            issues.append("신혼부부 나이 기준 못 읽음")
        if car is None:
            issues.append("신혼부부Ⅱ 자동차 기준 못 읽음")
        groups.append(dict(key="신생아가구", name="신생아가구", born_from=_date(*bm.groups()) if bm else None, **base))
        groups.append(dict(key="지원대상한부모", name="보호대상 한부모가족", exempt=True, homeless="household",
                           income_pct="excluded", asset_manwon="excluded", car_manwon="excluded", age_min=base["age_min"], age_max=base["age_max"])
                      if exempt else dict(key="지원대상한부모", name="보호대상 한부모가족", exempt=False, **base))
        groups.append(dict(key="신혼부부·한부모", name="신혼부부·예비신혼부부·6세 이하 자녀 가구", wed_from=_date(*wm.groups()) if wm else None,
                           kid6_from=_date(*km.pop()) if len(km) == 1 else None, **base))
        if re.search(r"혼인가구\(5순위\)", ns):
            groups.append(dict(key="혼인가구", name="혼인가구", **base))
    if not groups:
        return None
    return {"sh": True, "kind": "청년안심주택", "ref_date": _date(*mr.groups()) if mr else None, "income_basis": "도시근로자 월평균소득",
            "birth_bonus": "table", "prewed_ok": bool(re.search(r"예비신혼부부", ns)), "relaxed": False, "homeless_relaxed": False,
            "groups": groups, "issues": issues}


def parse_sh_terms(text: str, kind: str) -> dict | None:
    if kind == "신혼·신생아 매입임대":
        return parse_newlywed(text)
    if kind == "청년 매입임대":
        return parse_youth(text)
    if kind == "장기전세":
        return parse_jeonse(text)
    if kind == "사회주택":
        return parse_social(text)
    if kind == "행복주택":
        return parse_happy(text)
    if kind == "청년안심주택":
        return parse_youth_safe(text)
    return None
