"""LH 임대 공고 수집 (2026-10-05 사용자 'LH 임대 목록 + 자격 판정, 지금 청약 판정에는 영향 없게').

기존 청약 수집(pipeline)과 완전히 따로 돈다 — 결과는 docs/lh-rental.json 한 파일, 공고문 글은 evidence/lh/<공고ID>.txt.
이 파일이 실패해도 docs/listings.json·판정에는 아무 영향이 없다. 화면은 스위치 `lh_rental` 이 켜질 때만 이 파일을 읽는다.

원천 (공공데이터포털, 인증키 DATA_GO_KR_KEY — 코드·기록에 적지 않음):
 - 목록  B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1          (UPP_AIS_TP_CD=06 임대주택)
 - 상세  B552555/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1   (단지별 일정·주소·세대수·첨부 공고문)
 - 공급  B552555/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1   (주택형·전용면적·세대수·보증금·월임대료)
필드 이름은 evidence/qa/lh/ 의 실제 응답(2026-10-05 lh-probe)에서 확인한 것만 쓴다.
실행: python -m app.lh_rental (Actions 'LH 임대 수집' lh-rental.yml)"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "lh-rental.json"
TEXT_DIR = ROOT / "evidence" / "lh"
LOG = ROOT / "evidence" / "qa" / "lh-rental-log.txt"
KST = timezone(timedelta(hours=9))
API = "https://apis.data.go.kr/B552555"
LIST = f"{API}/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
DTL = f"{API}/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1"
SPL = f"{API}/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1"
# 자격 판정을 만들 유형 (공공주택 특별법 시행규칙 별표 3·4·5·5의2). 그 밖의 임대(공공임대 분양전환·전세임대 등)는 목록만.
JUDGE_TYPES = ("행복주택", "국민임대", "영구임대", "통합공공임대", "공공임대")   # 공공임대(50년·10년 분양전환 예비입주자)는 2026-10-05 추가
SKIP_TYPES = ("가정어린이집", "상가", "토지", "주거복지동")
LOOKBACK_DAYS = 90
UA = {"User-Agent": "Mozilla/5.0 (cheongyak-bot; +https://github.com/cheongyak/cheongyak.github.io)"}


def _ds(j, name: str) -> list[dict]:
    """응답은 [{dsSch:[...]}, {dsList:[...]}, ...] 또는 dict. 이름이 name 인 목록을 모아 돌려준다."""
    out: list[dict] = []
    for part in (j if isinstance(j, list) else [j]):
        if isinstance(part, dict) and isinstance(part.get(name), list):
            out += [x for x in part[name] if isinstance(x, dict)]
    return out


def _d(s: Optional[str]) -> Optional[str]:
    """'2026.10.13' · '20261013' → '2026-10-13'"""
    if not s:
        return None
    m = re.match(r"(\d{4})\.?(\d{2})\.?(\d{2})", str(s).strip())
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def _num(s) -> Optional[float]:
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def _int(s) -> Optional[int]:
    v = _num(s)
    return int(v) if v is not None else None


def notice_record(row: dict, dtl, spl) -> dict:
    """목록 한 줄 + 상세 + 공급 응답 → 화면용 공고 한 건. API 에 없는 값은 만들지 않는다(None)."""
    sched = []
    for s in _ds(dtl, "dsSplScdl"):
        sched.append({
            "complex": s.get("SBD_LGO_NM") or None,
            "apply_start": _d(s.get("SBSC_ACP_ST_DT")), "apply_end": _d(s.get("SBSC_ACP_CLSG_DT")),
            "apply_time": s.get("ACP_DTTM") or None,
            "docs_target": _d(s.get("PPR_SBM_OPE_ANC_DT")),
            "docs_start": _d(s.get("PPR_ACP_ST_DT")), "docs_end": _d(s.get("PPR_ACP_CLSG_DT")),
            "winner": _d(s.get("PZWR_ANC_DT")),
            "contract_start": _d(s.get("CTRT_ST_DT")), "contract_end": _d(s.get("CTRT_ED_DT")),
        })
    complexes = [{
        "name": c.get("LCC_NT_NM") or None,
        "address": " ".join(x for x in (c.get("LGDN_ADR"), c.get("LGDN_DTL_ADR")) if x) or None,
        "households": _int(c.get("HSH_CNT")),
        "area": c.get("DDO_AR") or None,
        "move_in": c.get("MVIN_XPC_YM") or None,
        "heating": c.get("HTN_FMLA_DESC") or None,
    } for c in _ds(dtl, "dsSbd")]
    units = []
    for u in _ds(spl, "dsList01"):
        dep, rent = u.get("LS_GMY"), u.get("RFE")
        units.append({
            "complex": u.get("SBD_LGO_NM") or None,
            "type": u.get("HTY_NNA") or None,
            "area": _num(u.get("DDO_AR")), "supply_area": _num(u.get("SPL_AR")),
            "households": _int(u.get("HSH_CNT")), "now_households": _int(u.get("NOW_HSH_CNT")),
            "deposit": _int(dep), "rent": _int(rent),            # 원. '공고문 참조'면 None
            "money_note": None if _int(dep) is not None and _int(rent) is not None else (dep if _int(dep) is None else rent),
        })
    files = [{"kind": f.get("SL_PAN_AHFL_DS_CD_NM") or None, "name": f.get("CMN_AHFL_NM") or None, "url": f.get("AHFL_URL") or None}
             for f in _ds(dtl, "dsAhflInfo") if f.get("AHFL_URL", "").startswith("http")]
    etc = next((e.get("ETC_CTS") for e in _ds(dtl, "dsEtcInfo") if e.get("ETC_CTS")), None)
    office = next(({"place": " ".join(x for x in (o.get("CTRT_PLC_ADR"), o.get("CTRT_PLC_DTL_ADR")) if x) or None,
                    "tel": o.get("SIL_OFC_TLNO") or None} for o in _ds(dtl, "dsCtrtPlc")), None)
    return {
        "id": row.get("PAN_ID"),
        "name": row.get("PAN_NM"),
        "type": row.get("AIS_TP_CD_NM"),
        "type_code": row.get("AIS_TP_CD"),
        "judge_type": row.get("AIS_TP_CD_NM") in JUDGE_TYPES,
        "region": row.get("CNP_CD_NM"),
        "posted": _d(row.get("PAN_NT_ST_DT")),
        "close": _d(row.get("CLSG_DT")),
        "status": row.get("PAN_SS"),
        "url": row.get("DTL_URL"),
        "url_mobile": row.get("DTL_URL_MOB"),
        "schedule": sched,
        "complexes": complexes,
        "units": units,
        "files": files,
        "etc": (etc or "")[:4000] or None,
        "office": office,
        "notice_pdf": next((f["url"] for f in files if f["kind"] and "PDF" in f["kind"].upper() and "공고" in f["kind"]), None),
        "notice_text": None,      # evidence/lh/<id>.txt 를 읽었으면 글자 수
        "rents": [],              # app/lh_terms.parse_lh_rents — 공고문 임대조건 표 (보증금 계 = 계약금 + 잔금 검사 통과한 줄만)
        "terms": None,            # app/lh_terms.parse_lh_terms — 계층별 무주택·소득·자산·자동차 기준
        "api": {k: row.get(k) for k in ("CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")},
    }


def fetch_pdf_text(http: httpx.Client, url: str, referer: Optional[str]) -> tuple[Optional[str], str]:
    """LH 첨부 PDF → 글. 기존 notice_pdf 의 읽기 도구(pypdf)를 그대로 쓴다. 실패해도 예외를 밖으로 내지 않는다."""
    from app.notice_pdf import pdf_text
    try:
        r = http.get(url, headers={**UA, **({"Referer": referer} if referer else {})})
    except Exception as e:
        return None, f"받기 실패 {e.__class__.__name__}"
    if r.status_code != 200 or r.content[:4] != b"%PDF":
        return None, f"PDF 아님(HTTP {r.status_code}, {len(r.content)}바이트, {r.headers.get('content-type', '')})"
    try:
        t = pdf_text(r.content)
    except Exception as e:
        return None, f"PDF 해석 실패 {e.__class__.__name__}"
    if len(t) < 500:
        return None, f"글자를 못 읽는 PDF({len(t)}자)"
    return t, f"PDF 읽음 {len(t)}자"


def main() -> int:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    log = [f"LH 임대 수집 {now:%Y-%m-%d %H:%M}"]
    if not key:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(log + ["DATA_GO_KR_KEY 없음 — 건너뜀"]) + "\n", encoding="utf-8")
        return 0
    scrub = lambda s: s.replace(key, "***")
    http = httpx.Client(timeout=httpx.Timeout(40, connect=10), follow_redirects=True, headers=UA)

    def api(url, **params):
        last = ""
        for attempt in range(3):
            try:
                r = http.get(url, params={"serviceKey": key, **params})
                return r.status_code, json.loads(r.text)
            except Exception as e:
                last = scrub(f"{e.__class__.__name__}")
                time.sleep(2 + attempt * 3)
        return 0, {"error": last}

    rows: list[dict] = []
    for page in range(1, 11):
        st, j = api(LIST, PG_SZ=100, PAGE=page, UPP_AIS_TP_CD="06",
                    PAN_ST_DT=(now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d"), PAN_ED_DT=now.strftime("%Y%m%d"))
        got = [x for part in (j if isinstance(j, list) else [j]) if isinstance(part, dict)
               for k, v in part.items() if isinstance(v, list) and k != "dsSch" and not k.endswith("Nm") for x in v if isinstance(x, dict) and x.get("PAN_ID")]
        log.append(f"[목록] {page}쪽 HTTP {st} · {len(got)}건")
        rows += got
        if len(got) < 100:
            break
    if not rows:
        log.append("[경고] 목록이 비어 있음 — 이전 파일을 그대로 둠")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
        return 1

    # 지금 신청할 수 있거나 곧 열리는 공고만 (마감일이 오늘 이후). 같은 공고가 정정되면 PAN_ID 가 같다.
    seen, open_rows = set(), []
    for r in rows:
        if not r.get("PAN_ID") or r["PAN_ID"] in seen:
            continue
        if any(s in (r.get("AIS_TP_CD_NM") or "") for s in SKIP_TYPES):
            continue
        close = _d(r.get("CLSG_DT"))
        if r.get("PAN_SS") == "접수마감" or (close and close < today):
            continue
        seen.add(r["PAN_ID"])
        open_rows.append(r)
    log.append(f"[목록] 전체 {len(rows)}건 · 지금 공고 {len(open_rows)}건")

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    notices = []
    for r in open_rows:
        p = {k: r.get(k) for k in ("PAN_ID", "CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")}
        st1, dtl = api(DTL, **p)
        st2, spl = api(SPL, **p)
        rec = notice_record(r, dtl, spl)
        msg = f"상세 {st1}/공급 {st2}"
        txt_path = TEXT_DIR / f"{rec['id']}.txt"
        if txt_path.exists():
            rec["notice_text"] = len(txt_path.read_text(encoding="utf-8"))
            msg += " · 공고문 저장본"
        elif rec["notice_pdf"]:
            t, m = fetch_pdf_text(http, rec["notice_pdf"], rec["url"])
            msg += f" · 공고문 {m}"
            if t:
                txt_path.write_text(t, encoding="utf-8")
                rec["notice_text"] = len(t)
        else:
            msg += " · 공고문 PDF 첨부 없음(" + ", ".join(f["kind"] or "?" for f in rec["files"][:4]) + ")"
        if rec["judge_type"] and txt_path.exists():
            try:
                from app.lh_terms import parse_lh_terms
                rec["terms"] = parse_lh_terms(txt_path.read_text(encoding="utf-8"), rec["type"], rec["name"] or "", rec["region"])
                g = rec["terms"]["groups"]
                from app.lh_terms import URBAN_2025
                tb = rec["terms"].get("income_table_100") or {}
                if rec["terms"].get("income_basis") == "도시근로자 월평균소득":
                    diff = [f"{k}인 공고문 {v:,} ≠ 앱 {URBAN_2025.get(int(k), 0):,}" for k, v in tb.items() if URBAN_2025.get(int(k)) != v]
                    if diff:
                        log.append(f"[검증·공고문 불일치] {rec['id']} 소득 100% 금액: " + ", ".join(diff))
                if rec["terms"].get("income_basis") == "기준 중위소득":   # 2026 기준 중위소득 고시와 같은지 (숫자가 붙어 칸이 밀리면 여기서 걸린다)
                    from app.lh_terms import MEDIAN_2026, MEDIAN_ADD_2026
                    diff = [f"{k}인 읽은 값 {v:,} ≠ 2026 기준 중위소득 {MEDIAN_2026.get(int(k), 0):,}" for k, v in tb.items() if MEDIAN_2026.get(int(k)) != v]
                    if not tb:
                        diff.append("기준 중위소득 표를 읽지 못함")
                    ap = rec["terms"].get("income_add_per")
                    if ap is not None and ap != MEDIAN_ADD_2026:
                        diff.append(f"8인 초과 1인당 {ap:,} ≠ {MEDIAN_ADD_2026:,}")
                    if diff:
                        log.append(f"[검증·공고문 불일치] {rec['id']} 기준 중위소득 100%: " + ", ".join(diff))
                msg += f" · 자격 계층 {len(g)}" + ("" if g else " (계층을 읽지 못함 — 화면은 공고문 확인)")
            except Exception as e:   # 읽기 실패는 기록만 하고 수집은 계속
                rec["terms"] = None
                msg += f" · 자격 읽기 실패 {e.__class__.__name__}"
        if txt_path.exists():
            try:
                from app.lh_terms import parse_lh_rents
                rec["rents"] = parse_lh_rents(txt_path.read_text(encoding="utf-8"), [u["type"] for u in rec["units"]])
                msg += f" · 임대조건 {len(rec['rents'])}줄"
            except Exception as e:
                rec["rents"] = []
                msg += f" · 임대조건 읽기 실패 {e.__class__.__name__}"
        log.append(f"[공고] {rec['type']} {rec['id']} {rec['name'][:50]} · 단지 {len(rec['complexes'])} · 주택형 {len(rec['units'])} · {msg}")
        notices.append(rec)
        time.sleep(0.3)

    notices.sort(key=lambda n: (n["close"] or "9999", n["id"]))
    data = {"updated": now.strftime("%Y-%m-%d %H:%M"), "source": "LH 청약플러스 임대 공고 (공공데이터포털 한국토지주택공사 분양임대공고 조회)",
            "count": len(notices), "notices": notices}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    log.append("[요약] 유형별 " + ", ".join(f"{k} {v}" for k, v in Counter(n["type"] for n in notices).most_common())
               + f" · 공고문 읽음 {sum(1 for n in notices if n['notice_text'])}/{len(notices)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
