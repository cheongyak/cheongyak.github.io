"""느슨한 읽기로 빈칸 채우기 (기능 loose_read, 2026-11-11). 규칙은 app/loose_re.py 머리말.

엄격하게 읽은 결과에서 **못 읽은 칸(None·없음)만** 느슨하게 읽은 값으로 채운다. 읽은 값은 바꾸지 않는다.
채운 칸은 결과의 `loose` 목록에 이름을 남긴다 — 수집이 `[공고문·느슨 읽기]` 줄로 기록하고, 아침 자동 고치기가 원문과 맞춰 본 뒤 정답 데이터에 넣는다.
"""
from __future__ import annotations

from typing import Optional

from app import lh_terms as _lh
from app.loose_re import loose

# 계층 칸 가운데 채우는 것 (문장이 '있다/없다'로 정해지는 참·거짓 값과 '모르는 계층' 목록은 채우지 않는다 — 판정을 넓히는 쪽이라 엄격하게 읽은 것만 쓴다)
_LH_TOP_SKIP = {"relaxed", "homeless_relaxed", "homeless_max1", "prewed_ok", "unknown_groups", "groups", "quotes", "income_basis", "local_unread", "loose"}


def fill_lh_terms(strict: dict, lo: dict) -> list[str]:
    """strict 를 그 자리에서 채우고, 채운 칸 이름 목록을 돌려준다."""
    filled: list[str] = []
    sq, lq = strict.setdefault("quotes", {}), lo.get("quotes") or {}
    if not strict.get("groups") and lo.get("groups"):
        strict["groups"] = lo["groups"]
        for g in lo["groups"]:
            sq[g["key"]] = lq.get(g["key"], {})
            filled.append(f"계층 {g['key']}")
    else:
        lg = {g["key"]: g for g in lo.get("groups") or []}
        for g in strict.get("groups") or []:
            o = lg.get(g["key"])
            if not o:
                continue
            for f, v in o.items():
                if f in ("key", "name") or v is None or g.get(f) is not None:
                    continue
                g[f] = v
                filled.append(f"{g['key']}.{f}")
                qk = {"income_pct": "income", "asset_manwon": "asset", "car_manwon": "car", "homeless": "homeless", "dual_add": "dual"}.get(f)
                if qk and (lq.get(g["key"]) or {}).get(qk):
                    sq.setdefault(g["key"], {})[qk] = lq[g["key"]][qk]
    for k, v in lo.items():
        if k in _LH_TOP_SKIP or v is None or strict.get(k) is not None:
            continue
        strict[k] = v
        filled.append(k)
    if "local" in filled and strict.get("local"):
        strict.pop("local_unread", None)
    return filled


def parse_lh_terms(text: str, kind: str, name: str = "", region: Optional[str] = None, mod=None) -> dict:
    """app.lh_terms.parse_lh_terms 와 같은 결과 + 못 읽은 칸은 느슨하게 읽어 채움(`loose` 목록). mod 는 시험·평가용(옛 규칙 모듈)."""
    mod = mod or _lh
    strict = mod.parse_lh_terms(text, kind, name, region)
    try:
        with loose(mod):
            lo = mod.parse_lh_terms(text, kind, name, region)
    except Exception:   # 느슨하게 읽다 난 오류는 버린다 — 엄격하게 읽은 결과가 그대로 나간다
        return strict
    filled = fill_lh_terms(strict, lo)
    if filled:
        strict["loose"] = filled
    return strict


# ── 분양 공고문 (app/notice_pdf.parse_notice) ─────────────────────────────────
_SALE_SKIP = {"quotes", "facts", "conflicts", "loose"}
_UNKNOWN = ({"unknown": True},)


def fill_notice(found: dict, lo: dict) -> list[str]:
    """found(엄격)에 없는 항목만 lo(느슨)에서 채운다. '못 읽음' 표시({'unknown': True})는 없는 것으로 본다."""
    filled = []
    for k, v in lo.items():
        if k in _SALE_SKIP or v is None or v in _UNKNOWN:
            continue
        if k in found and found[k] is not None and found[k] not in _UNKNOWN:
            continue
        found[k] = v
        filled.append(k)
        if (lo.get("quotes") or {}).get(k):
            found.setdefault("quotes", {})[k] = lo["quotes"][k]
    return filled


def parse_notice(text: str, mod=None) -> dict:
    """app.notice_pdf.parse_notice 와 같은 결과 + 못 읽은 항목은 느슨하게 읽어 채움(`loose` 목록)."""
    if mod is None:
        from app import notice_pdf as mod
    found = mod.parse_notice(text)
    try:
        with loose(mod):
            lo = mod.parse_notice(text)
    except Exception:
        return found
    filled = fill_notice(found, lo)
    if filled:
        found["loose"] = filled
    return found
