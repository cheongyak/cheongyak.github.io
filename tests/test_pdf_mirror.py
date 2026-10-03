"""첨부 서버(static)가 '찾을 수 없음' 글을 주면 청약홈 본 서버(www)에서 같은 공고문을 받는다 (2026-10-03 사용자 제보: 거주지 '공고문에서 읽지 못했어요').
근거: evidence/qa/pdf-fetch-probe.txt — static 은 200·59바이트 HTML, www 는 같은 주소로 PDF."""
import httpx

from app import notice_pdf

PAGE = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000494&pblancNo=2026000494"
Q = "/ai/aia/getAtchmnfl.do?houseManageNo=2026000494&pblancNo=2026000494&atchmnflSeqNo=1988347&atchmnflSn=2"
HTML = f'<dl class="pop_btn_txt mt_10"><dd><a href="https://static.applyhome.co.kr{Q}" class="radius_btn">모집공고문 보기</a></dd></dl>'
NOT_FOUND = b"The requested URL was not found on this server.<br><br><br>"


def _client(seen):
    def handler(req: httpx.Request):
        seen.append(str(req.url))
        if "selectAPTLttotPblancDetail" in str(req.url):
            return httpx.Response(200, text=HTML)
        if req.url.host == "static.applyhome.co.kr":
            return httpx.Response(200, content=NOT_FOUND, headers={"content-type": "text/html"})
        if req.url.host == "www.applyhome.co.kr":
            return httpx.Response(200, content=b"%PDF-1.4 fake", headers={"content-type": "application/octet-stream;charset=UTF-8"})
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_static_not_found_falls_back_to_www(monkeypatch):
    monkeypatch.setattr(notice_pdf, "pdf_text", lambda data: "입주자모집공고일 현재 대구광역시에 거주하는 " * 40)
    monkeypatch.setattr(notice_pdf, "pdf_text_alt", lambda data: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    seen = []
    text, msg, pdf = notice_pdf.fetch_notice_text(PAGE, _client(seen))
    assert text and "PDF 읽음" in msg
    assert pdf == "https://www.applyhome.co.kr" + Q          # 화면의 '공고문' 링크도 실제로 열리는 주소로
    assert any("static.applyhome.co.kr" in u for u in seen)   # 원래 주소를 먼저 시도


def test_mirrors_only_for_static():
    other = "https://apply.lh.or.kr/x.pdf"
    assert notice_pdf._with_mirrors([other]) == [other]
    assert notice_pdf._with_mirrors(["https://static.applyhome.co.kr" + Q]) == ["https://static.applyhome.co.kr" + Q, "https://www.applyhome.co.kr" + Q]
