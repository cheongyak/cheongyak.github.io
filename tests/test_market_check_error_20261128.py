"""2026-11-28: 시세 원자료 대조 도구가 API 오류 응답을 거래 0건으로 읽어 거짓 경보를 낸 일의 재발 방지"""
import pytest
from tools.qa.market_check import rows_of


def test_error_document_raises():
    with pytest.raises(RuntimeError):
        rows_of("<response><header><resultCode>04</resultCode><resultMsg>HTTP 에러</resultMsg></header></response>")
    with pytest.raises(RuntimeError):
        rows_of("<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>22</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")


def test_empty_month_is_ok():
    assert rows_of("<response><header><resultCode>000</resultCode></header><body><items/></body></response>") == []
