"""LH 임대: 공고문 PDF 가 글자 없는 그림이면 같은 공고의 공고문 .hwpx 로 읽는다 (2026-10-29 광주두암4 2015122300020967, 운영자 '응 수정해')."""
import httpx

from app.lh_rental import hwpx_notice_text
from tests.test_read_unsupported_20261022 import _hwpx, _p

LONG = "3. 신청자격 입주자 모집공고일(2026.10.27.) 현재 전남광주통합특별시 광산구, 동구, 서구, 남구, 북구에 거주하는 성년자인 무주택세대구성원으로서 " * 6
REC = {"id": "2015122300020967", "url": "https://apply.lh.or.kr/x",
       "files": [{"kind": "공고문(hwp)", "name": "광주두암4영구임대예비입주자표준모집공고문개정반영(2026.10.27).hwpx", "url": "https://apply.lh.or.kr/lhapply/lhFile.do?fileid=69147745"},
                 {"kind": "공고문(PDF)", "name": "광주두암4영구임대주택예비입주자모집(입주자모집공고일2026.10.27).pdf", "url": "https://apply.lh.or.kr/lhapply/lhFile.do?fileid=69147730"}]}


def _client(body: bytes, status: int = 200, seen=None):
    def h(req):
        if seen is not None:
            seen.append((str(req.url), req.headers.get("Referer")))
        return httpx.Response(status, content=body)
    return httpx.Client(transport=httpx.MockTransport(h))


def test_hwpx_fallback_reads_notice_attachment_with_referer():
    seen = []
    t, m = hwpx_notice_text(_client(_hwpx([_p(LONG)]), seen=seen), REC)
    assert t and "전남광주통합특별시" in t and m.startswith("HWPX 읽음")
    assert seen == [("https://apply.lh.or.kr/lhapply/lhFile.do?fileid=69147745", "https://apply.lh.or.kr/x")]   # .hwpx 첨부를, 공고 글을 Referer 로


def test_hwpx_fallback_refuses_non_zip_short_and_missing():
    assert hwpx_notice_text(_client(b"<html>error</html>"), REC)[0] is None
    assert hwpx_notice_text(_client(_hwpx([_p("짧은 글")])), REC)[0] is None
    assert hwpx_notice_text(_client(b"", status=404), REC)[0] is None
    no_hwpx = dict(REC, files=[f for f in REC["files"] if f["name"].endswith(".pdf")])
    assert hwpx_notice_text(_client(_hwpx([_p(LONG)])), no_hwpx) == (None, "공고문 HWPX 첨부 없음")
