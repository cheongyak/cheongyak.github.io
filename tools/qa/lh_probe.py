"""LH 임대 공고를 받을 수 있는지 점검 (2026-10-05 사용자 '8 LH 임대 범위 넓히기').
LH 청약플러스의 임대(국민임대·행복주택·영구임대·통합공공임대 등) 공고는 청약홈 API 에 없어 지금 수집하지 않는다.
공공데이터포털 '한국토지주택공사_분양임대공고문 조회 서비스'(B552555/lhLeaseNoticeInfo1)와 상세(lhLeaseNoticeDtlInfo1)를 같은 인증키(DATA_GO_KR_KEY)로 불러
응답 코드·건수·필드 이름만 evidence/qa/lh-probe.txt 에 남긴다 (인증키·개인 정보는 남기지 않음). 'SERVICE_KEY_IS_NOT_REGISTERED' 면 공공데이터포털에서 이 서비스 활용신청이 필요하다.
실행: python -m tools.qa.lh_probe (근거 자료 모으기)"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[2] / "evidence" / "qa" / "lh-probe.txt"
NOW = datetime.now(timezone(timedelta(hours=9)))
BASES = ["https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1", "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"]


def main() -> None:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    log = [f"점검 시각: {NOW:%Y-%m-%d %H:%M}"]
    if not key:
        OUT.write_text("\n".join(log + ["DATA_GO_KR_KEY 없음"]) + "\n", encoding="utf-8")
        return
    params = {"serviceKey": key, "PG_SZ": 50, "PAGE": 1, "PAN_ST_DT": (NOW - timedelta(days=60)).strftime("%Y%m%d"), "PAN_ED_DT": NOW.strftime("%Y%m%d"), "UPP_AIS_TP_CD": "06"}
    for base in BASES:
        try:
            r = httpx.get(base, params=params, timeout=40)
            body = r.text.replace(key, "***")
            log.append(f"[목록] {base.split('://')[0]} HTTP {r.status_code} · {len(body)}자 · 앞부분: " + re.sub(r"\s+", " ", body[:300]))
            try:
                j = r.json()
                rows = []
                for part in (j if isinstance(j, list) else [j]):
                    for v in (part.values() if isinstance(part, dict) else []):
                        if isinstance(v, list):
                            rows += [x for x in v if isinstance(x, dict)]
                log.append(f"[목록] 행 {len(rows)}개 · 필드: " + ", ".join(sorted({k for x in rows for k in x})[:60]))
                for x in rows[:15]:
                    log.append("  · " + " | ".join(str(x.get(k, "")) for k in ("AIS_TP_CD_NM", "PAN_NM", "CNP_CD_NM", "PAN_NT_ST_DT", "CLSG_DT", "PAN_SS")))
            except Exception as e:
                log.append(f"[목록] JSON 아님: {e.__class__.__name__}")
            if r.status_code == 200:
                break
        except Exception as e:
            log.append(f"[목록] {base} 실패: {e.__class__.__name__}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
