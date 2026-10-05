"""LH 임대 공고 원천 점검 (2026-10-05 사용자 'LH 임대 목록 + 자격 판정, 지금 청약 판정에는 영향 없게').
공공데이터포털 LH API 를 같은 인증키(DATA_GO_KR_KEY)로 불러 응답을 evidence/qa/lh/ 에 그대로 남긴다(인증키는 지움):
 - 목록  B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1 (분양임대공고문 조회, 2026-10-05 활용신청 승인 확인)
 - 상세  B552555/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1 (공고별 상세: 첨부파일·일정·단지)
 - 공급  B552555/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1 (공고별 공급정보: 주택형·세대수·임대조건)
상세·공급은 서비스가 따로라 'SERVICE_KEY_IS_NOT_REGISTERED' 면 그 서비스 활용신청이 필요하다. 요약은 evidence/qa/lh-probe.txt.
실행: python -m tools.qa.lh_probe (Actions 'LH 임대 원천 점검')"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "lh-probe.txt"
RAW = ROOT / "evidence" / "qa" / "lh"
NOW = datetime.now(timezone(timedelta(hours=9)))
API = "https://apis.data.go.kr/B552555"
LIST = f"{API}/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
DTL = f"{API}/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1"
SPL = f"{API}/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1"
WANT = ("행복주택", "국민임대", "영구임대", "통합공공임대")


def rows_of(j) -> list[dict]:
    out = []
    for part in (j if isinstance(j, list) else [j]):
        if isinstance(part, dict):
            for k, v in part.items():
                if isinstance(v, list) and k != "dsSch":
                    out += [x for x in v if isinstance(x, dict)]
    return out


def main() -> None:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    log = [f"점검 시각: {NOW:%Y-%m-%d %H:%M}"]
    RAW.mkdir(parents=True, exist_ok=True)
    if not key:
        OUT.write_text("\n".join(log + ["DATA_GO_KR_KEY 없음"]) + "\n", encoding="utf-8")
        return
    http = httpx.Client(timeout=40)
    scrub = lambda s: s.replace(key, "***")

    def get(url, **params):
        r = http.get(url, params={"serviceKey": key, **params})
        body = scrub(r.text)
        try:
            return r.status_code, json.loads(body), body
        except Exception:
            return r.status_code, None, body

    allrows = []
    for page in (1, 2, 3):
        st, j, body = get(LIST, PG_SZ=100, PAGE=page, PAN_ST_DT=(NOW - timedelta(days=60)).strftime("%Y%m%d"), PAN_ED_DT=NOW.strftime("%Y%m%d"), UPP_AIS_TP_CD="06")
        rows = rows_of(j) if j is not None else []
        log.append(f"[목록 {page}쪽] HTTP {st} · 행 {len(rows)}" + ("" if j is not None else " · " + re.sub(r"\s+", " ", body[:200])))
        allrows += rows
        if len(rows) < 100:
            break
    (RAW / "list.json").write_text(json.dumps(allrows, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    log.append("[목록] 유형별: " + ", ".join(f"{k} {v}" for k, v in Counter(r.get("AIS_TP_CD_NM") for r in allrows).most_common()))
    log.append("[목록] 상태별: " + ", ".join(f"{k} {v}" for k, v in Counter(r.get("PAN_SS") for r in allrows).most_common()))
    picks, seen = [], set()
    for r in allrows:
        t = r.get("AIS_TP_CD_NM")
        if t in WANT and t not in seen and r.get("PAN_SS") == "공고중":
            seen.add(t)
            picks.append(r)
    for r in picks:
        p = {k: r.get(k) for k in ("PAN_ID", "CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")}
        for nm, url in (("상세", DTL), ("공급", SPL)):
            st, j, body = get(url, **p)
            rows = rows_of(j) if j is not None else []
            (RAW / f"{nm}-{r['AIS_TP_CD_NM']}-{r['PAN_ID']}.json").write_text(body if j is None else json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
            log.append(f"[{nm}] {r['AIS_TP_CD_NM']} {r.get('PAN_NM','')[:40]} · HTTP {st} · 행 {len(rows)}" + ("" if j is not None else " · " + re.sub(r"\s+", " ", body[:200])))
            if rows:
                log.append("    필드: " + ", ".join(sorted({k for x in rows for k in x})[:80]))
    OUT.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
