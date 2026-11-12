"""규칙이 못 읽은 LH 임대 공고문을 AI(Claude)가 대신 읽는다 (기능 ai_read, 2026-11-11 운영자 '처음 보는 형태도 잘 읽게 — 방법 1 실패하면 방법 2').

순서: ① 읽기 규칙(엄격) → ② 띄어쓰기를 무시한 읽기(기능 loose_read) → ③ 그래도 비어 있는 칸이 있으면 여기.
AI 가 준 값은 그대로 믿지 않는다. 값마다 **근거 문장**을 함께 받게 하고, 아래 검사를 통과한 값만 **비어 있던 칸**에 채운다:
  - 근거 문장이 공고문 원문에 글자 그대로 있어야 한다(빈칸만 무시)
  - 값의 숫자·낱말이 그 근거 문장 안에 있어야 한다 (총자산 34,500만원 → 문장에 '34,500' 또는 '345,000,000' 등)
  - 값이 범위 안이어야 한다 (소득 50~250%, 총자산 5천만~6억, 자동차 0~1억 …)
규칙이 읽은 값은 바꾸지 않는다. 채운 칸은 terms['ai'] 에 남고, 화면은 그 공고를 '확인 필요'까지만 보여 준다('신청 가능해 보여요'로 단정하지 않음).
아침 자동 고치기가 원문과 맞춰 본 뒤 읽기 규칙·정답 데이터를 더하면 그때부터 규칙이 읽은 값으로 바뀐다.

**수집은 AI(API)를 부르지 않는다** (2026-11-12 운영자: ANTHROPIC_API_KEY 는 청약봇 전용). 11-11 하루는 수집이 Claude API 를 불렀고 그때 답 파일이 남아 있다.
지금은 세션(운영자와 일하는 Claude·아침 자동 고치기)이 공고문을 직접 읽어 답 파일(evidence/lh/ai/<공고ID>.json·evidence/notices/ai/<번호>.json)을 쓰고(tools/ai_answer.py),
수집은 그 답을 아래 검사기에 통과시켜 쓴다. 답 파일이 없는 공고는 `[공고문·AI 읽기] … 답 파일 없음` 줄을 남기고 '공고문 확인' 그대로 둔다.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.lh_terms import GROUP_KEYS, SIDO_SHORT

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "evidence" / "lh" / "ai"
PROMPT_V = 2                        # 지시문을 바꾸면 올린다 (올리면 저장해 둔 답을 다시 받는다)
MAX_CHARS = 150_000
KST = timezone(timedelta(hours=9))

SIDOS = set(SIDO_SHORT.values())
_EXCL = r"배제|불문|관계없이|상관없|적용하지|미적용|적용제외|무관|묻지않"

SYSTEM = """당신은 한국토지주택공사(LH) 임대주택 입주자 모집공고문에서 신청 자격 기준을 뽑아내는 도구입니다.
공고문에 **글자로 적혀 있는 것만** 뽑습니다. 추측하지 않습니다. 확실하지 않거나 공고문에 없으면 null 입니다.
값마다 근거 문장(quote)을 붙입니다. quote 는 공고문에서 **한 글자도 바꾸지 말고 그대로 복사한 이어진 글**(15~200자)이어야 하고, 그 값의 숫자·낱말이 quote 안에 들어 있어야 합니다.
여러 곳의 글을 이어 붙이거나 요약하면 안 됩니다. 답은 JSON 하나만 출력합니다(설명·코드블록 표시 없이).

출력 형식:
{
 "groups": [   // 공고문이 자격을 나눈 계층. key 는 "대학생","청년","신혼부부·한부모","고령자","주거급여수급자","일반" 중 하나. 계층 구분이 없으면 "일반" 하나
  {"key": "일반",
   "homeless": "household" | "self" | "household_or_single_self" | null,
        // household = 무주택세대구성원(세대원 전원 무주택) · self = 신청자 본인만 무주택(무주택자)
        // household_or_single_self = '무주택세대구성원(혼인 중이 아닌 경우로서 단독세대주로 입주하려는 사람은 무주택자)'처럼 단독세대주 예외가 붙은 문장
   "homeless_quote": "...",                      // '무주택세대구성원'·'무주택자' 같은 낱말이 들어 있는 문장. 괄호 속 예외가 붙어 있으면 그 괄호까지 포함
   "income_pct": {"1": 90, "2": 80, "3+": 70} | "excluded" | null,   // 가구원 수(1인·2인·3인 이상)별 소득 상한 퍼센트. 1인·2인 가산(예: +20%p, +10%p)이 적혀 있으면 더한 값. "excluded" = 이번 모집은 소득 기준을 보지 않는다고 적혀 있음
   "income_quote": "...",
   "asset_manwon": 34500 | "excluded" | null,    // 총자산 한도(만원). "excluded" = 총자산 기준을 보지 않는다고 적혀 있음
   "asset_quote": "...",
   "car_manwon": 4542 | 0 | "excluded" | null,   // 자동차가액 한도(만원). 0 = 자동차를 가지면 안 됨. "excluded" = 자동차 기준을 보지 않는다고 적혀 있음
   "car_quote": "...",
   "age_min": 19 | null, "age_max": 39 | null, "age_quote": "..."}
 ],
 "regions": ["충북"] | [] | null,   // (공공임대만) 신청할 수 있는 거주 시·도. 약칭(서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주). [] = 거주지역 제한이 없다고 적혀 있음
 "regions_quote": "...",
 "account": {"months": 6, "count": 6, "rank2_any": true} | "none" | null,   // (공공임대만) 1순위 청약통장 가입 개월 수·납입 횟수. rank2_any = 2순위는 가입만 되어 있으면 됨. "none" = 청약통장이 필요 없다고 적혀 있음
 "account_quote": "...",
 "local": {"name": "부산광역시", "sido": "부산", "sigun": null} | null,   // (공공임대가 아닌 유형만) 신청자격 첫 문장의 거주 요건 '모집공고일 현재 ○○에 거주하는 …'. 시·군이면 sigun 에 그 이름, 광역시·특별시 전체면 null
 "local_quote": "...",
 "other_groups": ["장기종사자"]   // 공고문에 있지만 위 여섯 key 로 옮길 수 없는 계층·신분 이름(산업단지 근로자, 창업인, 장기종사자 등). 없으면 []
}
공고문이 신청자를 계층·신분(청년, 신혼부부, 한부모가족, 고령자 …)으로 나눠 기준을 따로 적었으면 그 계층마다 하나씩 적고, 그런 공고문에 "일반" 계층을 지어내지 마세요.
값을 여러 문장에서 계산해 만들었으면(예: 표의 다른 줄) 그 값은 null 로 두세요 — quote 한 곳에서 확인되는 값만 적습니다.
소득·자산 기준 문장이 공고문에 없다는 것만으로 "excluded" 라고 하지 마세요 — 보지 않는다고 **적혀 있을 때만** "excluded" 입니다."""


def _ns(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _nums(q: str) -> set[int]:
    return {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", q) if x.replace(",", "")}


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


# ── AI 가 필요한가 ─────────────────────────────────────────────────────────

def gaps(terms: Optional[dict], kind: str) -> list[str]:
    """규칙으로 못 읽은 칸 이름 (없으면 AI 를 부르지 않는다). 화면이 '공고문 확인'으로 보여 주는 칸과 같다."""
    T = terms or {}
    out = []
    if not T.get("groups"):
        out.append("계층")
    if kind == "공공임대":
        out += [k for k in ("regions", "account") if T.get(k) is None]
    if T.get("local_unread") and not T.get("local"):
        out.append("local")
    for g in T.get("groups") or []:
        if g.get("key") == "주거급여수급자" or g.get("exempt"):
            continue
        out += [f"{g['key']}.{f}" for f in ("homeless", "income_pct", "asset_manwon", "car_manwon") if g.get(f) is None]
    return out


# ── 검사기: AI 답 → 검사를 통과한 값만 ─────────────────────────────────────

def _money_in(v: int, q: str) -> bool:
    """만원 값 v 가 문장에 금액으로 적혀 있는가: '34,500만원' · '345,000,000원' · '345백만원' · '3억4,500만원'"""
    n, qs = _nums(q), _ns(q)
    if v in n and "만원" in qs or v * 10000 in n:
        return True
    if v % 100 == 0 and v // 100 in n and "백만원" in qs:
        return True
    if v >= 10000 and "억" in qs and v // 10000 in n and (v % 10000 == 0 or v % 10000 in n):
        return True
    return False


def _check_value(field: str, v, q: str, region: Optional[str], after: str = "") -> Optional[str]:
    """값이 근거 문장과 맞으면 None, 아니면 탈락 이유. after = 원문에서 그 문장 바로 뒤 글(빈칸 뺌)."""
    qs, n = _ns(q), _nums(q)
    excl = bool(re.search(_EXCL, qs))
    if field == "homeless":
        single = "단독세대주" in qs or "단독세대주" in after[:80]   # '무주택세대구성원(혼인 중이 아닌 경우로서 단독세대주로 입주하려는 사람은 무주택자)' — 문장 안이나 바로 뒤 괄호
        if v == "household":
            if single:
                return "문장에 단독세대주 예외가 붙어 있음(세대원 전원으로 단정 못 함)"
            return None if re.search(r"무주택세대구성원|무주택세대", qs) else "문장에 '무주택세대구성원'이 없음"
        if v == "household_or_single_self":
            return None if "무주택세대구성원" in qs and "단독세대주" in qs and "무주택자" in qs else "문장에 무주택세대구성원·단독세대주·무주택자가 함께 있지 않음"
        if v == "self":
            return None if re.search(r"무주택자|본인", qs) and re.search(r"무주택|주택소유", qs) and "무주택세대구성원" not in qs else "문장이 본인 무주택으로 보이지 않음"
        return "값 형식"
    if field == "income_pct":
        if v == "excluded":
            return None if excl and "소득" in qs else "문장에 소득을 보지 않는다는 말이 없음"
        if not isinstance(v, dict) or set(v) - {"1", "2", "3+"} or not isinstance(v.get("3+"), int):
            return "값 형식"
        vals = [v.get(k) for k in ("1", "2", "3+")]
        if any(x is not None and (not isinstance(x, int) or not 50 <= x <= 250) for x in vals):
            return "범위 밖(50~250%)"
        have = [x for x in vals if x is not None]
        if have != sorted(have, reverse=True):
            return "1인 ≥ 2인 ≥ 3인 이상 순서가 아님"
        if not re.search(r"소득", qs):
            return "문장에 '소득'이 없음"
        for x in have:
            if x not in n and not any((x - b) in n for b in n if 0 < x - b <= 50):
                return f"문장에 {x}%(또는 가산 전 값과 가산 폭)가 없음"
        return None
    if field in ("asset_manwon", "car_manwon"):
        word = "자산" if field == "asset_manwon" else "자동차"
        if v == "excluded":
            return None if excl and (word in qs or "자산" in qs) else f"문장에 {word}을 보지 않는다는 말이 없음"
        if not isinstance(v, int) or isinstance(v, bool):
            return "값 형식"
        if field == "car_manwon" and v == 0:
            return None if re.search(r"자동차", qs) and re.search(r"소유하고있지않|보유하지않|소유하지않", qs) else "문장에 자동차를 가지면 안 된다는 말이 없음"
        lo, hi = (5000, 60000) if field == "asset_manwon" else (500, 10000)
        if not lo <= v <= hi:
            return "범위 밖"
        if word not in qs:
            return f"문장에 '{word}'이 없음"
        return None if _money_in(v, q) else "문장에 그 금액이 없음"
    if field == "age":
        a, b = v
        if a is not None and (not isinstance(a, int) or not 15 <= a <= 80 or a not in n):
            return "나이(하한)가 문장에 없음"
        if b is not None and (not isinstance(b, int) or not 15 <= b <= 80 or b not in n):
            return "나이(상한)가 문장에 없음"
        return None if "세" in qs else "문장에 '세'가 없음"
    if field == "regions":
        if not isinstance(v, list) or any(x not in SIDOS for x in v):
            return "값 형식(시·도 약칭 아님)"
        if not v:
            return None if re.search(r"국내에?거주|거주(?:지역|여부)[^.]{0,20}(?:" + _EXCL + ")", qs) else "문장에 거주지역 제한이 없다는 말이 없음"
        home = SIDO_SHORT.get(region or "")
        for x in v:
            full = [k for k, s in SIDO_SHORT.items() if s == x]
            if any(_ns(k) in qs for k in full):
                continue
            if x == home and len(v) == 1 and re.search(r"주택건설지역\([가-힣]{1,8}(?:시|군)\)", qs):
                continue   # '주택건설지역(익산시)' — 시·군만 적힌 꼴은 공고의 시·도일 때만
            return f"문장에 {x}(정식 이름)가 없음"
        return None if "거주" in qs or "무주택" in qs else "문장이 거주 요건이 아님"
    if field == "account":
        if v == "none":
            return None if excl and re.search(r"저축|통장", qs) else "문장에 청약통장을 보지 않는다는 말이 없음"
        if not isinstance(v, dict) or not all(isinstance(v.get(k), int) and not isinstance(v.get(k), bool) for k in ("months", "count")) or not isinstance(v.get("rank2_any"), bool):
            return "값 형식"
        m, c = v["months"], v["count"]
        if not (1 <= m <= 36 and 1 <= c <= 36):
            return "범위 밖"
        if not re.search(r"저축|통장", qs):
            return "문장에 청약통장 말이 없음"
        if not ((m in n and re.search(r"개월|월이", qs)) or (m % 12 == 0 and m // 12 in n and "년" in qs)) or c not in n or "회" not in qs:
            return "문장에 가입 기간·납입 횟수가 없음"
        return None
    if field == "local":
        if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not v["name"]:
            return "값 형식"
        if _ns(v["name"]) not in qs or "거주" not in qs and "주민등록" not in qs:
            return "문장에 그 지역 이름·거주 요건이 없음"
        home = SIDO_SHORT.get(region or "")
        if v.get("sido") not in SIDOS or (home and v["sido"] != home):
            return "시·도가 공고의 시·도와 다름"
        if v.get("sigun") not in (None, v["name"]):
            return "시·군 이름이 다름"
        return None
    return "모르는 칸"


def to_terms(answer: dict, texts: list[str], region: Optional[str], kind: str = "") -> tuple[dict, list[str]]:
    """AI 답(JSON) → 검사를 통과한 값만 담은 terms 꼴(app.loose_read.fill_lh_terms 에 넘길 수 있다)과 탈락 기록."""
    flat = [_ns(t) for t in texts if t]
    dropped: list[str] = []

    def ok(name: str, field: str, v, q) -> bool:
        if v is None:
            return False
        short = 4 if v == "excluded" else 10   # 표 칸 '소득 배제' 같은 짧은 글은 '미적용' 값일 때만 받는다(화면은 완화 공고·공공임대일 때만 미적용을 믿는다)
        if not isinstance(q, str) or len(_ns(q)) < short or len(q) > 400:
            dropped.append(f"{name}: 근거 문장 없음·길이")
            return False
        at = next(((f, f.find(_ns(q))) for f in flat if _ns(q) in f), None)
        if at is None:
            dropped.append(f"{name}: 근거 문장이 원문에 없음")
            return False
        try:
            why = _check_value(field, v, q, region, at[0][at[1] + len(_ns(q)): at[1] + len(_ns(q)) + 120])
        except Exception as e:   # 답 형식이 어긋나면 그 값만 버린다
            why = f"검사 오류 {e.__class__.__name__}"
        if why:
            dropped.append(f"{name}: {why}")
            return False
        return True

    out: dict = {"groups": [], "quotes": {}}
    seen = set()
    for g in answer.get("groups") or []:
        if not isinstance(g, dict) or g.get("key") not in GROUP_KEYS or g["key"] in seen:
            continue
        seen.add(g["key"])
        key = g["key"]
        r = {"key": key, "name": key, "homeless": None, "income_pct": None, "asset_manwon": None, "car_manwon": None, "age_min": None, "age_max": None}
        q = {}
        if key == "주거급여수급자":   # 읽기 규칙(행복주택)도 이 계층은 소득·자산 칸을 비워 두고 무주택은 세대원 전원으로 둔다(수급자 자격으로 판단) — AI 값은 받지 않고 계층만, 행복주택일 때만
            if kind == "행복주택":
                r["homeless"] = "household"
                out["groups"].append(r)
                out["quotes"][key] = q
            continue
        if key == "일반" and re.search(r"청년|신혼부부|한부모|고령자|대학생", _ns(str(g.get("homeless_quote") or ""))):
            # 계층별로 나눈 공고문('무주택세대구성원(청년은 입주자 본인, 예비신혼부부는 …)')에서 '일반' 계층을 지어낸 답 (담양삼만 905, 11-11 정확도 시험) — 계층째 버린다
            dropped.append("계층 일반: 계층별로 나눈 공고문으로 보임('일반' 계층을 만들지 않음)")
            continue
        for f, qk in (("homeless", "homeless"), ("income_pct", "income"), ("asset_manwon", "asset"), ("car_manwon", "car")):
            if ok(f"{key}.{f}", f, g.get(f), g.get(qk + "_quote")):
                r[f], q[qk] = g[f], g[qk + "_quote"].strip()
        if (g.get("age_min") is not None or g.get("age_max") is not None) and ok(f"{key}.age", "age", (g.get("age_min"), g.get("age_max")), g.get("age_quote")):
            r["age_min"], r["age_max"] = g.get("age_min"), g.get("age_max")
        if any(r[f] is not None for f in ("homeless", "income_pct", "asset_manwon", "car_manwon")):
            out["groups"].append(r)
            out["quotes"][key] = q
    if ok("regions", "regions", answer.get("regions"), answer.get("regions_quote")):
        out["regions"] = sorted(answer["regions"])
        out["quotes"].setdefault("일반", {})["region"] = answer["regions_quote"].strip()
    if ok("account", "account", answer.get("account"), answer.get("account_quote")):
        a = answer["account"]
        out["account"] = a if a == "none" else {"months": a["months"], "count": a["count"], "rank2_any": a["rank2_any"]}
        out["quotes"].setdefault("일반", {})["account"] = answer["account_quote"].strip()
    # 공공임대는 거주 요건을 regions(신청 가능 시·도)로 본다 — '주택건설지역(제천시,충청북도)'를 '제천시 거주자만'으로 좁히지 않게 local 은 받지 않는다 (11-11 정확도 시험)
    if kind != "공공임대" and ok("local", "local", answer.get("local"), answer.get("local_quote")):
        L = answer["local"]
        out["local"] = {"name": L["name"], "sido": L["sido"], "sigun": L.get("sigun"), "quote": answer["local_quote"].strip()}
    og = [re.sub(r"\s+", " ", x).strip()[:20] for x in answer.get("other_groups") or [] if isinstance(x, str) and x.strip()]
    if og:
        out["unknown_groups"] = og[:6]
    if all(g["key"] == "주거급여수급자" for g in out["groups"]):   # 검사를 통과한 값이 하나도 없으면 계층을 만들지 않는다
        out["groups"], out["quotes"] = [], {k: v for k, v in out["quotes"].items() if k != "주거급여수급자"}
    return out, dropped


# ── 답 파일 ────────────────────────────────────────────────────────────────
# 2026-11-12 운영자 'AI 호출은 네가 직접 열어 보는 걸로. API 키는 청약봇만': 수집은 Claude API 를 부르지 않는다(이 모듈에 네트워크 코드가 없다).
# 공고문은 세션(운영자와 일하는 Claude·아침 자동 고치기)이 직접 읽고, 위 SYSTEM 형식의 답을 tools/ai_answer.py 로 답 파일에 써 둔다.
# 수집은 그 답을 검사기에 통과시켜 쓴다 — 누가 읽었든 검사(근거 문장이 원문에 그대로·값이 문장 안·범위)는 같다.

def _now() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def save_answer(kind: str, nid: str, answer: dict, text: str, reader: str = "claude-session", cache_dir: Optional[Path] = None) -> Path:
    """세션이 읽은 답을 답 파일로 쓴다. kind: 'lh'(LH 임대, 글 지문과 묶임) · 'sh'(SH 임대, nid = 글번호, 글 지문과 묶임) · 'sale'(분양)."""
    d = cache_dir or {"lh": DIR, "sh": SH_DIR}.get(kind, SALE_DIR)
    d.mkdir(parents=True, exist_ok=True)
    rec = {"id": nid, "prompt_v": {"lh": PROMPT_V, "sh": SH_PROMPT_V}.get(kind, SALE_PROMPT_V), "model": reader, "at": _now(), "answer": answer}
    if kind in ("lh", "sh"):
        rec["sha"] = sha(text)
    f = d / f"{nid}.json"
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return f


class Budget:
    """(예전: 한 번 수집에서 새로 부를 수 있는 횟수) 수집이 AI 를 부르지 않게 된 뒤로는 쓰이지 않는다 — 부르는 쪽 모양만 남김"""
    def __init__(self, n: int = 0):
        self.left = n


def fill(nid: str, terms: Optional[dict], texts: dict, kind: str, name: str, region: Optional[str], budget: Optional[Budget] = None,
         cache_dir: Optional[Path] = None) -> tuple[Optional[dict], list[str]]:
    """규칙으로 못 읽은 칸을 AI 가 읽은 값(검사 통과한 것만)으로 채운 terms 와 기록 줄. 채운 것이 없으면 terms 를 그대로 돌려준다(같은 객체).
    texts: 읽기 도구 → 공고문 글 (답 파일은 첫 번째 글의 지문과 묶이고, 근거 문장은 어느 도구 글에든 있으면 된다)."""
    log: list[str] = []
    need = gaps(terms, kind)
    tx = [t for t in texts.values() if t and len(t) >= 500]
    if not need or not tx:
        return terms, log
    d = cache_dir or DIR
    f = d / f"{nid}.json"
    saved = None
    try:
        saved = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    key = sha(tx[0])
    if not (saved and saved.get("sha") == key and saved.get("prompt_v") == PROMPT_V and isinstance(saved.get("answer"), dict)):
        # 수집은 AI 를 부르지 않는다(2026-11-12 운영자: API 키는 청약봇 전용). 세션이 공고문을 직접 읽어 답 파일을 써 두면(tools/ai_answer.py) 다음 수집부터 쓴다
        return terms, [f"[공고문·AI 읽기] {nid} 못 읽은 칸 {len(need)}개({', '.join(need)}) — 답 파일 없음. 세션이 공고문을 읽고 `python -m tools.ai_answer lh {nid} <답.json>` 으로 써 둘 것"]
    ai_terms, dropped = to_terms(saved["answer"], tx, region, kind)
    if "계층" not in need:
        # 규칙이 계층을 읽은 공고: AI 값은 화면이 '공고문 확인'으로 보이는 칸(need)에만 쓴다. 규칙이 일부러 비워 두는 칸(나이 등)은 채우지 않는다
        # (2026-11-11 남원노암 2015122300021022 첫 실제 호출에서 못 읽은 칸이 아닌 '일반.age_min' 하나만 채워 'AI 가 읽은 공고'가 됨)
        for g in ai_terms.get("groups") or []:
            for f in list(g):
                if f not in ("key", "name") and f"{g['key']}.{f}" not in need:
                    g[f] = None
        for k in [k for k in ai_terms if k not in ("groups", "quotes") and k not in need]:
            ai_terms.pop(k)
    for x in dropped:
        log.append(f"[공고문·AI 읽기·탈락] {nid} {x}")
    import copy
    from app.loose_read import fill_lh_terms
    out = copy.deepcopy(terms) if terms else {"relaxed": False, "homeless_relaxed": False, "homeless_max1": False, "income_basis": None, "groups": [], "quotes": {}, "income_table_100": None}
    no_groups = not out.get("groups")
    filled = fill_lh_terms(out, ai_terms)
    if filled and no_groups and ai_terms.get("unknown_groups") and not out.get("unknown_groups"):
        out["unknown_groups"] = ai_terms["unknown_groups"]   # AI 가 계층을 통째로 읽은 공고: 여섯 계층으로 못 옮긴 계층 이름 → 화면 '일부 계층 판정 못 함'
    if not filled:
        log.append(f"[공고문·AI 읽기] {nid} 못 읽은 칸 {len(need)}개 — AI 도 검사를 통과한 값을 주지 못함 (화면 '공고문 확인' 그대로)")
        return terms, log
    out["ai"] = {"fields": filled, "model": saved.get("model"), "at": saved.get("at")}
    log.append(f"[공고문·AI 읽기] {nid} AI 가 읽어 채운 칸: {', '.join(filled)} — 화면은 '확인 필요'까지만. 원문과 맞춰 보고 읽기 규칙·정답 데이터에 넣을 것")
    return out, log


# ── 분양 공고문 (기능 ai_read_sale, 2026-11-11 운영자 'AI 읽기를 분양에도') ───────────────────────────
# 분양은 AI 값을 **판정에 쓰지 않는다**. 규칙이 못 읽어 화면이 '확인 필요'로 보이는 두 항목(거주 지역 요건·실거주 의무)에
# 'AI가 공고문에서 읽은 내용(참고)'과 근거 문장을 붙여 줄 뿐이다 — 판정 결과('확인 필요')는 그대로다.
SALE_DIR = ROOT / "evidence" / "notices" / "ai"
SALE_PROMPT_V = 2
SALE_KEYS = ("residence", "residence_duty")

SYSTEM_SALE = """당신은 아파트 분양 입주자 모집공고문에서 두 가지 조건을 뽑아내는 도구입니다.
공고문에 **글자로 적혀 있는 것만** 뽑습니다. 추측하지 않습니다. 확실하지 않거나 공고문에 없으면 null 입니다.
값마다 근거 문장(quote)을 붙입니다. quote 는 공고문에서 **한 글자도 바꾸지 말고 그대로 복사한 이어진 글**(15~250자)이어야 하고, 그 값의 숫자·지역 이름이 quote 안에 들어 있어야 합니다.
여러 곳의 글을 이어 붙이거나 요약하면 안 됩니다. 답은 JSON 하나만 출력합니다(설명·코드블록 표시 없이).

출력 형식:
{
 "residence": {                       // 일반공급 1순위의 거주 지역 요건(해당지역·기타지역). 모르면 residence 전체를 null
   "area": "경기도 의정부시" | null,   // 해당지역(우선공급 지역) 이름 — 공고문에 적힌 그대로. 시·도 전체면 "제주특별자치도"처럼.
                                      // 우선하는 지역 없이 여러 시·도 거주자를 똑같이 받으면(예: '부산광역시 및 울산광역시, 경상남도에 거주하는 …') area 는 null, 그 시·도는 모두 others 에
   "months": 0,                       // 해당지역으로 인정받는 계속 거주 기간(개월). '1년 이상' = 12. 기간 요건이 없으면 0
   "since": "2025-11-05" | null,      // '○○○○.○○.○○. 이전부터 계속 거주' 날짜가 적혀 있으면
   "others": ["서울", "인천", "경기"]   // 기타지역 시·도 약칭(서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주). 전국이면 ["전국"].
                                      // 해당지역 거주자만 신청할 수 있으면(기타지역이 없음, 예: '서울특별시에 거주하는 …을 대상으로') []
 },
 "residence_quote": "...",            // 해당지역·기타지역이 함께 적힌 한 곳(요약 표의 줄 등)
 "residence_duty_years": 3 | 0 | null,   // 당첨자의 실거주(거주) 의무 기간(년). 공고문에 거주의무가 '없음'·'해당 없음'·'미적용'이라고 적혀 있으면 0. 말이 없으면 null
 "residence_duty_quote": "..."
}"""


def _area_ok(area: str, qs: str) -> bool:
    parts = [p for p in re.split(r"\s+", area.strip()) if p]
    return bool(parts) and all(_ns(p) in qs for p in parts) and bool(re.search(r"(시|군|구|도)$", parts[-1]))


def sale_hints(answer: dict, texts: list[str]) -> tuple[dict, list[str]]:
    """AI 답 → 검사를 통과한 항목만 {'residence': {'text','quote'}, 'residence_duty': {'text','quote','years'}} 와 탈락 기록."""
    flat = [_ns(t) for t in texts if t]
    out, dropped = {}, []

    def quote_ok(name: str, q) -> Optional[str]:
        if not isinstance(q, str) or len(_ns(q)) < 10 or len(q) > 500:
            dropped.append(f"{name}: 근거 문장 없음·길이")
            return None
        if not any(_ns(q) in f for f in flat):
            dropped.append(f"{name}: 근거 문장이 원문에 없음")
            return None
        return _ns(q)

    R = answer.get("residence")
    if isinstance(R, dict):
        qs = quote_ok("residence", answer.get("residence_quote"))
        if qs:
            n = _nums(answer["residence_quote"])
            area, months, since, others = R.get("area"), R.get("months"), R.get("since"), R.get("others")
            if area is None and isinstance(others, list) and len(others) == 1 and others[0] in SIDOS:
                # '충청북도에 거주하는 …을 대상으로' 를 area 없음·others [충북] 으로 답한 꼴(2026910243) — 한 시·도 거주자만 받는 것이므로 해당지역 하나·기타지역 없음과 같다
                full = next((k for k, v in SIDO_SHORT.items() if v == others[0] and _ns(k) in qs), None)
                if full:
                    area, others = full, []
            why = None
            if area is None and not (isinstance(others, list) and others):
                why = "해당지역도 기타지역도 없음"
            elif area is not None and (not isinstance(area, str) or not _area_ok(area, qs)):
                why = "해당지역 이름이 문장에 없음"
            elif area and isinstance(others, list) and others and re.search(re.escape(_ns(area)) + r"(?:및|,|·|와|과|또는)[^.]{0,40}에거주하는", qs):
                # '부산광역시 및 울산광역시, 경상남도에 거주하는 …' — 여러 시·도를 똑같이 받는 문장을 해당지역(부산)+기타지역으로 나눈 답 (2026910234, 11-11 정확도 시험)
                why = "여러 지역을 똑같이 받는 문장으로 보임(해당지역 우선이 아님)"
            elif "거주" not in qs:
                why = "문장에 '거주'가 없음"
            elif not isinstance(months, int) or isinstance(months, bool) or not 0 <= months <= 60:
                why = "거주기간 형식·범위"
            elif months and not ((months in n and "개월" in qs) or (months % 12 == 0 and months // 12 in n and "년" in qs)):
                why = "문장에 그 거주기간이 없음"
            elif not months and re.search(r"\d(?:년|개월)이상", qs):
                why = "문장에 거주기간이 있는데 0 으로 답함"
            elif not isinstance(others, list) or any(x not in SIDOS and x != "전국" for x in others):
                why = "기타지역 형식"
            elif not others and not re.search(r"에거주하는|거주자(?:만|에한)", qs):
                why = "기타지역이 없다고 볼 문장이 아님('…에 거주하는 …을 대상으로' 꼴만 받음)"
            else:
                for x in others:
                    names = ["전국"] if x == "전국" else [k for k, v in SIDO_SHORT.items() if v == x] + [x] + (["수도권"] if x in ("서울", "인천", "경기") else [])
                    if not any(_ns(k) in qs for k in names):
                        why = f"문장에 기타지역 {x} 가 없음"
                        break
            if not why and since is not None:
                m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(since))
                if not m or not all(int(x) in n for x in m.groups()):
                    why = "문장에 그 날짜가 없음"
            if why:
                dropped.append(f"residence: {why}")
            else:
                per = "" if not months else (f" · {months // 12}년" if months % 12 == 0 else f" · {months}개월") + " 이상 계속 거주" + (f"({since} 이전부터)" if since else "")
                txt = (f"{'·'.join(others)} 거주자(우선하는 지역 없음)" if area is None else
                       f"{area} 거주자만 신청{per}" if not others else f"해당지역 {area} 거주자{per} · 기타지역 {'·'.join(others)}")
                out["residence"] = {"text": txt, "quote": answer["residence_quote"].strip(),
                                    "value": {"area": area, "months": months, "since": since, "others": sorted(others)}}
    y = answer.get("residence_duty_years")
    if y is not None:
        qs = quote_ok("residence_duty", answer.get("residence_duty_quote"))
        if qs:
            n = _nums(answer["residence_duty_quote"])
            if not isinstance(y, int) or isinstance(y, bool) or not 0 <= y <= 10:
                dropped.append("residence_duty: 형식·범위")
            elif not re.search(r"거주의무|실거주", qs):
                dropped.append("residence_duty: 문장에 '거주의무'가 없음")
            elif y and not (y in n and "년" in qs):
                dropped.append("residence_duty: 문장에 그 기간이 없음")
            elif not y and not re.search(r"(?:거주의무|실거주의무)(?:기간)?[^.가-힣]{0,3}(?:은|는|이|가)?[^.가-힣]{0,3}(?:없음|없습|해당없|해당사항없|미적용|적용되지않|적용받지않)", qs):
                dropped.append("residence_duty: 문장에 거주의무가 없다는 말이 없음(바로 붙어 있어야 함 — 표 머리와 값이 떨어진 글은 받지 않음)")
            else:
                out["residence_duty"] = {"text": f"거주의무 {y}년" if y else "거주의무 없음", "quote": answer["residence_duty_quote"].strip(), "years": y}
    return out, dropped


SALE_HEAD, SALE_WIN, SALE_MAX = 12_000, 700, 45_000


def sale_excerpt(text: str) -> str:
    """분양 공고문은 길다(15만 자 ≈ 입력 15만 토큰, 1건 추정 $0.30 — 2026-11-11 첫 실제 호출). 두 항목에 필요한 곳만 보낸다:
    앞부분(요약 표가 있는 1~2쪽) + '해당지역·기타지역·거주의무·…에 거주하는' 둘레. 조각은 원문 그대로이고 사이를 '…'로 나눈다(근거 문장은 한 조각 안에서만 나온다)."""
    if len(text) <= SALE_MAX:
        return text
    spans = [(0, SALE_HEAD)]
    for m in re.finditer(r"해당\s?지역|기타\s?지역|거주\s?의무|실거주|에\s?거주하는|계속\s?거주", text):
        a, b = max(0, m.start() - SALE_WIN), min(len(text), m.end() + SALE_WIN)
        if a <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], b))
        else:
            spans.append((a, b))
    out, n = [], 0
    for a, b in spans:
        if n + (b - a) > SALE_MAX:
            break
        out.append(text[a:b])
        n += b - a
    return "\n…\n".join(out)


def sale_gaps(found: dict) -> list[str]:
    """규칙이 못 읽어 화면이 '확인 필요'로 보이는 항목. 실거주 의무는 '공고문에 말이 없음'(duty_silent)으로 읽은 공고는 뺀다."""
    out = []
    if not found.get("residence"):
        out.append("residence")
    if found.get("residence_duty") is None and not found.get("duty_silent"):
        out.append("residence_duty")
    return out


def sale_fill(nid: str, found: dict, text: str, name: str, budget: Optional[Budget] = None,
              cache_dir: Optional[Path] = None, need: Optional[list] = None) -> tuple[dict, list[str]]:
    """→ (못 읽은 항목의 AI 참고 내용 {항목: {'text','quote'}}, 기록 줄). 답 파일(세션이 읽어 써 둔 것)이 있을 때만."""
    log: list[str] = []
    need = sale_gaps(found) if need is None else need
    if not need or not text or len(text) < 500:
        return {}, log
    d = cache_dir or SALE_DIR
    f = d / f"{nid}.json"
    saved = None
    try:
        saved = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    if not (saved and saved.get("prompt_v") == SALE_PROMPT_V and isinstance(saved.get("answer"), dict)):
        return {}, [f"[공고문·AI 읽기] {name} ({nid}): 못 읽은 항목 {', '.join(need)} — 답 파일 없음. 세션이 공고문을 읽고 `python -m tools.ai_answer sale {nid} <답.json>` 으로 써 둘 것"]
    hints, dropped = sale_hints(saved["answer"], [text])
    for x in dropped:
        log.append(f"[공고문·AI 읽기·탈락] {name} ({nid}): {x}")
    hints = {k: {"text": v["text"], "quote": v["quote"]} for k, v in hints.items() if k in need}
    if hints:
        log.append(f"[공고문·AI 읽기] {name} ({nid}): AI 가 읽은 참고 내용 " + " / ".join(f"{k}: {v['text']}" for k, v in hints.items()) + " — 판정에는 쓰지 않음. 원문과 맞춰 보고 읽기 규칙·정답 데이터에 넣을 것")
    else:
        log.append(f"[공고문·AI 읽기] {name} ({nid}): 못 읽은 항목 {', '.join(need)} — AI 도 검사를 통과한 값을 주지 못함")
    return hints, log


# ── SH 임대 공고문 (기능 ai_read_sh, 2026-11-12 운영자 'SH 도 공고문 실패하면 네가 AI 로 읽어. API 키는 쓰지 말고') ───────────────
# SH 는 공고 종류마다 읽기 규칙·자격 꼴이 달라(app/sh_terms.py: 출생일 하한·검증 면제·출산가구 표 …) AI 값으로 **판정하지 않는다**.
# 규칙이 자격을 못 읽은 공고(판정하는 여섯 종류인데 terms 없음·기준 칸이 빔)에 '세션이 공고문에서 읽은 자격 기준(참고)'과 근거 문장을 붙여 줄 뿐이다.
# 수집은 Claude API 를 부르지 않는다 — 세션이 원문(evidence/sh/<글번호>.txt)을 직접 읽어 `python -m tools.ai_answer sh <글번호> <답.json>` 으로 써 둔 답 파일만 쓴다.
SH_DIR = ROOT / "evidence" / "sh" / "ai"
SH_PROMPT_V = 1
SH_KINDS = ("신혼·신생아 매입임대", "청년 매입임대", "장기전세", "사회주택", "행복주택", "청년안심주택")   # app/sh_terms.parse_sh_terms 가 읽는 종류

SYSTEM_SH = """당신은 서울주택도시개발공사(SH) 임대주택 입주자 모집공고문에서 신청 자격 기준을 뽑아내는 도구입니다.
공고문에 **글자로 적혀 있는 것만** 뽑습니다. 추측하지 않습니다. 확실하지 않거나 공고문에 없으면 null 입니다.
값마다 근거 문장(quote)을 붙입니다. quote 는 공고문에서 **한 글자도 바꾸지 말고 그대로 복사한 이어진 글**(15~200자)이어야 하고, 그 값의 숫자·낱말이 quote 안에 들어 있어야 합니다.
여러 곳의 글을 이어 붙이거나 요약하면 안 됩니다. 답은 JSON 하나만 출력합니다.

출력 형식:
{
 "groups": [   // 공고문이 자격을 나눈 계층·유형. name 은 공고문에 적힌 이름 그대로(예: "청년", "신혼부부", "일반공급"). 구분이 없으면 공고문의 공급 대상 이름 하나
  {"name": "청년",
   "homeless": "household" | "self" | "household_or_single_self" | null, "homeless_quote": "...",
   "income_pct": {"1": 120, "2": 110, "3+": 100} | "excluded" | null, "income_quote": "...",   // 가구원 수별 소득 상한 퍼센트(가산이 적혀 있으면 더한 값)
   "asset_manwon": 34500 | "excluded" | null, "asset_quote": "...",                            // 총자산 한도(만원)
   "car_manwon": 4542 | 0 | "excluded" | null, "car_quote": "...",                             // 자동차가액 한도(만원). 0 = 자동차를 가지면 안 됨
   "age_min": 19 | null, "age_max": 39 | null, "age_quote": "..."}
 ]
}
값을 여러 문장에서 계산해 만들었으면 그 값은 null 로 두세요 — quote 한 곳에서 확인되는 값만 적습니다.
소득·자산 기준 문장이 없다는 것만으로 "excluded" 라고 하지 마세요 — 보지 않는다고 **적혀 있을 때만** "excluded" 입니다."""

_SH_HOME = {"household": "세대원 전원 무주택(무주택세대구성원)", "self": "본인만 무주택(무주택자)", "household_or_single_self": "세대원 전원 무주택 — 혼인 중이 아닌 단독세대주는 본인만"}


def _sh_text(field: str, v) -> str:
    if field == "homeless":
        return _SH_HOME[v]
    if v == "excluded":
        return "이번 모집은 보지 않음"
    if field == "income_pct":
        have = [v[k] for k in ("1", "2", "3+") if v.get(k) is not None]
        if len(set(have)) == 1:   # 가구원 수와 상관없이 한 비율
            return f"{have[0]}% 이하"
        return " · ".join(f"{'3인 이상' if k == '3+' else k + '인'} {v[k]}% 이하" for k in ("1", "2", "3+") if v.get(k) is not None)
    if field == "car_manwon" and v == 0:
        return "자동차를 가지면 안 됨"
    if field == "age":
        a, b = v
        return "만 " + (f"{a}세 이상" if a is not None else "") + (" " if a is not None and b is not None else "") + (f"{b}세 이하" if b is not None else "")
    return f"{v:,}만원 이하"


def sh_gaps(terms: Optional[dict], kind: str) -> list[str]:
    """규칙이 못 읽은 것 이름. 판정하는 여섯 종류만 본다(그 밖의 SH 공고는 처음부터 '판정 미지원')."""
    if kind not in SH_KINDS:
        return []
    T = terms or {}
    if not T.get("groups"):
        return ["자격"]
    return [f"{g['key']}.{f}" for g in T["groups"] if not g.get("exempt") for f in ("homeless", "income_pct", "asset_manwon", "car_manwon") if g.get(f) is None]


def sh_hints(answer: dict, texts: list[str]) -> tuple[dict, list[str]]:
    """세션 답 → 검사를 통과한 값만 {'groups': [{'name', 'items': [{'k','label','text','quote'}]}]} 와 탈락 기록. 검사는 LH 와 같은 _check_value."""
    flat = [_ns(t) for t in texts if t]
    dropped: list[str] = []
    groups = []
    seen = set()
    for g in answer.get("groups") or []:
        name = re.sub(r"\s+", " ", str(g.get("name") or "")).strip() if isinstance(g, dict) else ""
        if not name or len(name) > 30 or name in seen:
            continue
        if not any(_ns(name) in f for f in flat):
            dropped.append(f"계층 {name}: 이름이 원문에 없음")
            continue
        seen.add(name)
        items = []
        for field, qk, label in (("homeless", "homeless", "무주택"), ("age", "age", "나이"), ("income_pct", "income", "소득"), ("asset_manwon", "asset", "총자산"), ("car_manwon", "car", "자동차")):
            v = (g.get("age_min"), g.get("age_max")) if field == "age" else g.get(field)
            q = g.get(qk + "_quote")
            if v is None or v == (None, None):
                continue
            nm = f"{name}.{field}"
            short = 4 if v == "excluded" else 10
            if not isinstance(q, str) or len(_ns(q)) < short or len(q) > 400:
                dropped.append(f"{nm}: 근거 문장 없음·길이")
                continue
            at = next(((f, f.find(_ns(q))) for f in flat if _ns(q) in f), None)
            if at is None:
                dropped.append(f"{nm}: 근거 문장이 원문에 없음")
                continue
            try:
                why = _check_value(field, v, q, None, at[0][at[1] + len(_ns(q)): at[1] + len(_ns(q)) + 120])
            except Exception as e:
                why = f"검사 오류 {e.__class__.__name__}"
            if why:
                dropped.append(f"{nm}: {why}")
                continue
            items.append({"k": field, "label": label, "text": _sh_text(field, v), "quote": q.strip()})
        if items:
            groups.append({"name": name, "items": items})
    return ({"groups": groups} if groups else {}), dropped


def sh_fill(seq: str, terms: Optional[dict], kind: str, text: Optional[str], name: str = "", cache_dir: Optional[Path] = None) -> tuple[Optional[dict], list[str]]:
    """→ (참고 내용 {'groups', 'need', 'model', 'at'} 또는 None, 기록 줄). 답 파일(세션이 읽어 써 둔 것, 글 지문과 묶임)이 있을 때만."""
    need = sh_gaps(terms, kind)
    if not need or not text or len(text) < 500:
        return None, []
    nid = "SH-" + seq
    saved = None
    try:
        saved = json.loads(((cache_dir or SH_DIR) / f"{seq}.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    if not (saved and saved.get("sha") == sha(text) and saved.get("prompt_v") == SH_PROMPT_V and isinstance(saved.get("answer"), dict)):
        return None, [f"[공고문·AI 읽기] {nid} {name[:30]} 못 읽은 것 {', '.join(need)} — 답 파일 없음. 세션이 공고문(evidence/sh/{seq}.txt)을 읽고 `python -m tools.ai_answer sh {seq} <답.json>` 으로 써 둘 것"]
    hints, dropped = sh_hints(saved["answer"], [text])
    log = [f"[공고문·AI 읽기·탈락] {nid} {x}" for x in dropped]
    if not hints:
        return None, log + [f"[공고문·AI 읽기] {nid} 못 읽은 것 {', '.join(need)} — 답 파일의 값이 검사를 통과하지 못함 (화면 그대로)"]
    hints.update(need=need, model=saved.get("model"), at=saved.get("at"))
    log.append(f"[공고문·AI 읽기] {nid} 세션이 읽은 참고 내용 계층 {len(hints['groups'])}개·값 {sum(len(g['items']) for g in hints['groups'])}개 — 판정에는 쓰지 않음. 원문과 맞춰 보고 읽기 규칙·정답 데이터에 넣을 것")
    return hints, log
