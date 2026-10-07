"""시세·전세 추정.

순서:
1. 같은 단지 분양권 전매·매매 거래 (단지명 일치) — 가장 믿을 만함
2. 같은 시군구, 준공 10년 이내, 같은 평형(전용 ±3㎡) 매매 거래
기준 시세 = 중앙값, 보수 시세 = 하위 25% (거래 4건 미만이면 기준 × 0.9)
전세 = 같은 조건 전세(월세 0) 보증금 중앙값 × 입주장 할인
"""
from __future__ import annotations

import re
import statistics
from datetime import date
from typing import Optional

from . import rules as R


def months_back(today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s()·\-]|아파트", "", s or "")


def same_complex(apt: str, name: str) -> bool:
    a, n = _norm(apt), _norm(name)
    if not a or not n:
        return False
    return a in n or n in a


def _in_band(area: Optional[float], target: Optional[float]) -> bool:
    return area is not None and target is not None and abs(area - target) <= R.AREA_BAND


def _p25(xs: list[float]) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * 0.25
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _summary(amounts_manwon: list[float]) -> tuple[float, float]:
    base = statistics.median(amounts_manwon) / 10000
    low = _p25(amounts_manwon) / 10000 if len(amounts_manwon) >= 4 else base * R.LOW_DISCOUNT
    return round(low, 2), round(base, 2)


MAX_COMPS = 8


def _comp(r: dict, label: str, value_key: str) -> dict:
    """화면에 보여줄 근거 거래 한 건 (금액은 억 원)."""
    return {"apt": r.get("apt", ""), "umd": r.get("umd") or "", "area": r.get("area"), "floor": r.get("floor"), "dong": r.get("dong") or "",
            "amount": round((r.get(value_key) or 0) / 10000, 2), "date": r.get("date", ""),
            "kind": label, "direct": r.get("deal_type") == "직거래"}


def _recent(comps: list[dict]) -> list[dict]:
    return sorted(comps, key=lambda c: c["date"], reverse=True)[:MAX_COMPS]


def estimate_market(name: str, area: Optional[float], trades: list[dict], presales: list[dict],
                    this_year: int, area_fallback: bool = False) -> dict:
    # 실제 시장 거래만 쓴다: 해제 거래는 parse_items 에서 이미 빠지고, 직거래(가족 간 저가 거래 등이 섞임)도 뺀다
    is_direct = lambda r: r.get("deal_type") == "직거래"
    newbuild = lambda r: bool(r.get("build_year")) and r["build_year"] >= this_year - R.NEW_BUILD_YEARS
    # 뺀 직거래 수는 실제로 비교 대상이 됐을 거래만 센다 (같은 단지·같은 평형, 없으면 같은 구 신축·같은 평형)
    own_direct = sum(1 for r in presales + trades
                     if is_direct(r) and r.get("amount") and same_complex(r["apt"], name) and _in_band(r["area"], area))
    area_direct = sum(1 for r in trades if is_direct(r) and r.get("amount") and _in_band(r["area"], area) and newbuild(r))
    wide_direct = sum(1 for r in trades if is_direct(r) and r.get("amount") and r.get("area") and area and abs(r["area"] - area) <= R.AREA_BAND_WIDE and newbuild(r))
    trades = [r for r in trades if not is_direct(r)]
    presales = [r for r in presales if not is_direct(r)]
    # 분양권전매 API 의 ownershipGbn 은 '분'(분양권) / '입'(입주권) 약자로 온다 (2026-09-29 실제 응답)
    names = {"분": "분양권", "입": "입주권"}
    tagged = [(r, names.get(r.get("kind") or "", r.get("kind") or "분양권")) for r in presales] + [(r, "매매") for r in trades]
    own = [(r, k) for r, k in tagged if r.get("amount") and same_complex(r["apt"], name) and _in_band(r["area"], area)]
    if own:
        low, base = _summary([r["amount"] for r, _ in own])
        return {"mkt_low": low, "mkt_base": base, "mkt_basis": "same_complex", "mkt_count": len(own),
                "mkt_comps": _recent([_comp(r, k, "amount") for r, k in own]),
                "mkt_direct_excluded": own_direct,
                "mkt_note": f"같은 단지 같은 평형 거래 {len(own)}건 기준 (최근 {R.MARKET_MONTHS}개월)"}
    comps = [r for r in trades
             if r.get("amount") and _in_band(r["area"], area)
             and r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    if len(comps) >= 3:
        low, base = _summary([r["amount"] for r in comps])
        return {"mkt_low": low, "mkt_base": base, "mkt_basis": "district_newbuild", "mkt_count": len(comps),
                "mkt_comps": _recent([_comp(r, "매매", "amount") for r in comps]),
                "mkt_direct_excluded": area_direct,
                "mkt_note": f"같은 구 준공 {R.NEW_BUILD_YEARS}년 이내 같은 평형 매매 {len(comps)}건 기준 (최근 {R.MARKET_MONTHS}개월)"}
    # 기능 mkt_area_fallback (2026-10-07, evidence/qa/market-probe.txt): 같은 평형 거래가 3건 미만이면 같은 구 준공 10년 이내
    # 비슷한 면적(±10㎡) 매매의 ㎡당 가격 중앙값(보수: 하위 25%) × 이 주택형 전용면적. 107㎡처럼 거래가 드문 평형용 — '추정'으로 표시
    wide = [r for r in trades if area_fallback and area and r.get("amount") and r.get("area") and abs(r["area"] - area) <= R.AREA_BAND_WIDE and newbuild(r)]
    if len(wide) >= R.AREA_FALLBACK_MIN:
        ppa = [r["amount"] / r["area"] for r in wide]
        base = statistics.median(ppa) * area / 10000
        low = _p25(ppa) * area / 10000 if len(ppa) >= 4 else base * R.LOW_DISCOUNT
        return {"mkt_low": round(low, 2), "mkt_base": round(base, 2), "mkt_basis": "district_area_ppa", "mkt_count": len(wide),
                "mkt_comps": _recent([_comp(r, "매매", "amount") for r in wide]),
                "mkt_direct_excluded": wide_direct,
                "mkt_note": f"같은 평형 거래가 부족해 같은 구 준공 {R.NEW_BUILD_YEARS}년 이내 비슷한 면적(±{R.AREA_BAND_WIDE:g}㎡) 매매 {len(wide)}건의 "
                            f"㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월)"}
    return {"mkt_low": None, "mkt_base": None, "mkt_basis": None, "mkt_count": len(comps),
            "mkt_comps": _recent([_comp(r, "매매", "amount") for r in comps]),
            "mkt_direct_excluded": area_direct,
            "mkt_note": "비교할 거래가 부족해요. 시세를 직접 확인하세요."}


def estimate_jeonse(name: str, area: Optional[float], rents: list[dict], this_year: int) -> dict:
    pool = [r for r in rents if r.get("deposit") and not r.get("monthly") and _in_band(r["area"], area)]
    own = [r for r in pool if same_complex(r["apt"], name)]
    comps = own or [r for r in pool if r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    shown = _recent([_comp(r, "전세", "deposit") for r in comps])
    if len(comps) < 3 and not own:
        return {"jeonse": None, "jeonse_note": "전세 거래가 부족해 추정하지 못했어요.", "jeonse_weak": True,
                "jeonse_comps": shown}
    v = statistics.median([r["deposit"] for r in comps]) / 10000 * R.JEONSE_MOVEIN_DISCOUNT
    src = "같은 단지" if own else f"같은 구 준공 {R.NEW_BUILD_YEARS}년 이내"
    return {"jeonse": round(v, 2),
            "jeonse_note": f"{src} 전세 {len(comps)}건 중앙값에서 입주장 할인 {int((1-R.JEONSE_MOVEIN_DISCOUNT)*100)}%",
            "jeonse_weak": len(comps) < 5, "jeonse_comps": shown}
