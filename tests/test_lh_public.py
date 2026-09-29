"""국민주택(공공분양)·신혼희망타운 납입 인정 횟수 — 실제 공고문 8건으로 검증 (기능: public_deposit)."""
import json
import pathlib

import httpx

from app import lh, notice_pdf, pipeline
from app.models import Listing

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
PUBLIC = ["2026000414", "2026000416", "2026000409", "2026000438", "2026000437", "2026820008", "2026820011", "2026820009"]


def test_golden_public_deposit_from_real_notices():
    """공고문 원문 8건(공공분양 5 · 신혼희망타운 3)에서 읽은 1순위 가입기간·납입 횟수가 정답과 같다."""
    for no in PUBLIC:
        text = (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")
        got = notice_pdf.parse_notice(text)
        want = GOLD[no]["fields"]
        assert got.get("deposit_count") == want["deposit_count"], no
        assert got.get("account_months") == want["account_months"], no


def test_private_notice_has_no_deposit_count():
    """민영주택 공고문(광명·숭의)에는 납입 횟수 기준을 만들지 않는다 (특별공급 문장에 속지 않기)."""
    for no in ("2026000453", "2026000448"):
        text = (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")
        assert "deposit_count" not in notice_pdf.parse_notice(text), no


def test_lh_pick_notice_from_real_list():
    html = (ROOT / "evidence" / "pages" / "lh-list-1027.html").read_text(encoding="utf-8")
    rows = lh._ROW.findall(html)
    p = lh.pick_notice("인천계양지구 A6블록 공공분양주택(본청약)", rows)
    assert p and "인천계양 A6블록 공공분양주택" in p[4] and "정정" in p[4]          # 정정공고 우선
    assert lh.pick_notice("인천계양지구 A9블록 공공분양주택", [r for r in rows if "A6" in r[4]]) is None  # 다른 블록은 안 고름
    fake = [("1", "03", "06", "09", "양주회천 A25BL 영구임대주택 추가입주자 모집 공고")]
    assert lh.pick_notice("양주회천지구 A25블록", fake) is None                      # 임대 공고는 안 고름


def test_lh_pick_pdf_skips_pamphlet():
    files = [("68663146", "시흥하중A-4블록신혼희망타운(공공분양)잔여세대입주자모집공고문.hwpx"),
             ("68663278", "시흥하중A-4블록신혼희망타운(공공분양)팸플릿.pdf"),
             ("68663246", "시흥하중A-4블록신혼희망타운(공공분양)잔여세대입주자모집공고문.pdf")]
    assert lh.pick_pdf(files)[0] == "68663246"


def test_fetch_text_falls_back_to_lh(monkeypatch):
    monkeypatch.setattr(pipeline.notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "PDF 링크 못 찾음 (페이지 10000자)", None))
    monkeypatch.setattr(pipeline, "feature_on", lambda name: True)
    body = "1순위 공고문 " * 200

    def h(req):
        u = str(req.url)
        if "selectWrtancList" in u:
            return httpx.Response(200, text='<a href="javascript:" data-id1="0000061174" data-id2="02" data-id3="05" data-id4="05" class="wrtancInfoBtn"> <span>[정정공고]인천계양 A6블록 공공분양주택 입주자모집공고</span></a>')
        if "selectWrtancInfo" in u:
            return httpx.Response(200, text="<a href=\"javascript:fileDownLoad('68595376')\">(정정)인천계양A6블록입주자모집공고문(0914).pdf</a>")
        return httpx.Response(200, content=b"%PDF-fake")

    monkeypatch.setattr(pipeline.notice_pdf, "pdf_text", lambda data: body)
    L0 = Listing(id="2026000414-059.0000A", name="인천계양지구 A6블록 공공분양주택(본청약)", address="인천", region="인천", kind="k",
                 unit="59A", area=59, price=5, category="general", house_dtl="국민")
    text, msg, url = pipeline._fetch_text("https://applyhome/x", L0, httpx.Client(transport=httpx.MockTransport(h)))
    assert text == body and url.endswith("fileid=68595376") and "LH청약플러스" in msg
