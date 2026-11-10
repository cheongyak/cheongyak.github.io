"""규칙이 못 읽은 LH 임대 공고문을 AI(Claude)가 대신 읽는다 (기능 ai_read, 2026-11-11 운영자 '처음 보는 형태도 잘 읽게 — 방법 1 실패하면 방법 2').

순서: ① 읽기 규칙(엄격) → ② 띄어쓰기를 무시한 읽기(기능 loose_read) → ③ 그래도 비어 있는 칸이 있으면 여기.
AI 가 준 값은 그대로 믿지 않는다. 값마다 **근거 문장**을 함께 받게 하고, 아래 검사를 통과한 값만 **비어 있던 칸**에 채운다:
  - 근거 문장이 공고문 원문에 글자 그대로 있어야 한다(빈칸만 무시)
  - 값의 숫자·낱말이 그 근거 문장 안에 있어야 한다 (총자산 34,500만원 → 문장에 '34,500' 또는 '345,000,000' 등)
  - 값이 범위 안이어야 한다 (소득 50~250%, 총자산 5천만~6억, 자동차 0~1억 …)
규칙이 읽은 값은 바꾸지 않는다. 채운 칸은 terms['ai'] 에 남고, 화면은 그 공고를 '확인 필요'까지만 보여 준다('신청 가능해 보여요'로 단정하지 않음).
아침 자동 고치기가 원문과 맞춰 본 뒤 읽기 규칙·정답 데이터를 더하면 그때부터 규칙이 읽은 값으로 바뀐다.

인증키는 GitHub Secrets ANTHROPIC_API_KEY (환경변수)에서만 읽는다. 없으면 건너뛴다. 기록·출력에 키를 쓰지 않는다.
같은 공고문(글 지문이 같음)은 한 번만 부른다 — 답은 evidence/lh/ai/<공고ID>.json 에 둔다. 한 달 추정 사용액이 한도를 넘으면 부르지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from app.lh_terms import GROUP_KEYS, SIDO_SHORT

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "evidence" / "lh" / "ai"
SPEND = DIR / "_spend.json"
MODEL = "claude-sonnet-5-5"        # 청약봇 자유 답변과 같은 모델 (chat/worker/src/llm.js FREE_MODEL)
PRICE = (2.0, 10.0)                 # 100만 토큰당 달러 [입력, 출력] — chat/worker/src/llm.js PRICE 와 같은 추정 단가
PROMPT_V = 2                        # 지시문을 바꾸면 올린다 (올리면 저장해 둔 답을 다시 받는다)
MONTH_USD = 5.0                     # 한 달 추정 사용액 한도 (docs/config.json ai_read.month_usd 로 바꿀 수 있다)
MAX_PER_RUN = 6                     # 한 번 수집에서 새로 부르는 공고 수
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


# ── Claude 호출 ────────────────────────────────────────────────────────────

def _post(api_key: str, body: dict) -> dict:
    import httpx
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=httpx.Timeout(180, connect=15), json=body,
                   headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"})
    if r.status_code != 200:
        try:
            e = r.json().get("error") or {}
            why = f"{e.get('type', '')}: {e.get('message', '')}"[:160]
        except Exception:
            why = ""
        raise RuntimeError(f"claude {r.status_code} {why}".strip())
    return r.json()


def ask(text: str, kind: str, name: str, api_key: str, post: Optional[Callable] = None) -> tuple[dict, dict]:
    """→ (AI 답 JSON, usage). 실패하면 예외."""
    user = f"공고 유형: {kind}\n공고 이름: {name}\n\n아래는 공고문 글입니다(PDF 에서 뽑아 줄·칸 순서가 흐트러진 곳이 있을 수 있습니다).\n\n<공고문>\n{text[:MAX_CHARS]}\n</공고문>"
    body = {"model": MODEL, "max_tokens": 8000, "output_config": {"effort": "medium"},
            "system": [{"type": "text", "text": SYSTEM}], "messages": [{"role": "user", "content": user}]}
    j = (post or _post)(api_key, body)
    out = "".join(c.get("text", "") for c in j.get("content") or [] if c.get("type") == "text")
    a, b = out.find("{"), out.rfind("}")
    if a < 0 or b <= a:
        raise RuntimeError("답에 JSON 이 없음")
    return json.loads(out[a:b + 1]), (j.get("usage") or {})


def usd_of(usage: dict) -> float:
    return ((usage.get("input_tokens") or 0) * PRICE[0] + (usage.get("output_tokens") or 0) * PRICE[1]) / 1e6


def _month() -> str:
    return datetime.now(KST).strftime("%Y-%m")


def month_spent() -> float:
    try:
        return float(json.loads(SPEND.read_text(encoding="utf-8")).get(_month(), 0))
    except Exception:
        return 0.0


def _add_spent(usd: float) -> None:
    try:
        d = json.loads(SPEND.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d[_month()] = round(float(d.get(_month(), 0)) + usd, 4)
    DIR.mkdir(parents=True, exist_ok=True)
    SPEND.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def month_cap() -> float:
    try:
        return float((json.loads((ROOT / "docs" / "config.json").read_text(encoding="utf-8")).get("ai_read") or {}).get("month_usd", MONTH_USD))
    except Exception:
        return MONTH_USD


class Budget:
    """한 번 수집에서 새로 부를 수 있는 횟수"""
    def __init__(self, n: int = MAX_PER_RUN):
        self.left = n


def fill(nid: str, terms: Optional[dict], texts: dict, kind: str, name: str, region: Optional[str], budget: Budget,
         post: Optional[Callable] = None, api_key: Optional[str] = None, cache_dir: Optional[Path] = None) -> tuple[Optional[dict], list[str]]:
    """규칙으로 못 읽은 칸을 AI 가 읽은 값(검사 통과한 것만)으로 채운 terms 와 기록 줄. 채운 것이 없으면 terms 를 그대로 돌려준다(같은 객체).
    texts: 읽기 도구 → 공고문 글 (첫 번째 글을 AI 에 보내고, 근거 문장은 어느 도구 글에든 있으면 된다)."""
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
        api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return terms, [f"[공고문·AI 읽기] {nid} 못 읽은 칸 {len(need)}개 — ANTHROPIC_API_KEY 없음, 건너뜀"]
        if budget.left <= 0:
            return terms, [f"[공고문·AI 읽기] {nid} 이번 실행 호출 수 한도 — 다음 수집에서 읽음"]
        if month_spent() >= month_cap():
            return terms, [f"[공고문·AI 읽기] {nid} 이번 달 추정 사용액 ${month_spent():.2f} 가 한도 ${month_cap():.0f} 를 넘어 부르지 않음"]
        budget.left -= 1
        try:
            answer, usage = ask(tx[0], kind, name, api_key, post)
        except Exception as e:
            return terms, [f"[공고문·AI 읽기] {nid} 호출 실패: {str(e)[:160].replace(api_key, '***')}"]
        usd = usd_of(usage)
        if cache_dir is None:
            _add_spent(usd)
        saved = {"id": nid, "sha": key, "prompt_v": PROMPT_V, "model": MODEL, "at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                 "usage": {k: usage.get(k) for k in ("input_tokens", "output_tokens")}, "usd": round(usd, 4), "answer": answer}
        d.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(saved, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        log.append(f"[공고문·AI 읽기] {nid} AI 호출 (입력 {usage.get('input_tokens')}·출력 {usage.get('output_tokens')} 토큰, 추정 ${usd:.3f} · 이번 달 ${month_spent():.2f}/{month_cap():.0f})")
    ai_terms, dropped = to_terms(saved["answer"], tx, region, kind)
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
