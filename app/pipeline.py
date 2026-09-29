"""매일 한 번 돌리는 수집 작업.

    python -m app.pipeline            # 실제 API 호출 → data/listings.json 저장
    python -m app.pipeline --dry-run  # 저장하지 않고 요약만 출력

접수 중이거나 예정인 공고를 주택형 단위로 펼치고, 시세·전세를 붙이고, 등급을 매겨 저장한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from . import region as RG
from . import rules as R
from .engine import grade
from .market import estimate_jeonse, estimate_market, months_back
from .models import Listing
from .sources.applyhome import ApplyhomeClient, iter_open_listings
from .sources.rtms import RtmsClient

DATA = Path(__file__).resolve().parent.parent / "data" / "listings.json"
RTMS_ERRORS: set[str] = set()


def build_listing(raw: dict, rtms: Optional[RtmsClient], today: date) -> Optional[Listing]:
    if not raw.get("price"):
        return None
    addr = raw["address"]
    reg = RG.region_of(addr)
    sg = RG.sigungu_of(addr)
    lawd = RG.lawd_of(sg)
    regulated = raw["speculative"] if raw.get("speculative") is not None else RG.is_regulated(addr)
    capital = RG.is_capital(addr)
    price_cap = bool(raw.get("price_cap"))

    mk = {"mkt_low": None, "mkt_base": None, "mkt_note": "지역코드를 몰라 시세를 조회하지 못했어요."}
    js = {"jeonse": None, "jeonse_note": "", "jeonse_weak": False}
    if rtms and lawd:
        months = months_back(today, R.MARKET_MONTHS)

        def safe(kind):
            try:
                return rtms.recent(kind, lawd, months)
            except Exception as e:
                RTMS_ERRORS.add(str(e)[:160])
                return None
        trades, presales, rents = safe("trade"), safe("presale"), safe("rent")
        if trades is not None or presales is not None:
            mk = estimate_market(raw["name"], raw["area"], trades or [], presales or [], today.year)
        else:
            mk["mkt_note"] = "실거래가 조회에 실패해 시세를 계산하지 못했어요."
        if rents is not None:
            js = estimate_jeonse(raw["name"], raw["area"], rents, today.year)

    remainder = raw["category"] == "remainder"
    limits = [("재당첨 제한", "10년" if regulated else "공고문 확인")]
    if price_cap:
        limits.append(("실거주 의무", "공고문 확인"))

    return Listing(
        id=f"{raw['notice_no']}-{raw.get('house_ty') or raw['unit']}",
        name=raw["name"], address=addr, region=reg, sigungu=sg,
        kind=raw["kind"], category=raw["category"], unit=raw["unit"], area=raw["area"],
        households=raw.get("households"),
        notice=raw["notice"], apply=raw["apply"], apply_end=raw["apply_end"], winner=raw["winner"],
        contract=raw["contract"], move_in=raw["move_in"],
        price=raw["price"], ext=0.0, contract_rate=0.10, mid_rate=0.0 if remainder else 0.6,
        **mk, **js,
        capital=capital, regulated=bool(regulated),
        land_permit=bool(regulated) and capital and today.isoformat() <= R.LAND_PERMIT_UNTIL,
        price_cap=price_cap, residence_duty=None if price_cap else 0,
        unregistered=True,
        need_head=bool(regulated), need_account=not remainder,
        limits=limits, url=raw.get("url"),
    )


def run(dry_run: bool = False, today: Optional[date] = None) -> list[Listing]:
    today = today or date.today()
    since = (today - timedelta(days=60)).isoformat()
    ah = ApplyhomeClient()
    rt = RtmsClient()
    out: list[Listing] = []
    for raw in iter_open_listings(ah, today.isoformat(), since):
        try:
            L = build_listing(raw, rt, today)
        except Exception as e:  # 한 공고가 실패해도 나머지는 진행
            print(f"[건너뜀] {raw.get('name')} {raw.get('unit')}: {e}", file=sys.stderr)
            continue
        if L:
            out.append(L)
    summary(out)
    for msg in sorted(RTMS_ERRORS):
        print(f"[실거래가 경고] {msg}")
    if not dry_run:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(json.dumps([l.model_dump() for l in out], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {DATA} ({len(out)}건)")
    return out


def summary(listings: list[Listing]) -> None:
    for L in listings:
        g = grade(L)
        m = "" if g["lo"] is None else f"마진 {g['lo']:+.2f}~{g['hi']:+.2f}억"
        print(f"{g['name']:<5} {L.name} {L.unit} · {L.region} {L.sigungu or ''} · 분양가 {L.price:.2f}억 {m}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    run(dry_run=ap.parse_args().dry_run)
