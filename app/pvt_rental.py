"""청약홈 공공지원 민간임대 공고 수집 — 1단계: 목록·일정·주택형·공급금액만, 자격 판정은 하지 않음 (기능 pvt_rental, 2026-10-21 사용자 'GH 임대 → 공공지원 민간임대 순서로 추가').

청약홈 분양정보 API(odcloud ApplyhomeInfoDetailSvc)의 공공지원 민간임대 개요·주택형을 읽어 docs/pvt-rental.json 으로. 청약·LH·SH 수집과 따로 돈다.
응답 필드는 2026-10-21 tools/qa/pvt_probe.py 로 확인(evidence/qa/pvt-rent-probe.json)했고, 금액 뜻은 같은 공고의 청약홈 공고 화면
(울산반구 수자인 더센트럴 2026850052, selectPRMOLttotPblancDetailView.do)과 대조했다:
  SUPLY_AMOUNT = '공급금액'(만원, 주택형별 최고 금액 · 천원 단위 절사), SUBSCRPT_REQST_AMOUNT = '청약신청금'(만원),
  SPSPLY_YGMN·NEW_MRRG·AGED_HSHLDCO = 특별공급 청년·신혼부부·고령자, GNSPLY_HSHLDCO = 일반공급, SUPLY_HSHLDCO = 계.
임대보증금·월 임대료는 API·청약홈 화면에 없어 화면은 '모집공고문 확인'. 자격 판정은 2단계(정답 데이터 뒤)에서.
실행: python -m app.pvt_rental (Actions '공공지원 민간임대 수집' pvt-rental.yml, DATA_GO_KR_KEY)"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.sources.applyhome import ApplyhomeClient, to_date, to_int

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "pvt-rental.json"
LOG = ROOT / "evidence" / "qa" / "pvt-rental-log.txt"
KST = timezone(timedelta(hours=9))
DETAIL, MODEL = "/getPblPvtRentLttotPblancDetail", "/getPblPvtRentLttotPblancMdl"
# 기능 pvt_rental_urbty (2026-10-22 사용자 '임대 공고 중 안 다루는 것도 다 수집'): 청약홈 '오피스텔·도시형·민간임대' 묶음 중 민간임대만.
# 오피스텔·도시형생활주택은 분양이라 넣지 않는다. 구분은 개요의 HOUSE_DTL_SECD_NM(2026-10-14 [응답 필드·미수집] 로 있음 확인) — 값에 '민간임대'가 있을 때만.
URBTY_DETAIL, URBTY_MODEL = "/getUrbtyOfctlLttotPblancDetail", "/getUrbtyOfctlLttotPblancMdl"
LOOKBACK_DAYS = 90
KEEP_AFTER_WINNER_DAYS = 14


def feature_on(name: str) -> bool:
    """기능 스위치 (docs/config.json features, 적혀 있지 않으면 켜짐)"""
    try:
        return bool(json.loads((ROOT / "docs" / "config.json").read_text(encoding="utf-8")).get("features", {}).get(name, True))
    except Exception:
        return True


def _region(addr: str) -> Optional[str]:
    return (addr or "").split(" ")[0] or None


def _f(v) -> Optional[float]:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _still_open(d: dict, since: str, today: date) -> bool:
    """공고일이 since 이후이고, 발표 뒤 KEEP_AFTER_WINNER_DAYS 일(발표일이 없으면 접수 마감일)이 아직 안 지난 공고"""
    end = to_date(d.get("SUBSCRPT_RCEPT_ENDDE")) or to_date(d.get("SUBSCRPT_RCEPT_BGNDE"))
    w = to_date(d.get("PRZWNER_PRESNATN_DE"))
    last = (date.fromisoformat(w) + timedelta(days=KEEP_AFTER_WINNER_DAYS)).isoformat() if w else end
    return (to_date(d.get("RCRIT_PBLANC_DE")) or "") >= since and bool(last) and last >= today.isoformat()


def record(d: dict, models: list[dict], kind: str = "공공지원 민간임대") -> dict:
    no = str(d.get("PBLANC_NO") or d.get("HOUSE_MANAGE_NO"))
    a, b, w = to_date(d.get("SUBSCRPT_RCEPT_BGNDE")), to_date(d.get("SUBSCRPT_RCEPT_ENDDE")), to_date(d.get("PRZWNER_PRESNATN_DE"))
    units = []
    for m in models:
        sp = {k: to_int(m.get(f)) or 0 for k, f in (("청년", "SPSPLY_YGMN_HSHLDCO"), ("신혼부부", "SPSPLY_NEW_MRRG_HSHLDCO"), ("고령자", "SPSPLY_AGED_HSHLDCO"))}
        units.append({"complex": None, "type": m.get("TP") or m.get("HOUSE_TY") or m.get("GP"), "area": _f(m.get("EXCLUSE_AR")), "households": to_int(m.get("SUPLY_HSHLDCO")),
                      "now_households": to_int(m.get("SUPLY_HSHLDCO")), "general": to_int(m.get("GNSPLY_HSHLDCO")), "special": sp,
                      "supply_amount": to_int(m.get("SUPLY_AMOUNT")), "apply_fee": to_int(m.get("SUBSCRPT_REQST_AMOUNT")),
                      "deposit": None, "rent": None})
    return {
        "id": "PVT-" + no, "org": "PVT", "name": d.get("HOUSE_NM") or "", "type": kind, "judge_type": False,
        "youth": any((u["special"]["청년"] or 0) > 0 for u in units), "region": _region(d.get("HSSPLY_ADRES")),
        "posted": to_date(d.get("RCRIT_PBLANC_DE")), "close": b, "status": None,
        "url": d.get("PBLANC_URL"), "url_mobile": d.get("PBLANC_URL"),
        "schedule": [{"complex": None, "apply_start": a, "apply_end": b, "docs_target": None, "winner": w, "rank1": False,
                      "contract_start": to_date(d.get("CNTRCT_CNCLS_BGNDE")), "contract_end": to_date(d.get("CNTRCT_CNCLS_ENDDE"))}] if a or b else [],
        "complexes": [{"name": d.get("HOUSE_NM"), "address": d.get("HSSPLY_ADRES"), "households": to_int(d.get("TOT_SUPLY_HSHLDCO")),
                       "move_in": d.get("MVN_PREARNGE_YM"), "builder": d.get("BSNS_MBY_NM")}],
        "units": units, "rents": [], "terms": None, "files": [], "notice_pdf": None, "home": d.get("HMPG_ADRES"),
        "office": {"place": None, "tel": d.get("MDHS_TELNO")},
    }


def main() -> int:
    now = datetime.now(KST)
    today = now.date()
    since = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    log = [f"공공지원 민간임대 수집 {now:%Y-%m-%d %H:%M}"]
    c = ApplyhomeClient()
    rows, seen = [], set()
    for page in range(1, 20):
        data = c._get(DETAIL, page=page).get("data", [])   # 최신 공고가 앞 (2026-10-21 응답 확인)
        for d in data:
            no = str(d.get("PBLANC_NO") or "")
            if no and no not in seen:
                seen.add(no)
                rows.append(d)
        if len(data) < 100 or all((to_date(d.get("RCRIT_PBLANC_DE")) or "") < since for d in data):
            break
    keep = [d for d in rows if _still_open(d, since, today)]
    log.append(f"[목록] 받은 공고 {len(rows)}건 · 공고일 {since} 이후이고 아직 열려 있는 공고 {len(keep)}건")
    keep = [(d, DETAIL, MODEL, "공공지원 민간임대") for d in keep]
    if feature_on("pvt_rental_urbty"):
        urows, seen_u = [], set()
        for page in range(1, 20):
            try:
                data = c._get(URBTY_DETAIL, page=page).get("data", [])
            except Exception as e:
                log.append(f"[목록·민간임대] 오피스텔·도시형·민간임대 목록 실패 {e.__class__.__name__}")
                break
            for d in data:
                no = str(d.get("PBLANC_NO") or "")
                if no and no not in seen_u:
                    seen_u.add(no)
                    urows.append(d)
            if len(data) < 100 or all((to_date(d.get("RCRIT_PBLANC_DE")) or "") < since for d in data):
                break
        kinds = {}
        for d in urows:
            k = str(d.get("HOUSE_DTL_SECD_NM") or d.get("HOUSE_SECD_NM") or "?")
            kinds[k] = kinds.get(k, 0) + 1
        open_u = [d for d in urows if _still_open(d, since, today)]
        pr = [d for d in open_u if "민간임대" in str(d.get("HOUSE_DTL_SECD_NM") or "")]
        log.append(f"[목록·민간임대] 오피스텔·도시형·민간임대 {len(urows)}건(구분 {kinds}) · 열려 있는 {len(open_u)}건 중 민간임대 {len(pr)}건만 담음(오피스텔·도시형은 분양이라 뺌)")
        if urows:
            log.append(f"[응답 필드] 오피스텔·도시형·민간임대 개요: {', '.join(sorted(urows[0].keys()))}")
        keep += [(d, URBTY_DETAIL, URBTY_MODEL, "민간임대") for d in pr]
    notices = []
    model_keys = set()
    for d, _, model, kind in keep:
        no = str(d.get("PBLANC_NO"))
        try:
            ms = c._get(model, **{"cond[PBLANC_NO::EQ]": no}).get("data", [])
        except Exception as e:
            log.append(f"[공고] PVT-{no} 주택형 실패 {e.__class__.__name__}")
            ms = []
        if kind == "민간임대" and ms and not model_keys:
            model_keys = set(ms[0].keys())
            log.append(f"[응답 필드] 민간임대 주택형: {', '.join(sorted(model_keys))}")   # 금액 칸 이름이 공공지원 민간임대와 다르면 화면은 '청약홈 공고 확인'
        rec = record(d, ms, kind)
        notices.append(rec)
        s = rec["schedule"][0] if rec["schedule"] else {}
        log.append(f"[공고] {rec['id']} {rec['name'][:30]} · {rec['region']} · 접수 {s.get('apply_start')}~{s.get('apply_end')} · 주택형 {len(ms)} · {sum(u['households'] or 0 for u in rec['units'])}세대")
    out = {"updated": now.strftime("%Y-%m-%d %H:%M"), "source": "청약홈 분양정보 API 공공지원 민간임대·민간임대 (한국부동산원)", "count": len(notices),
           "notices": sorted(notices, key=lambda n: n["posted"] or "", reverse=True)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
