"""마이홈포털 공공주택 모집공고 API 점검 (2026-10-21 GH 임대 추가 — GH 청약센터는 Actions 서버에서 접속이 안 돼, 여러 공사 공고를 모으는 국토부 API 를 본다).
API: 국토교통부_마이홈포털 공공주택 모집공고 조회 서비스 (data.go.kr 15108420, 자동 승인 — 같은 인증키로 활용신청이 돼 있어야 함)
주소 https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList — 응답(공급기관·유형·지역·일정 필드)을 값까지 evidence/qa/myhome-probe.json 에. 인증키는 남기지 않는다.
실행: python -m tools.qa.myhome_probe (DATA_GO_KR_KEY 필요)"""
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
URL = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"


def main():
    key = os.environ.get("DATA_GO_KR_KEY", "")
    out = {}
    with httpx.Client(timeout=30) as c:
        for label, params in (("기본", {"pageNo": 1, "numOfRows": 100}), ("기본 JSON", {"pageNo": 1, "numOfRows": 100, "_type": "json"}),
                              ("경기", {"pageNo": 1, "numOfRows": 100, "brtcCode": "41"})):
            try:
                r = c.get(URL, params={"serviceKey": key, **params})
                body = r.text
                out[label] = {"status": r.status_code, "type": r.headers.get("content-type"), "body": body[:60000]}
                print(label, r.status_code, r.headers.get("content-type"), body[:300].replace(key, "***") if key else body[:300])
            except Exception as e:
                out[label] = {"error": f"{e.__class__.__name__} {e}"}
                print(label, "실패", e.__class__.__name__, e)
        # 2026-10-22: API 키가 아직 등록 안 됨(403) — 키 없이 마이홈포털 화면이 목록을 주는지 (지방 공사 임대 공고 대안 경로 근거)
        for label, url in (("화면", "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcView.do"),):
            try:
                r = c.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
                t = r.text
                import re as _re
                out[label] = {"status": r.status_code, "type": r.headers.get("content-type"), "len": len(t),
                              "ajax": sorted(set(_re.findall(r"[\w/]*select\w*List\w*\.do", t)))[:20], "forms": _re.findall(r"<form[^>]*>", t)[:5],
                              "agencies": sorted(set(_re.findall(r"(인천도시공사|부산도시공사|대구도시개발공사|광주광역시도시공사|대전도시공사|울산도시공사|경기주택도시공사|경북개발공사|경남개발공사|전북개발공사|전남개발공사|충북개발공사|충남개발공사|강원개발공사|제주특별자치도개발공사|세종도시교통공사|SH|LH)", t))),
                              "body": t[:30000]}
                print(label, r.status_code, len(t), out[label]["ajax"][:5])
            except Exception as e:
                out[label] = {"error": f"{e.__class__.__name__} {e}"}
                print(label, "실패", e.__class__.__name__)
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if key:
        s = s.replace(key, "***")
    (ROOT / "evidence/qa/myhome-probe.json").write_text(s + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
