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

import httpx

from . import region as RG
from . import rules as R
from .engine import grade
from .market import estimate_jeonse, estimate_market, months_back
from .models import Listing
from .sources.applyhome import RAW_KEYS, ApplyhomeClient, iter_open_listings, probe_fields
from .sources.rtms import RtmsClient
from .sources import cmpet
from . import geo, lawd as LC, notice_pdf, notify, validate

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "listings.json"
RUN_LOG = ROOT / "docs" / "run-log.txt"
RTMS_ERRORS: set[str] = set()
MARKET_BUDGET_SEC = 600      # 실거래 조회에 쓰는 최대 시간 (공공데이터포털이 느려도 수집이 끝나게)
NOTICE_BUDGET_SEC = 300      # 공고문 PDF 읽기에 쓰는 최대 시간


def feature_on(name: str) -> bool:
    """기능 스위치 (docs/config.json 의 features). 적혀 있지 않으면 켜진 것으로 본다. 목록은 FEATURES.md"""
    return bool(notify.load_config().get("features", {}).get(name, True))


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


MARKET_CACHE = ROOT / "docs" / "market-cache.json"
MARKET_FAIL_NOTE = "실거래가 조회에 실패해 시세를 계산하지 못했어요."
MARKET_KEYS = ("mkt_low", "mkt_base", "mkt_note", "mkt_basis", "mkt_count", "mkt_direct_excluded", "mkt_comps",
               "jeonse", "jeonse_note", "jeonse_comps", "jeonse_weak")


def market_fallback(out: list, today: date, log: list[str], path: Optional[Path] = None) -> None:
    """실거래가 조회가 실패한 주택형은 마지막으로 조회에 성공한 날의 시세를 쓰고 '○월 ○일 조회값'이라고 적는다.
    조회에 성공한 주택형(거래 부족 포함)은 그 값을 기록해 둔다 (docs/market-cache.json)."""
    path = path or MARKET_CACHE
    if not out:   # 청약홈이 0건을 준 날은 공고 목록을 그대로 두므로 시세 기록도 지우지 않는다 (2026-10-01 00시 실행에서 기록이 비워진 문제)
        return
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    used = failed = 0
    for L in out:
        if L.mkt_note == MARKET_FAIL_NOTE:
            failed += 1
            c = cache.get(L.id)
            if c:
                for k in MARKET_KEYS:
                    if k in c:
                        setattr(L, k, c[k])
                d = c.get("date", "")
                L.mkt_note = (c.get("mkt_note") or "") + f" · 오늘 실거래가 조회가 실패해 {d[5:7]}월 {d[8:10]}일 조회값을 보여줘요."
                used += 1
        elif not L.mkt_note.startswith("시군구 코드를"):
            cache[L.id] = {k: getattr(L, k) for k in MARKET_KEYS} | {"date": today.isoformat()}
    keep = {L.id for L in out}
    cache = {k: v for k, v in cache.items() if k in keep}
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=0, default=str), encoding="utf-8")
    if failed:
        log.append(f"[경고·시세] 실거래가 조회 실패 {failed}건 → 지난 조회값 사용 {used}건, 시세 없음 {failed - used}건")


def build_listing(raw: dict, rtms: Optional[RtmsClient], today: date, lawd_cache: Optional[dict] = None) -> Optional[Listing]:
    if not raw.get("price"):
        return None
    addr = raw["address"]
    reg = RG.region_of(addr)
    sg = RG.sigungu_of(addr)
    lawd = LC.lawd_for(addr, lawd_cache if lawd_cache is not None else {}, raw.get("area_code_nm"))
    regulated = raw["speculative"] if raw.get("speculative") is not None else RG.is_regulated(addr)
    capital = RG.is_capital(addr)
    price_cap = bool(raw.get("price_cap"))

    mk = {"mkt_low": None, "mkt_base": None, "mkt_note": "시군구 코드를 아직 확인하지 못해 시세를 조회하지 못했어요 (지도 좌표로 확인되면 다음 수집부터 조회)."}
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
            mk["mkt_note"] = MARKET_FAIL_NOTE
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
        sido=RG.sido_of(addr) or raw.get("area_code_nm"), district=RG.sigungu_any(RG.main_address(addr)),
        supply_type=raw.get("supply_type"), house_secd=raw.get("house_secd"), house_dtl=raw.get("house_dtl"),
        rent_secd=raw.get("rent_secd"), special_apply=raw.get("special_apply"),
        special_apply_end=raw.get("special_apply_end"),
        kind=kind_label(raw), category=raw["category"], target=target_of(raw["name"]), unit=raw["unit"], area=raw["area"],
        households=raw.get("households"),
        special_units=raw.get("special_units") if feature_on("special_counts") else None,
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
    if "납입 인정 횟수" in got and prev.get("deposit_count"):
        found["deposit_count"] = prev["deposit_count"]
    if "1순위 가입기간" in got and prev.get("account_months"):
        found["account_months"] = prev["account_months"]
    if "거주 지역 요건" in got and prev.get("residence"):
        found["residence"] = prev["residence"]
    if "다자녀 지역 배정" in got and prev.get("mc_quota"):
        found["mc_quota"] = prev["mc_quota"]
    if "접수 일정" in got and prev.get("schedule"):
        found["schedule"] = prev["schedule"]
    if "공공 일반공급 소득·자산" in got and prev.get("pub_limits"):
        found["pub_limits"] = prev["pub_limits"]
    return found, prev.get("notice_pdf")


NOTICE_CACHE = ROOT / "docs" / "notice-cache.json"
PARSER_VERSION = 7   # 7: 공공분양 일반공급 소득·자산(pub_limits) · 6: 공급유형별 접수 일정(schedule) · 5: 다자녀 지역 배정(mc_quota) · 4: 거주 지역 요건(residence) 추가 · parse_notice 규칙을 바꾸면 올린다 → 모든 공고문을 다시 읽는다   # 공고문에서 읽은 값 보관 (공고문은 한 번 나오면 바뀌지 않는다)


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fetch_text(url: str, L0: Listing, client=None):
    """청약홈 공고 화면에서 공고문 PDF 를 받고, 없으면(LH 공공분양) LH청약플러스에서 받는다 (기능: public_deposit)."""
    text, msg, pdf = notice_pdf.fetch_notice_text(url, client)
    if text or "PDF 링크 못 찾음" not in msg or L0.house_dtl != "국민" or not feature_on("public_deposit"):
        return text, msg, pdf
    from . import lh
    try:
        http = client or httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=notice_pdf.UA)
        data, m2, url2 = lh.fetch_lh_notice(L0.name, http)
        if not data:
            return None, msg + " → " + m2, None
        t2 = notice_pdf.pdf_text(data)
        return (t2, f"PDF 읽음 ({len(t2)}자, {m2}): {url2}", url2) if len(t2) > 500 else (None, msg + " → LH 공고문 글자 없음", None)
    except Exception as e:
        return None, msg + f" → LH 실패 {e.__class__.__name__}", None


def apply_notice(listings: list[Listing], log: list[str], client=None, previous: Optional[dict] = None,
                 cache: Optional[dict] = None) -> None:
    """공고별로 공고문 PDF 를 한 번 읽어 같은 공고의 주택형 전체에 반영한다.
    이번에 못 읽으면 (1) 공고문 보관 기록(cache: 공고번호 → 읽은 값) (2) 지난 실행 결과(previous) 순으로 지난 값을 쓴다.
    직전 실행에서 공고가 잠깐 빠졌다 돌아와도 보관 기록으로 되살린다 (2026-09-30 강변역 사례)."""
    previous = previous or {}
    cache = {} if cache is None else cache
    groups: dict[str, list[Listing]] = {}
    for L in listings:
        if L.url:
            groups.setdefault(L.url, []).append(L)
    import time
    from concurrent.futures import ThreadPoolExecutor, wait
    start = time.monotonic()
    # 이미 같은 읽기 규칙(PARSER_VERSION)으로 읽은 공고문은 다시 받지 않는다 (공고문은 바뀌지 않고, 받기·읽기가 가장 오래 걸린다)
    fresh = {url for url, Ls in groups.items() if cache.get(Ls[0].id.split("-")[0], {}).get("v") == PARSER_VERSION}
    ex = ThreadPoolExecutor(max_workers=6)
    futs = {url: ex.submit(_fetch_text, url, Ls[0], client) for url, Ls in groups.items() if url not in fresh}
    wait(list(futs.values()), timeout=NOTICE_BUDGET_SEC)
    ex.shutdown(wait=False, cancel_futures=True)
    log.append(f"[시간] 공고문 {len(groups)}건 중 새로 읽기 {len(futs)}건 {time.monotonic() - start:.0f}초 (보관 기록 사용 {len(fresh)}건)")
    for url, Ls in groups.items():
        nid = Ls[0].id.split("-")[0]
        if url in fresh:
            text, msg, pdf = None, "보관 기록", cache[nid].get("notice_pdf")
            found = dict(cache[nid]["found"])
        else:
            f = futs[url]
            if not f.done() or f.cancelled():
                text, msg, pdf = None, "시간 제한으로 이번 실행에서는 읽지 못했어요", None
            else:
                try:
                    text, msg, pdf = f.result()
                except Exception as e:
                    text, msg, pdf = None, f"읽기 실패: {e.__class__.__name__}", None
            found = notice_pdf.parse_notice(text) if text else {}
            log.append(f"[공고문] {Ls[0].name}: {msg} → {found or '추출 없음'}")
            if text and found:
                cache[nid] = {"name": Ls[0].name, "found": found, "notice_pdf": pdf, "v": PARSER_VERSION}
        if not text and url not in fresh:
            prev = previous.get(Ls[0].id)
            if cache.get(nid, {}).get("found"):
                found, pdf = dict(cache[nid]["found"]), cache[nid].get("notice_pdf")
                log.append(f"[공고문] {Ls[0].name}: 이번엔 못 읽어 보관해 둔 공고문 값을 써요 → {found}")
            elif prev and prev.get("from_notice"):
                found, pdf = _from_previous(prev)
                log.append(f"[공고문] {Ls[0].name}: 이번엔 못 읽어 지난 실행에서 공고문으로 읽은 값을 유지해요 → {found}")
        if text:   # 못 읽은 항목은 원문 문장을 남겨 규칙을 근거 있게 고친다
            for key, word in (("rewin_years", "재당첨"), ("need_head", "무주택세대"), ("balance", "입주지정기간")):
                if key not in found:
                    for sn in notice_pdf.snippets(text, word):
                        log.append(f"[공고문·원문] {Ls[0].name} ({word}): …{sn}…")
        labels = {"need_head": "세대주 요건", "price_cap": "분양가상한제", "residence_duty": "실거주 의무",
                  "balance": "잔금일", "ext": "발코니 확장비", "rewin_years": "재당첨 제한",
                  "account_months": "1순위 가입기간", "deposit_count": "납입 인정 횟수", "residence": "거주 지역 요건", "mc_quota": "다자녀 지역 배정", "schedule": "접수 일정", "pub_limits": "공공 일반공급 소득·자산"}
        for L in Ls:
            L.notice_pdf = pdf
            L.from_notice = [labels[k] for k in found if k in labels and not (k == "ext" and len(Ls) != 1)
                             and not (k == "residence" and not feature_on("residence_v2"))
                             and not (k == "mc_quota" and not feature_on("mc_quota"))
                             and not (k == "schedule" and not feature_on("notice_schedule"))
                             and not (k == "pub_limits" and not feature_on("pub_general_limits"))]
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
            if "account_months" in found and feature_on("account_rules"):
                L.account_months = found["account_months"]
            if "deposit_count" in found and feature_on("public_deposit"):
                L.deposit_count = found["deposit_count"]
            if "residence" in found and feature_on("residence_v2"):
                L.residence = found["residence"]
            if "mc_quota" in found and feature_on("mc_quota"):
                L.mc_quota = found["mc_quota"]
            if "pub_limits" in found and feature_on("pub_general_limits"):
                L.pub_limits = found["pub_limits"]
            if "schedule" in found and feature_on("notice_schedule"):
                L.schedule = found["schedule"]
                sp = found["schedule"].get("special")
                if sp and not L.special_apply:      # 청약홈 API 가 특별공급 날짜를 안 준 공고만 공고문 날짜로 채운다
                    L.special_apply, L.special_apply_end = sp
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
    lawd_cache = LC.load()
    lawds = {LC.lawd_for(r["address"], lawd_cache, r.get("area_code_nm")) for r in raws if r.get("price")}
    keys = [(k, l, ym) for l in sorted(x for x in lawds if x) for k in ("trade", "presale", "rent") for ym in months]
    pf = rt.prefetch(keys, budget_sec=MARKET_BUDGET_SEC)
    log.append(f"[시간] 공고 {len(raws)}건 {t1 - t0:.0f}초 · 실거래 요청 {pf['total']}건 {pf['seconds']:.0f}초 "
               f"(성공 {pf['done']}, 실패 {pf['failed']}, 시간 초과로 생략 {pf['skipped']})")
    for msg, n in pf.get("errors", []):
        log.append(f"[실거래 오류] {n}건: {msg}")
    for raw in raws:
        try:
            L = build_listing(raw, rt, today, lawd_cache)
        except Exception as e:  # 한 공고가 실패해도 나머지는 진행
            log.append(f"[건너뜀] {raw.get('name')} {raw.get('unit')}: {e}")
            continue
        if L:
            out.append(L)
    market_fallback(out, today, log)
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
            cache = _load_cache(NOTICE_CACHE)
            # 처음 한 번: 지난 결과에서 공고문 값을 보관 기록으로 옮긴다
            for x in prev.values():
                n = x["id"].split("-")[0]
                if n not in cache and x.get("from_notice"):
                    f0, pdf0 = _from_previous(x)
                    if f0:
                        cache[n] = {"name": x.get("name"), "found": f0, "notice_pdf": pdf0}
            apply_notice(out, log, previous=prev, cache=cache)
            if not dry_run:
                live = {L.id.split("-")[0] for L in out}
                NOTICE_CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in live}, ensure_ascii=False, indent=1,
                                                   sort_keys=True), encoding="utf-8")
        except Exception as e:
            log.append(f"[공고문] 전체 실패: {e}")
        on = feature_on
        try:
            if on("competition"):
                cmpet.apply_competition(out, log, today.isoformat())
        except Exception as e:
            log.append(f"[경쟁률] 전체 실패: {e}")
        try:
            if on("area_competition"):
                hist = cmpet.update_history(ah, out, log, today)
                cmpet.attach_area_comps(out, hist, today)
                if not dry_run:
                    cmpet.save_history(hist)
        except Exception as e:
            log.append(f"[지난 경쟁률] 전체 실패: {e}")
        try:
            geo.apply_geo(out, log, previous=prev, probe=not dry_run, geocode_on=on("naver_map"), nearby_on=on("nearby"),
                          lawd_cache=lawd_cache)
            if not dry_run:
                LC.save(lawd_cache)
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
        if feature_on("ntfy_alerts"):
            log += notify.send(msgs, cfg)
        else:   # ntfy.sh 공개 주제는 누구나 보낼 수 있어 보내기를 제한할 수 있을 때까지 끔 (기능: ntfy_alerts)
            log.append(f"[알림] 꺼져 있어 보내지 않음 (ntfy_alerts 스위치) · 보낼 알림 {len(msgs)}건")
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
