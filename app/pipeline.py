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
from .sources.applyhome import RAW_KEYS, ApplyhomeClient, iter_open_listings, probe_fields
from .sources.rtms import RtmsClient
from .sources import cmpet
from . import geo, notice_pdf, notify, validate

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "listings.json"
RUN_LOG = ROOT / "docs" / "run-log.txt"
RTMS_ERRORS: set[str] = set()
MARKET_BUDGET_SEC = 600      # 실거래 조회에 쓰는 최대 시간 (공공데이터포털이 느려도 수집이 끝나게)
NOTICE_BUDGET_SEC = 300      # 공고문 PDF 읽기에 쓰는 최대 시간


def kind_label(raw: dict) -> str:
    k = raw.get("kind") or ""
    if raw["category"] == "general":
        return "일반분양 (특별공급·1순위)" if k in ("", "APT", "민영", "국민") else f"일반분양 · {k}"
    return k or "무순위·잔여세대"


def target_of(name: str) -> Optional[str]:
    if "신혼희망타운" in name:
        return "신혼부부"
    if "청년" in name and "주택" in name:
        return "청년"
    return None


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
    # 준공 임박(입주 6개월 이내) 단지는 중도금 없이 잔금, 그 외엔 중도금 60% 가정
    soon = (today + timedelta(days=183)).isoformat()[:7]
    built = bool(raw.get("move_in")) and raw["move_in"][:7] <= soon
    # 공고문에서 못 읽을 때의 기본값 (주택공급에 관한 규칙 제54조 기준 추정):
    # 규제지역(투기과열·조정대상) 10년, 비규제지역이면서 분양가상한제가 아니면 재당첨 제한 대상이 아님
    limits = [("재당첨 제한", "10년" if regulated else ("공고문 확인" if price_cap else "없음"))]
    if price_cap:
        limits.append(("실거주 의무", "공고문 확인"))

    return Listing(
        id=f"{raw['notice_no']}-{raw.get('house_ty') or raw['unit']}",
        name=raw["name"], address=addr, region=reg, sigungu=sg,
        sido=RG.sido_of(addr) or raw.get("area_code_nm"), district=RG.sigungu_any(addr),
        supply_type=raw.get("supply_type"), house_secd=raw.get("house_secd"), house_dtl=raw.get("house_dtl"),
        rent_secd=raw.get("rent_secd"), special_apply=raw.get("special_apply"),
        special_apply_end=raw.get("special_apply_end"),
        kind=kind_label(raw), category=raw["category"], target=target_of(raw["name"]), unit=raw["unit"], area=raw["area"],
        households=raw.get("households"),
        notice=raw["notice"], apply=raw["apply"], apply_end=raw["apply_end"], winner=raw["winner"],
        contract=raw["contract"], move_in=raw["move_in"],
        price=raw["price"], ext=0.0, contract_rate=0.10, mid_rate=0.0 if built else 0.6,
        **mk, **js,
        capital=capital, regulated=bool(regulated),
        land_permit=bool(regulated) and capital and today.isoformat() <= R.LAND_PERMIT_UNTIL,
        price_cap=price_cap, residence_duty=None if price_cap else 0,
        unregistered=True,
        need_head=bool(regulated), need_account=not remainder,
        limits=limits, url=raw.get("url"),
    )


def _from_previous(prev: dict) -> tuple[dict, Optional[str]]:
    """지난 실행에서 공고문으로 읽었던 값을 되살린다 (공고문은 한 번 나오면 바뀌지 않는다)."""
    got = prev.get("from_notice") or []
    found: dict = {}
    if "세대주 요건" in got:
        found["need_head"] = prev.get("need_head")
    if "분양가상한제" in got:
        found["price_cap"] = prev.get("price_cap")
    if "실거주 의무" in got and prev.get("residence_duty") is not None:
        found["residence_duty"] = prev["residence_duty"]
    if "잔금일" in got and prev.get("balance"):
        found["balance"] = prev["balance"]
    if "발코니 확장비" in got and prev.get("ext"):
        found["ext"] = prev["ext"]
    if "재당첨 제한" in got:
        v = next((l[1] for l in prev.get("limits", []) if l[0] == "재당첨 제한"), None)
        if v and v.endswith("년"):
            found["rewin_years"] = int(v[:-1])
        elif v == "없음":
            found["rewin_years"] = 0
    return found, prev.get("notice_pdf")


def apply_notice(listings: list[Listing], log: list[str], client=None, previous: Optional[dict] = None) -> None:
    """공고별로 공고문 PDF 를 한 번 읽어 같은 공고의 주택형 전체에 반영한다.
    이번에 못 읽으면 지난 실행에서 읽은 값(previous: 공고 id → 지난 공고 데이터)을 유지한다."""
    previous = previous or {}
    groups: dict[str, list[Listing]] = {}
    for L in listings:
        if L.url:
            groups.setdefault(L.url, []).append(L)
    import time
    from concurrent.futures import ThreadPoolExecutor, wait
    start = time.monotonic()
    ex = ThreadPoolExecutor(max_workers=6)
    futs = {url: ex.submit(notice_pdf.fetch_notice_text, url, client) for url in groups}
    wait(list(futs.values()), timeout=NOTICE_BUDGET_SEC)
    ex.shutdown(wait=False, cancel_futures=True)
    log.append(f"[시간] 공고문 {len(groups)}건 {time.monotonic() - start:.0f}초")
    for url, Ls in groups.items():
        f = futs[url]
        if not f.done():
            log.append(f"[공고문] {Ls[0].name}: 시간 제한으로 이번 실행에서는 읽지 못했어요")
            continue
        try:
            text, msg, pdf = f.result()
        except Exception as e:
            text, msg, pdf = None, f"읽기 실패: {e.__class__.__name__}", None
        found = notice_pdf.parse_notice(text) if text else {}
        log.append(f"[공고문] {Ls[0].name}: {msg} → {found or '추출 없음'}")
        if not text:
            prev = previous.get(Ls[0].id)
            if prev and prev.get("from_notice"):
                found, pdf = _from_previous(prev)
                log.append(f"[공고문] {Ls[0].name}: 이번엔 못 읽어 지난 실행에서 공고문으로 읽은 값을 유지해요 → {found}")
        if text:   # 못 읽은 항목은 원문 문장을 남겨 규칙을 근거 있게 고친다
            for key, word in (("rewin_years", "재당첨"), ("need_head", "무주택세대"), ("balance", "입주지정기간")):
                if key not in found:
                    for sn in notice_pdf.snippets(text, word):
                        log.append(f"[공고문·원문] {Ls[0].name} ({word}): …{sn}…")
        labels = {"need_head": "세대주 요건", "price_cap": "분양가상한제", "residence_duty": "실거주 의무",
                  "balance": "잔금일", "ext": "발코니 확장비", "rewin_years": "재당첨 제한"}
        for L in Ls:
            L.notice_pdf = pdf
            L.from_notice = [labels[k] for k in found if k in labels and not (k == "ext" and len(Ls) != 1)]
            if "need_head" in found:
                L.need_head = found["need_head"]
            if "price_cap" in found:
                L.price_cap = found["price_cap"]
            if not (L.capital and L.price_cap):
                L.residence_duty = 0            # 거주의무는 수도권 분양가상한제 주택에만 있다
            elif "residence_duty" in found:
                L.residence_duty = found["residence_duty"]
            elif L.residence_duty == 0:
                L.residence_duty = None
            if "balance" in found:
                L.balance = found["balance"]
            if "ext" in found and len(Ls) == 1:
                L.ext = found["ext"]
            if "rewin_years" in found:
                n = found["rewin_years"]
                L.limits = [x for x in L.limits if x[0] != "재당첨 제한"]
                L.limits.insert(0, ("재당첨 제한", f"{n}년" if n else "없음"))
            L.limits = [x for x in L.limits if x[0] != "실거주 의무"]
            duty = L.residence_duty
            L.limits.append(("실거주 의무", "공고문 확인" if duty is None else (f"{duty}년" if duty else "없음")))


def run(dry_run: bool = False, today: Optional[date] = None, read_notices: bool = True) -> list[Listing]:
    today = today or date.today()
    since = (today - timedelta(days=60)).isoformat()
    ah = ApplyhomeClient()
    rt = RtmsClient()
    log: list[str] = []
    out: list[Listing] = []
    import time
    t0 = time.monotonic()
    raws = list(iter_open_listings(ah, today.isoformat(), since))
    t1 = time.monotonic()
    months = months_back(today, R.MARKET_MONTHS)
    lawds = {RG.lawd_of(RG.sigungu_of(r["address"])) for r in raws if r.get("price")}
    keys = [(k, l, ym) for l in sorted(x for x in lawds if x) for k in ("trade", "presale", "rent") for ym in months]
    pf = rt.prefetch(keys, budget_sec=MARKET_BUDGET_SEC)
    log.append(f"[시간] 공고 {len(raws)}건 {t1 - t0:.0f}초 · 실거래 요청 {pf['total']}건 {pf['seconds']:.0f}초 "
               f"(성공 {pf['done']}, 실패 {pf['failed']}, 시간 초과로 생략 {pf['skipped']})")
    for raw in raws:
        try:
            L = build_listing(raw, rt, today)
        except Exception as e:  # 한 공고가 실패해도 나머지는 진행
            log.append(f"[건너뜀] {raw.get('name')} {raw.get('unit')}: {e}")
            continue
        if L:
            out.append(L)
    prev_rows: list = []
    try:
        prev_rows = json.loads(notify.PREVIOUS.read_text(encoding="utf-8"))
    except Exception:
        pass
    prev = {x["id"]: x for x in prev_rows}
    if not out and prev_rows:
        # 청약홈 API 가 일시적으로 빈 목록을 돌려주면(2026-09-30 00시대 실제 발생) 서비스가 비지 않게 지난 결과를 유지한다
        log.append(f"[경고] 청약홈에서 공고를 0건 받았어요. 일시적인 문제일 수 있어 지난 결과({len(prev_rows)}건)를 그대로 둬요")
        from .sources.applyhome import ENDPOINTS
        for cat in ("general", "remainder"):   # 원인 확인용: 날짜 필터 없이 / 있이 받은 건수
            for label, extra in (("필터 없이", {}), (f"공고일 {since} 이후", {"cond[RCRIT_PBLANC_DE::GTE]": since})):
                try:
                    j = ah._get(ENDPOINTS[cat][0], perPage=1, **extra)
                    log.append(f"[경고·확인] {cat} {label}: totalCount={j.get('totalCount')} matchCount={j.get('matchCount')} "
                               f"첫 공고={[(d.get('HOUSE_NM'), d.get('RCRIT_PBLANC_DE')) for d in j.get('data', [])]}")
                except Exception as e:
                    log.append(f"[경고·확인] {cat} {label}: 실패 {e.__class__.__name__} {e}")
        for l in log:
            print(l)
        if not dry_run:
            DATA.parent.mkdir(parents=True, exist_ok=True)
            DATA.write_text(json.dumps(prev_rows, ensure_ascii=False, indent=1), encoding="utf-8")
            RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
            RUN_LOG.write_text(f"실행: {today.isoformat()} · 공고 0건 받음 → 지난 결과 {len(prev_rows)}건 유지\n\n" + "\n".join(log) + "\n",
                               encoding="utf-8")
        return []
    if read_notices:
        try:
            apply_notice(out, log, previous=prev)
        except Exception as e:
            log.append(f"[공고문] 전체 실패: {e}")
        try:
            cmpet.apply_competition(out, log, today.isoformat())
        except Exception as e:
            log.append(f"[경쟁률] 전체 실패: {e}")
        try:
            geo.apply_geo(out, log, previous=prev, probe=not dry_run)
        except Exception as e:
            log.append(f"[위치] 전체 실패: {e}")
    log += [f"[실거래가 경고] {m}" for m in sorted(RTMS_ERRORS)]
    # 실제 응답 필드 기록 (필터·기능을 추가하기 전에 근거로 쓴다)
    for name, keys in RAW_KEYS.items():
        log.append(f"[응답 필드] {name}: {', '.join(keys)}")
    try:
        for name, keys in probe_fields(ah).items():
            log.append(f"[응답 필드·미수집] {name}: {', '.join(keys)}")
    except Exception as e:
        log.append(f"[응답 필드·미수집] 확인 실패: {e}")

    log += validate.run_checks(out, today)
    lines = summary(out)
    cfg = notify.load_config()
    msgs = notify.build_messages(out, notify.load_previous_ids(), today, cfg)
    if not dry_run:
        log += notify.send(msgs, cfg)
    else:
        log += [f"(보낼 알림) {m['title']}" for m in msgs]
    for l in log:
        print(l)
    if not dry_run:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(json.dumps([l.model_dump() for l in out], ensure_ascii=False, indent=1), encoding="utf-8")
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        RUN_LOG.write_text(f"실행: {today.isoformat()} · 공고 {len(out)}건\n\n" + "\n".join(lines + [""] + log) + "\n",
                           encoding="utf-8")
        print(f"저장: {DATA} ({len(out)}건)")
    return out


def summary(listings: list[Listing]) -> list[str]:
    lines = []
    for L in sorted(listings, key=lambda L: (["lotto", "consider", "flat", "pass", "unknown"].index(grade(L)["grade"]), L.name)):
        g = grade(L)
        m = "" if g["lo"] is None else f"마진 {g['lo']:+.2f}~{g['hi']:+.2f}억"
        head = "세대주" if L.need_head else "세대구성원"
        lines.append(f"{g['name']:<5} {L.name} {L.unit} · {L.sigungu or L.region} · 분양가 {L.price:.2f}억 {m} · {head}")
    for l in lines:
        print(l)
    return lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    run(dry_run=ap.parse_args().dry_run)
