"""LH 임대 공고문에서 입주 자격 조건을 읽는다 (기능 lh_rental, 2026-10-05).

기존 분양 공고문 읽기(app/notice_pdf.py)와 따로 둔다 — 분양 판정에 영향이 없게.
읽는 것: 자격 완화 여부, 계층(대학생·청년·신혼부부·한부모·고령자·주거급여수급자·일반)별
무주택 범위, 소득 기준(퍼센트 또는 '배제'), 총자산·자동차 한도(만원 또는 '배제'), 소득 100% 금액표.
못 읽은 값은 None — 화면은 '공고문 확인'으로 보여주고 추측하지 않는다.
정답 데이터: tests/golden/lh_rental.json (공고문 원문을 읽어 확인한 값), 시험: tests/test_lh_terms.py.

근거 법령: 공공주택 특별법 시행규칙 별표 3(영구임대)·4(국민임대)·5(행복주택)·5의2(통합공공임대) —
법령 표는 퍼센트만 정하고 금액(총자산·자동차·소득 금액)은 공고문에 있다(evidence/law/public/)."""
from __future__ import annotations

import re
from typing import Optional

# 2025년 도시근로자 가구원수별 월평균소득 100% (1~8인, 원) — 화면 RENT_URBAN_2025 와 같아야 한다(tests/test_lh_terms.py). 수집이 공고문 표와 대조해 다르면 기록한다.
URBAN_2025 = {1: 3813363, 2: 5866270, 3: 8168429, 4: 8802202, 5: 9326985, 6: 9906263, 7: 10485541, 8: 11064819}

GROUP_KEYS = ("대학생", "청년", "신혼부부·한부모", "고령자", "주거급여수급자", "일반")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def _manwon(num: str, unit: str) -> int:
    v = _int(num)
    return v * 100 if unit.startswith("백만") else v // 10000 if unit == "원" else v


def _q(t: str, m, before=40, after=80) -> str:
    return t[max(0, m.start() - before): m.end() + after].strip()


def is_relaxed(t: str, name: str = "") -> bool:
    return bool(re.search(r"자격\s?완화|입주자격완화", name)) or bool(re.search(r"입주자격\s?완화\s?(주요내용|모집|조건|등)|【완화조건】|요건을 아래와 같이 완화|입주자격 요건\([^)]*\)을 완화", t))


# ── 국민임대·영구임대 (계층 하나 '일반') ─────────────────────────────────────────

def _base_section(t: str) -> str:
    m = re.search(r"■\s?소득\s?및\s?자산\s?보유\s?기준", t) or re.search(r"소득\s?및\s?자산\s?보유\s?기준\s?■\s?구분", t)
    return t[m.start(): m.start() + 2600] if m else ""


def _relax_section(t: str) -> str:
    m = re.search(r"입주자격\s?완화\s?(주요내용|내용)|완화조건|소득·총자산 배제|소득기준을 완화", t)
    return t[m.start(): m.start() + 900] if m else ""


def _general_terms(t: str, kind: str) -> tuple[dict, dict]:
    sec, rel = _base_section(t), _relax_section(t)
    both = rel + " " + sec
    q: dict = {}
    # 소득
    income = None
    m = (re.search(r"소득\s?(?:\(금회 배제\)|금회\s?소득배제|•\s?적용배제|•?\s?소득\s?기준\s?적용하지\s?아니함)", sec)
         or re.search(r"소득\s?기준\s?:\s?[^.]{0,40}요건\s?배제", sec)
         or re.search(r"소득\s?기준\s?가구원수별\s?소득기준\s?적용\s?(?:→|☞)\s?적용\s?배제", rel)
         or re.search(r"소득요건\s?소득요건\s?배제", rel))
    if m:
        income, q["income"] = "excluded", _q(both, m) if m.re.pattern.find("→") < 0 else _q(rel, m)
    else:
        m = (re.search(r"(?:월평균\s?소득의?|월평균)\s?150%\s?이하", both) or re.search(r"소득완화\s?조건[^.]{0,120}?150%", both)
             or re.search(r"월평균소득\s?70%\s?이하\s?☞\s?전년도\s?월평균소득의\s?150%\s?이하", both))
        if m:
            income, q["income"] = {"1": 150, "2": 150, "3+": 150}, _q(both, m)
        elif kind == "영구임대" and (m := re.search(r"월평균\s?소득\s?50%(?:\s?\(1인\s?70%,\s?2인\s?60%\))?\s?이하\s?:\s?차목", sec)):
            if re.search(r"1인\s?(?:가구\s?)?20%p?,?\s?2인\s?(?:가구\s?)?10%p?", sec) or "1인 70%, 2인 60%" in m.group(0):
                income, q["income"] = {"1": 70, "2": 60, "3+": 50}, _q(sec, m, 10, 120)
        elif kind == "국민임대" and (m := re.search(r"월평균\s?소득\s?\(원\)\s?70%\s?80%\s?90%", sec)):
            if (m2 := re.search(r"1인\s?가구\s?20%p?\s?가산,\s?2인\s?가구\s?10%p?\s?가산", sec)):
                income, q["income"] = {"1": 90, "2": 80, "3+": 70}, _q(sec, m, 10, 10) + " … " + m2.group(0)
    # 총자산
    asset = None
    m = (re.search(r"총자산가액\s?(?:\(금회 배제\)|금회\s?자산배제|•\s?자산\s?기준\s?적용하지\s?아니함)", sec)
         or re.search(r"총자산\s?기준\s?\(총자산\s?배제\)", sec)
         or re.search(r"총자산\s?기준\s?[\d,]+만원\s?이하\s?(?:→|☞)\s?적용\s?배제", rel)
         or re.search(r"총자산\s?요건\s?총자산\s?요건\s?배제", rel)
         or re.search(r"소득\s?및\s?총자산\s?완화\s?입주자", sec))
    if m:
        asset, q["asset"] = "excluded", _q(sec if m.string is sec else rel, m)
    elif (m := re.search(r"총\s?자산(?:가액)?[^.]{0,80}?합\s?산\s?기준\s?\(?\s?([\d,]+)\s?\)?\s?(백만원|만원)\s?이하", sec)) or \
            (m := re.search(r"총자산가액\s?합산기준\s?([\d,]+)(만원)\s?이하", sec)):
        asset, q["asset"] = _manwon(m.group(1), m.group(2)), _q(sec, m, 10, 10)
    elif (m := re.search(r"총자산가액\s?합산기준\s?(백만원|만원)\s?이하\s?\(\s?([\d,]+)\s?\)", sec)):   # PDF 글 순서가 뒤집힌 표 (태백철암1)
        asset, q["asset"] = _manwon(m.group(2), m.group(1)), _q(sec, m, 10, 10)
    # 자동차
    car = None
    m = (re.search(r"개별\s?자동차가액(?:\s?중\s?높은\s?차량가액이)?\s?\(?\s?([\d,]+)\s?\)?\s?만원\s?이하", sec)
         or re.search(r"개별\s?자동차가액\s?만원\s?이하\s?\(\s?([\d,]+)\s?\)", sec)
         or re.search(r"자동차가액\s?(?:\(금회 적용\))?\s?•\s?([\d,]+)만원\s?이하", sec))
    if m:
        car, q["car"] = _int(m.group(1)), _q(sec, m, 10, 10)
    elif (m := re.search(r"자동차\s?기준\s?([\d,]+)만원\s?이하\s?(?:→|☞)\s?([\d,]+)만원\s?이하", rel)):
        car, q["car"] = _int(m.group(2)), _q(rel, m, 5, 10)
    g = {"key": "일반", "name": "일반", "homeless": "household", "income_pct": income, "asset_manwon": asset, "car_manwon": car,
         "age_min": None, "age_max": None}
    if kind == "국민임대" and re.search(r"고령자|효도주택|주거약자", t[:3000]) and (re.search(r"만\s?65세\s?이상", _relax_section(t) + sec) or re.search(r"65세\s?이상\s?주거약자용\s?효도주택", t)):
        g.update(key="고령자", name="고령자(만65세 이상)", age_min=65)
    return g, q


# ── 행복주택 (계층별 절 '3-1. 대학생 계층' …) ──────────────────────────────────────

_HH = [("대학생", r"대학생"), ("청년", r"청년(?:\s?창업인)?"), ("신혼부부·한부모", r"신혼부부\s?[·ㆍ]\s?한부모가족"), ("고령자", r"고령자"), ("주거급여수급자", r"주거급여\s?수급자")]


def _happy_groups(t: str) -> tuple[list[dict], dict]:
    heads = []
    for key, pat in _HH:
        for m in re.finditer(r"\b\d-\d\.\s?(?:" + pat + r")(?:\s?계층)?\s", t):
            heads.append((m.start(), key))
    heads.sort()
    bounds = sorted(m.start() for m in re.finditer(r"\b\d-\d\.\s", t))
    groups, quotes = [], {}
    seen = set()
    for i, (pos, key) in enumerate(heads):
        if key in seen:
            continue
        seen.add(key)
        end = next((b for b in bounds if b > pos), pos + 9000)
        seg = t[pos:end]
        seg_main = re.sub(r"\(\s?일\s?반\s?요건\s?:[^)]*\)", " ", seg)     # 완화 공고의 '(일반요건: …)' 괄호는 원래 기준이라 뺀다
        g = {"key": key, "name": key, "homeless": "self" if key in ("대학생", "청년") else "household",
             "income_pct": None, "asset_manwon": None, "car_manwon": None,
             "age_min": 19 if key == "청년" else 65 if key == "고령자" else None, "age_max": 39 if key == "청년" else None}
        q = {}
        if key == "주거급여수급자":
            groups.append(g); quotes[key] = q
            continue
        if (m := re.search(r"소득\s?(?:요건|기준)\s?배제", seg_main)):
            g["income_pct"], q["income"] = "excluded", _q(seg_main, m, 20, 10)
        elif (m := re.search(r"월평균소득의\s?(\d{2,3})\s?퍼센트\s?이하[^.]{0,30}?1인인\s?경우에는\s?(\d{2,3})\s?퍼센트,\s?2인인\s?경우에는\s?(\d{2,3})\s?퍼센트", seg_main)):
            g["income_pct"], q["income"] = {"1": int(m.group(2)), "2": int(m.group(3)), "3+": int(m.group(1))}, _q(seg_main, m, 10, 10)
        elif key == "신혼부부·한부모" and (m := re.search(r"월평균소득의\s?(\d{2,3})\s?퍼센트[^.]{0,80}?가구원\s?수가\s?2인인\s?경우에는\s?(\d{2,3})\s?퍼센트", seg_main)):
            g["income_pct"], q["income"] = {"1": None, "2": int(m.group(2)), "3+": int(m.group(1))}, _q(seg_main, m, 10, 10)
        # PDF 글 순서가 섞여 대학생 ④(본인 자산·차량)가 청년 절 뒤에 오는 공고문이 있다(익산제3일반산단) — 대학생 문구는 '신청자 본인'으로 가려 문서 전체에서 찾는다
        whole = re.sub(r"\(\s?일\s?반\s?요건\s?:[^)]*\)", " ", t) if key == "대학생" else seg_main
        if key == "대학생":
            seg_main = re.sub(r"신청자\s?본인이\s?자동차가액\s?산출대상[^.]{0,30}", " ", seg_main)
            m = re.search(r"총\s?자산\s?(?:가액|요건)\s?배제\s?\(단,\s?신청자\s?본인이", whole) or re.search(r"신청자\s?본인의\s?총\s?자산가액\s?합산기준이\s?([\d,]+)\s?만원\s?이하", whole)
            if m:
                g["asset_manwon"], q["asset"] = ("excluded" if "배제" in m.group(0) else _int(m.group(1))), _q(whole, m, 20, 10)
        else:
            seg_main = re.sub(r"총\s?자산요건\s?배제\s?\(단,\s?신청자\s?본인이[^)]*\)", " ", seg_main)
        if g["asset_manwon"] is not None:
            pass
        elif (m := re.search(r"총\s?자산\s?(?:가액|요건)\s?배제", seg_main)):
            g["asset_manwon"], q["asset"] = "excluded", _q(seg_main, m, 20, 10)
        elif (m := re.search(r"총\s?자산\s?(?:합산)?가액(?:\s?합산\s?기준)?이?\s?([\d,]+)\s?만원\s?이하", seg_main)):
            g["asset_manwon"], q["asset"] = _int(m.group(1)), _q(seg_main, m, 30, 10)
        if key != "대학생" and (m := re.search(r"자동차\s?가액[이은]?\s?([\d,]+)\s?만원\s?이하", seg_main)):
            g["car_manwon"], q["car"] = _int(m.group(1)), _q(seg_main, m, 20, 10)
        elif key == "대학생" and (m := re.search(r"자동차가액\s?산출대상\s?자동차를\s?소유하고\s?있지\s?않을\s?것", whole)):
            g["car_manwon"], q["car"] = 0, _q(whole, m, 20, 0)
        groups.append(g); quotes[key] = q
    return groups, quotes


# ── 통합공공임대 (● 청년 / ● 신혼부부ㆍ한부모가족 / ● 고령자 / ● 일반) ───────────────────

def _integrated_groups(t: str) -> tuple[list[dict], dict]:
    groups, quotes = [], {}
    asset = car = None
    qa = {}
    if (m := re.search(r"자산기준\s?:\s?총자산\s?([\d,]+)원\s?및\s?자동차\s?([\d,]+)원\s?이하", t)) or \
            (m := re.search(r"총자산가액\s?([\d,]+)원\s?이하\s?[\d,]+원\s?이하\s?[\d,]+원\s?이하\s?자동차가액\s?([\d,]+)원\s?이하", t)):
        asset, car = _int(m.group(1)) // 10000, _int(m.group(2)) // 10000
        qa = {"asset": _q(t, m, 10, 10), "car": _q(t, m, 10, 10)}
    m0 = re.search(r"일반공급\s?■\s?신청가능\s?소득ㆍ?·?자산기준", t)
    start = m0.start() if m0 else 0
    for key, pat in (("청년", r"청년"), ("신혼부부·한부모", r"신혼부부\s?[ㆍ·]\s?한부모가족"), ("고령자", r"고령자"), ("일반", r"일반")):
        m = re.search(r"●\s?" + pat + r"\s", t[start:])
        if not m:
            continue
        seg = t[start + m.start(): start + m.start() + 900]
        g = {"key": key, "name": key, "homeless": "self" if key == "청년" else "household", "income_pct": None,
             "asset_manwon": asset, "car_manwon": car, "age_min": 18 if key == "청년" else 65 if key == "고령자" else None,
             "age_max": 39 if key == "청년" else None}
        q = dict(qa)
        if (mi := re.search(r"기준\s?중위소득의\s?(\d{2,3})\s?퍼센트", seg)):
            base = int(mi.group(1))
            if key == "신혼부부·한부모":
                g["income_pct"] = {"1": None, "2": base + 10, "3+": base}
            else:
                g["income_pct"] = {"1": base + 20, "2": base + 10, "3+": base}
            q["income"] = _q(seg, mi, 30, 60)
            if not re.search(r"1~2인\s?가구|2인\s?가구", seg[mi.start(): mi.start() + 120]):
                g["income_pct"] = None   # 가산 문장을 확인하지 못하면 퍼센트를 만들지 않는다
        if key == "청년" and (ma := re.search(r"(\d{2})세\s?이상\s?(\d{2})세\s?이하", seg)):
            g["age_min"], g["age_max"] = int(ma.group(1)), int(ma.group(2))
        groups.append(g); quotes[key] = q
    return groups, quotes


def income_table(t: str) -> Optional[dict]:
    """소득 100% 금액표 (월, 원). 행복주택 '가구원수 … 100% 110% 120%' 표, 통합공공임대 기준 중위소득 '~100%' 열."""
    out = {}
    for m in re.finditer(r"([3-6])인\s?([\d,]{9,10})원\s?이하\s?100%", t):
        out.setdefault(m.group(1), _int(m.group(2)))
    if out:
        return out
    m = re.search(r"소득구간\s?~30%\s?~50%\s?~70%\s?~100%", t)
    if m:
        seg = t[m.end(): m.end() + 1500]
        for n in range(1, 9):
            r = re.search(rf"{n}인\s?([\d,]+)\s([\d,]+)\s([\d,]+)\s([\d,]+)\s", seg)
            if r:
                out[str(n)] = _int(r.group(4))
        return out or None
    return None


def parse_lh_terms(text: str, kind: str, name: str = "") -> dict:
    t = flat(text)
    res = {"relaxed": is_relaxed(t, name), "homeless_relaxed": bool(re.search(r"연접\s?지역에\s?주택(?:이|을)?\s?(?:없|소유하지)", t)),
           "income_basis": None, "groups": [], "quotes": {}, "income_table_100": None}
    if kind in ("국민임대", "영구임대"):
        g, q = _general_terms(t, kind)
        res["groups"], res["quotes"] = [g], {g["key"]: q}
        res["income_basis"] = "도시근로자 월평균소득"
    elif kind == "행복주택":
        res["groups"], res["quotes"] = _happy_groups(t)
        res["income_basis"] = "도시근로자 월평균소득"
        res["income_table_100"] = income_table(t)
    elif kind == "통합공공임대":
        res["groups"], res["quotes"] = _integrated_groups(t)
        res["income_basis"] = "기준 중위소득"
        res["income_table_100"] = income_table(t)
    return res


# ── 임대조건 (보증금·월 임대료) ─────────────────────────────────────────────
# LH API 는 보증금·월세를 '공고문 참조'로만 준다. 공고문 임대조건 표의 한 줄은 '임대보증금 계 · 계약금 · 잔금 · 월 임대료' 순서라
# 계 = 계약금 + 잔금 이 맞는 네 숫자만 받는다(맞지 않으면 버림 — 추측하지 않음). 계약금 칸이 합쳐진 표(익산제3일반산단)는 앞줄 계약금으로 같은 검사를 한다.
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")


def _norm_type(s: str) -> str:
    return re.sub(r"\s|형|㎡", "", s or "")


def _rent_group(lbl: str) -> Optional[str]:
    l = re.sub(r"\s", "", lbl)
    for pat, name in ((r"「?가」?군", "가군"), (r"「?나」?군", "나군")):
        if re.search(pat, l):
            return name
    if (m := re.search(r"(\d)구간", l)):
        return f"{m.group(1)}구간"
    if re.search(r"청년\(?소득(?:無|X|없)", l):
        return "대학생·청년(소득 없음)" if "대학생" in l else "청년(소득 없음)"
    if re.search(r"소득\)?\s?(?:有|O|있)", l):
        return "청년(소득 있음)"
    if re.search(r"소득\)?\s?(?:無|X|없)", l):
        return "청년(소득 없음)"
    for pat, name in ((r"신혼부부", "신혼부부·한부모"), (r"주거급여", "주거급여수급자"), (r"고령자", "고령자"), (r"대학생", "대학생"), (r"청년", "청년")):
        if re.search(pat, l):
            return name
    return None


def parse_lh_rents(text: str, unit_types: list[str]) -> list[dict]:
    t = flat(text)
    types = sorted({_norm_type(u) for u in unit_types if u}, key=len, reverse=True)
    toks = [(m.start(), m.end(), int(m.group(0).replace(",", ""))) for m in _NUM.finditer(t)]
    rows, seen = [], set()
    cur_type, cur_complex, last_end, last_quad, last_contract = None, None, 0, None, None
    i = 0
    while i < len(toks) - 2:
        s0, e0, a = toks[i]
        found = None
        if i + 3 < len(toks):
            b, c, d = toks[i + 1][2], toks[i + 2][2], toks[i + 3][2]
            if a == b + c and b > 0 and c > 0:
                found = (a, b, d, toks[i + 3][1], 4)
        if not found and last_contract and toks[i + 1][2] and a == toks[i + 1][2] + last_contract and i + 2 < len(toks):
            found = (a, last_contract, toks[i + 2][2], toks[i + 2][1], 3)
        if not found:
            i += 1
            continue
        dep, contract, rent, end, used = found
        thousand = dep < 1_000_000 and "천원" in t[max(0, s0 - 3000): s0]   # 금액 단위가 천원인 표(군산 7개 단지·양산 삼성파크빌)
        dep_won = dep * 1000 if thousand else dep
        if not (1_000_000 <= dep_won <= 500_000_000 and 10_000 <= rent <= 3_000_000 and contract < dep):
            i += 1
            continue
        # 앞 줄과 이 줄 사이 글자에서 주택형·계층을 찾는다 (금액 숫자는 빼고)
        lbl_raw = t[last_end:s0] if last_end else t[max(0, s0 - 400):s0]
        lbl = re.sub(r"\(\s?[+\-−]\s?\)\s?[\d,]+|[\d]{1,3}(?:,\d{3})+", " ", lbl_raw)
        lbl_ns = re.sub(r"\s", "", lbl)
        lbl_full = lbl
        cut0 = max(lbl.rfind("잔금"), lbl.rfind("월임대료"), lbl.rfind("월 임대료"))
        if cut0 >= 0 and ("임대보증금" in lbl or "계약금" in lbl):
            lbl = lbl[cut0 + 2:]                 # 표 머리글 앞의 글(앞 표의 면적 등)은 먼저 보지 않는다
        if not re.search(r"(?<![\d.,])\d{2,3}(?:\.\d{1,4})?(?:\s?[A-Z]{1,2}\d?)?(?![\d,])", re.sub(r"[\d.]+\s?%", " ", lbl)):
            m_h = [x for x in re.findall(r"【([^】]{1,40})】", lbl_full) if re.search(r"\d", x)]   # 통합공공임대 '【 31 A 】 구간별 임대조건' 머리글의 주택형
            if m_h:
                lbl = m_h[-1] + " " + lbl
        lbl_t = re.sub(r"[\d.]+\s?%|\d{4}[.\-]\d{1,2}[.\-]\d{1,2}|-\s?\d{1,2}\s?-", " ", lbl)
        lbl_t = re.sub(r"(\d)\s+([A-Z]{1,2})(?![a-z])", r"\1\2", lbl_t)        # '【 31 A 】' → 31A
        hits = [m for m in re.finditer(r"(?<![\d.,])(\d{2,3}(?:\.\d{1,4})?(?:[A-Z]{1,2}\d?)?)(?!\d|,\d{3})", lbl_t)
                if 10 <= float(re.match(r"[\d.]+", m.group(1)).group(0)) <= 200]   # 주택형(전용면적) 범위 — 천원 단위 계약금 '300' 같은 금액은 뺀다
        hit = None
        if hits:
            cl = [hits[-1]]
            for m in reversed(hits[:-1]):          # '25A 25B' · '31A, 31AS, 31B' 처럼 붙어 있는 주택형은 한 줄로 묶는다
                if re.fullmatch(r"[\s,/·]*", lbl_t[m.end(): cl[0].start()]):
                    cl.insert(0, m)
                else:
                    break
            hit = (cl[0].start(), "/".join(m.group(1) for m in cl))
            gw = re.search(r"대학생|청년|신혼|고령자|주거급여|[가나]」?\s?군|\d구간", lbl_t)
            before = [m for m in hits if gw and m.end() <= gw.start()]
            if gw and before and hits[-1].start() > gw.start():      # '16 대학생 180'(180 = 예비자 수) → 계층 앞의 16
                hit = (before[-1].start(), before[-1].group(1))
        if hit:
            cur_type = hit[1]
            pre = re.sub(r"[()（）\[\]【】:]", " ", lbl_t[:hit[0]])
            mc = re.search(r"([가-힣][가-힣0-9·\- ]{0,24}[가-힣0-9])\s*$", pre)
            name = mc.group(1).strip() if mc else ""
            name = re.split(r"입주\s?시|계약\s?시|잔\s?금|계약금|임\s?대\s?료|보\s?증\s?금|\(원\)|\b원\b", name)[-1].strip()
            if re.fullmatch(r"(?:[가-힣0-9]\s)+[가-힣0-9]+", name):      # '삼 성 파 크 빌' 처럼 글자마다 띄운 표
                name = name.replace(" ", "")
            if name and not re.search(r"원$|단위|구간|주택형|공급|형별|천원|대상|계층|군$|주거약자|^원\s|최대|전환", name) and _rent_group(name) is None:
                cur_complex = name
        elif cur_type is None and len(types) == 1:
            cur_type = types[0]
        cut = max(lbl.rfind("잔금"), lbl.rfind("월임대료"), lbl.rfind("월 임대료"))   # 표 머리글(가군·나군 이름이 다 들어 있음)은 계층 판단에서 뺀다
        grp = _rent_group(lbl[cut + 2:] if cut >= 0 and ("임대보증금" in lbl or "계약금" in lbl) else lbl)
        ga_na = bool(re.search(r"가\s?군[^.]{0,80}나\s?군", t[max(0, s0 - 3000):s0]))   # 영구임대 가군·나군 표 — 계층은 가군·나군만
        if ga_na and grp not in ("가군", "나군"):
            grp = None
        back = t[max(0, s0 - 2500): s0]
        if back.rfind("상한 임대조건") > max(back.rfind("구간별 임대조건"), back.rfind("구간별임대조건")):
            grp = "생계·의료급여 수급자 등 상한"   # 통합공공임대 '[주거급여 수급자가 아닌 경우] 상한 임대조건' 표
        if grp is None and last_quad and last_quad["group"] == "가군" and last_quad["type"] == cur_type and not hit:
            grp = "나군"
        if grp is None and hit and ga_na:
            grp = "가군"
        if cur_type is None:
            i += 1
            continue
        key = (cur_complex, cur_type, grp, dep_won, rent)
        row = {"complex": cur_complex, "type": cur_type, "group": grp, "deposit": dep_won, "rent": rent}
        if key not in seen:
            seen.add(key)
            rows.append(row)
        last_quad = row
        last_end, last_contract = end, contract
        i += used
    return rows
