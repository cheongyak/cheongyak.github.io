"""2026-11-28: 실거래가 API 가 관문 오류 문서를 보냈는데 '거래 0건'으로 읽혀 시세가 전부 '확인 부족'이 된 사고의 재발 방지"""
import pytest
from app.sources.rtms import RtmsClient, RtmsError, parse_page

GATEWAY = ("<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>"
           "<returnAuthMsg>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR</returnAuthMsg>"
           "<returnReasonCode>22</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
EMPTY_OK = ("<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
            "<body><items/><numOfRows>1000</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount></body></response>")


def test_gateway_error_is_not_zero_trades():
    with pytest.raises(RtmsError) as e:
        parse_page(GATEWAY)
    assert "22" in str(e.value) and "EXCEEDS" in str(e.value)


def test_unknown_document_is_not_zero_trades():
    with pytest.raises(RtmsError):
        parse_page("<html><body>점검 중</body></html>".replace("body", "div"))


def test_real_empty_month_is_still_ok():
    assert parse_page(EMPTY_OK) == ([], 0)


def test_all_empty_marks_failed():
    rt = RtmsClient(service_key="x")
    for i in range(30):
        rt._cache[("trade", f"{11000 + i}", "202611")] = []
    assert rt.all_empty()
    rt.mark_failed("실패")
    with pytest.raises(RtmsError):
        rt.fetch("trade", "11000", "202611")
    rt2 = RtmsClient(service_key="x")
    for i in range(30):
        rt2._cache[("trade", f"{11000 + i}", "202611")] = []
    rt2._cache[("rent", "11000", "202611")] = [{"a": 1}]
    assert not rt2.all_empty()
    rt3 = RtmsClient(service_key="x")   # 응답이 몇 건뿐이면(한 지역) 거래 0건이 실제일 수 있다
    rt3._cache[("trade", "11000", "202611")] = []
    assert not rt3.all_empty()
