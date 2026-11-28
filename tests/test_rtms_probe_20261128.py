"""2026-11-28: 한 쪽 1000건 요청만 오류가 날 때 작은 크기로 바꿔 받는지"""
from app.sources.rtms import RtmsClient

ERR = "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>HTTP_ERROR</errMsg><returnReasonCode>04</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"


def _ok(n):
    items = "".join(f"<item><aptNm>가</aptNm><dealAmount>50,000</dealAmount><excluUseAr>84.9</excluUseAr><dealYear>2026</dealYear><dealMonth>11</dealMonth><dealDay>{i % 28 + 1}</dealDay><floor>5</floor><buildYear>2020</buildYear></item>" for i in range(n))
    return f"<response><header><resultCode>000</resultCode></header><body><items>{items}</items><totalCount>{n}</totalCount></body></response>"


class R:
    def __init__(self, text): self.text, self.status_code, self.headers = text, 200, {}
    def raise_for_status(self): pass


class Http:
    def __init__(self, ok_size, total=250): self.ok, self.total, self.calls = ok_size, total, []
    def get(self, url, params=None):
        self.calls.append((params["numOfRows"], params["pageNo"]))
        if params["numOfRows"] > self.ok:
            return R(ERR)
        left = self.total - params["numOfRows"] * (params["pageNo"] - 1)
        return R(_ok(max(0, min(params["numOfRows"], left))))


def test_probe_keeps_1000_when_fine():
    rt = RtmsClient(service_key="x", client=Http(1000))
    assert "정상" in rt.probe("11110", "202611")[0] and rt.page_size == 1000


def test_probe_falls_back_and_pages_with_smaller_size():
    h = Http(100)
    rt = RtmsClient(service_key="x", client=h)
    out = rt.probe("11110", "202611")
    assert "실패" in out[0] and "정상" in out[1] and rt.page_size == 100
    rows = rt.fetch("trade", "11110", "202611")
    assert len(rows) == 250 and h.calls[-3:] == [(100, 1), (100, 2), (100, 3)]
