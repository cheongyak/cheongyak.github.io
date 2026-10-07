"""실거래가 쪽 넘기기 (2026-10-07 '최근 자동 검증에서 공고문과 다른 값' — 시세 원자료 대조 4건 불일치).
원인: 한 쪽(1,000건)에 해제 거래가 섞이면 해제를 뺀 건수(<1,000)로 마지막 쪽이라 보고 다음 쪽을 받지 않았다.
남양주(41360) 매매처럼 한 달 1,000건이 넘는 지역에서 몇~십여 건이 빠져 시세·근거 거래 수가 원자료와 달랐다 (evidence/qa/market-check.json)."""
import httpx

from app.sources.rtms import RtmsClient


def _xml(n, cancel=0, start=0):
    items = "".join(f"<item><aptNm>A{start + i}</aptNm><excluUseAr>84.9</excluUseAr><dealAmount>50,000</dealAmount><dealYear>2026</dealYear>"
                    f"<dealMonth>9</dealMonth><dealDay>1</dealDay><buildYear>2020</buildYear><cdealType>{'O' if i < cancel else ''}</cdealType></item>"
                    for i in range(n))
    return f"<response><header><resultCode>000</resultCode></header><body><items>{items}</items></body></response>"


def test_full_page_with_cancels_still_reads_next_page():
    pages = {1: _xml(1000, cancel=7), 2: _xml(12, start=1000)}
    seen = []

    def handler(req):
        p = int(req.url.params["pageNo"]); seen.append(p)
        return httpx.Response(200, text=pages.get(p, _xml(0)))

    rt = RtmsClient(service_key="test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    rows = rt.fetch("trade", "41360", "202609")
    assert seen == [1, 2] and len(rows) == 993 + 12


def test_short_page_stops():
    seen = []

    def handler(req):
        seen.append(int(req.url.params["pageNo"]))
        return httpx.Response(200, text=_xml(999))

    rt = RtmsClient(service_key="test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(rt.fetch("trade", "41360", "202609")) == 999 and seen == [1]
