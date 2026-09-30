"""국토교통부 실거래가 API (공공데이터포털, apis.data.go.kr).

매매 · 분양권전매 · 전월세 세 가지를 같은 방식(LAWD_CD + DEAL_YMD)으로 부르고 XML 로 받는다.
금액은 만 원 단위 문자열("123,000").
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

BASE = "https://apis.data.go.kr/1613000"
ENDPOINTS = {
    "trade": "/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",         # 아파트 매매 실거래가 자료
    "presale": "/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade",     # 아파트 분양권·입주권 전매
    "rent": "/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",            # 아파트 전월세
}


class RtmsError(RuntimeError):
    pass


def safe_msg(e: BaseException) -> str:
    """기록용 오류 문장. 요청 주소에 들어 있는 인증키(serviceKey)는 지운다"""
    m = f"{type(e).__name__}: {e}"
    m = re.sub(r"(serviceKey=)[^&\s']+", r"\1***", m)
    return m[:200]


def _num(v) -> Optional[float]:
    if v in (None, ""):
        return None
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    code = root.findtext(".//resultCode")
    if code not in (None, "00", "000"):
        raise RtmsError(f"실거래가 API 오류 {code}: {root.findtext('.//resultMsg')}")
    rows = []
    for it in root.iter("item"):
        r = {c.tag: (c.text or "").strip() for c in it}
        if r.get("cdealType", "").upper() == "O":   # 해제된 거래 제외
            continue
        rows.append({
            "apt": r.get("aptNm", ""),
            "umd": r.get("umdNm", ""),                      # 법정동 이름 (네이버 부동산에서 같은 이름 다른 단지와 구분하는 데 씀)
            "area": _num(r.get("excluUseAr")),
            "amount": _num(r.get("dealAmount")),            # 매매·분양권 (만 원)
            "deposit": _num(r.get("deposit")),              # 전월세 보증금 (만 원)
            "monthly": _num(r.get("monthlyRent")) or 0,
            "floor": _num(r.get("floor")),
            "dong": r.get("aptDong", ""),                   # 동 (매매 자료에만 있고 비어 있을 수 있음. 호수는 국토부가 공개하지 않음)
            "build_year": _num(r.get("buildYear")),
            "date": f"{r.get('dealYear','')}-{str(r.get('dealMonth','')).zfill(2)}-{str(r.get('dealDay','')).zfill(2)}",
            "kind": r.get("ownershipGbn", ""),              # 분양권 / 입주권
            "deal_type": r.get("dealingGbn", ""),           # 중개거래 / 직거래
        })
    return rows


class RtmsClient:
    def __init__(self, service_key: Optional[str] = None, client: Optional[httpx.Client] = None):
        self.key = service_key or os.environ.get("DATA_GO_KR_KEY")
        if not self.key:
            raise RtmsError("환경변수 DATA_GO_KR_KEY 가 없어요.")
        self.http = client or httpx.Client(timeout=httpx.Timeout(15, connect=10))
        self._cache: dict[tuple, list[dict]] = {}
        self.frozen = False          # True 면 새로 요청하지 않는다 (시간 제한을 넘긴 뒤)
        self.stats = {"requests": 0, "failed": 0}

    def prefetch(self, keys: list[tuple], budget_sec: float, workers: int = 8) -> dict:
        """(kind, lawd, ym) 목록을 동시에 받아 캐시에 넣는다. 시간 제한을 넘기면 남은 것은 포기한다."""
        import time
        from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
        start, todo = time.monotonic(), [k for k in dict.fromkeys(keys) if k not in self._cache]
        done_n = fail_n = 0
        errors: dict[str, int] = {}
        ex = ThreadPoolExecutor(max_workers=workers)
        futs = {ex.submit(self.fetch, *k): k for k in todo}
        pending = set(futs)
        while pending:
            left = budget_sec - (time.monotonic() - start)
            if left <= 0:
                break
            done, pending = wait(pending, timeout=left, return_when=FIRST_COMPLETED)
            for f in done:
                if f.exception():
                    fail_n += 1
                    k = safe_msg(f.exception())
                    errors[k] = errors.get(k, 0) + 1
                else:
                    done_n += 1
        for f in pending:
            f.cancel()
        ex.shutdown(wait=False, cancel_futures=True)
        self.frozen = True
        return {"total": len(todo), "done": done_n, "failed": fail_n, "skipped": len(pending),
                "seconds": round(time.monotonic() - start, 1),
                "errors": sorted(errors.items(), key=lambda x: -x[1])[:5]}

    def fetch(self, kind: str, lawd: str, ym: str) -> list[dict]:
        """kind: trade|presale|rent, lawd: 5자리, ym: YYYYMM"""
        key = (kind, lawd, ym)
        if key in self._cache:
            return self._cache[key]
        if self.frozen:
            raise RtmsError("시간 제한으로 이번 실행에서는 조회하지 못했어요")
        self.stats["requests"] += 1
        rows: list[dict] = []
        for page in range(1, 20):
            batch = self._get_page(kind, lawd, ym, page)
            rows.extend(batch)
            if len(batch) < 1000:
                break
        self._cache[key] = rows
        return rows

    def _get_page(self, kind: str, lawd: str, ym: str, page: int, tries: int = 3) -> list[dict]:
        """한 쪽 받기. 연결 오류·5xx·429 와 XML 이 아닌 응답(게이트웨이 오류 문서)은 잠깐 쉬었다 다시 시도한다"""
        import time
        last: Optional[BaseException] = None
        for i in range(tries):
            try:
                r = self.http.get(BASE + ENDPOINTS[kind], params={
                    "serviceKey": self.key, "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": page})
                if r.status_code in (401, 403):
                    raise RtmsError(f"{kind} API 권한 없음({r.status_code}). 공공데이터포털에서 이 API 활용신청·승인 상태를 확인하세요.")
                if r.status_code == 429 or r.status_code >= 500:
                    raise RtmsError(f"{kind} API 응답 {r.status_code}")
                r.raise_for_status()
                try:
                    return parse_items(r.text)
                except ET.ParseError:
                    raise RtmsError(f"{kind} API 가 XML 이 아닌 응답을 보냄: {r.text[:80]!r}")
            except RtmsError as e:
                if "권한 없음" in str(e) or "API 오류" in str(e) and "LIMITED" in str(e):
                    raise
                last = e
            except httpx.HTTPError as e:
                last = e
            time.sleep(1.5 * (i + 1))
        raise last if last else RtmsError("알 수 없는 오류")

    def recent(self, kind: str, lawd: str, months: list[str]) -> list[dict]:
        out: list[dict] = []
        for ym in months:
            out.extend(self.fetch(kind, lawd, ym))
        return out
