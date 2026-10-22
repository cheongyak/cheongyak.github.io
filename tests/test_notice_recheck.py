"""정정 공고·첨부 교체 다시 읽기 (기능 notice_recheck, 2026-10-22 '아직 남은 것' — 정정 공고 처리 점검).
보관 기록(PARSER_VERSION 같음)이 있으면 공고문을 다시 받지 않아, 첨부가 바뀐 공고 4건(2026000463·498·507·2026930033)은
읽기 규칙 버전이 우연히 올라갈 때만 새 파일로 읽혔다."""
import httpx

from app import notice_pdf, pipeline
from tests.test_notice_and_notify import L

OLD = "https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do?houseManageNo=2026000463&pblancNo=2026000463&atchmnflSeqNo=1978209&atchmnflSn=5"
PAGE = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000463"
NEW = "https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do?houseManageNo=2026000463&pblancNo=2026000463&atchmnflSeqNo=1978209&atchmnflSn=6"


def _client(links):
    html = "".join(f'<a href="{u}">모집공고문.pdf</a>' for u in links)
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html)))


def test_att_key_ignores_url_shape():
    assert pipeline._att_key(OLD) == ("2026000463", "1978209", "5")
    assert pipeline._att_key(OLD.replace("static.applyhome", "www.applyhome")) == pipeline._att_key(OLD)
    assert pipeline._att_key("https://x/p.pdf") is None and pipeline._att_key(None) is None


def test_recheck_finds_replaced_attachment_only():
    assert pipeline.recheck_attachments({PAGE: OLD}, _client([OLD])) == {}                  # 같은 파일 → 다시 안 읽음
    assert pipeline.recheck_attachments({PAGE: OLD}, _client([NEW])) == {PAGE: (OLD, NEW)}  # 순번 5 → 6 (2026000463 실제)
    assert pipeline.recheck_attachments({PAGE: OLD}, _client([NEW, OLD])) == {}             # 옛 파일도 아직 올라 있으면 그대로
    assert pipeline.recheck_attachments({PAGE: "https://x/p.pdf"}, _client([NEW])) == {}    # 청약홈 첨부가 아닌 기록은 건드리지 않음
    down = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert pipeline.recheck_attachments({PAGE: OLD}, down) == {}                               # 화면을 못 받으면 지난 값 유지


def test_apply_notice_rereads_corrected_notice_and_logs_changes(monkeypatch):
    calls = []
    monkeypatch.setattr(notice_pdf, "fetch_notice_text",
                        lambda url, client=None: calls.append(url) or ("재당첨 제한 5년 적용 1순위 : 입주자저축에 가입하여 가입기간이 12개월이 경과하고", "PDF 읽음", NEW))
    x = L()
    nid = x.id.split("-")[0]
    cache = {nid: {"found": {"rewin_years": 10, "account_months": 24}, "notice_pdf": OLD, "v": pipeline.PARSER_VERSION}}
    log = []
    pipeline.apply_notice([x], log, client=_client([NEW]), cache=cache)
    assert len(calls) == 1 and cache[nid]["notice_pdf"] == NEW and cache[nid]["found"]["account_months"] == 12
    assert ("재당첨 제한", "5년") in x.limits
    assert any("[공고문·정정]" in l and "첨부가 바뀌어" in l for l in log)
    assert any("[공고문·정정]" in l and "account_months" in l and "rewin_years" in l for l in log)
    assert any(l.startswith("[공고문·정정 확인]") and "바뀜 1건" in l for l in log)   # 매 수집 확인했다는 줄 (바뀐 게 없어도 남음)


def test_apply_notice_keeps_cache_when_attachment_same(monkeypatch):
    calls = []
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: calls.append(url) or (None, "x", None))
    x = L()
    nid = x.id.split("-")[0]
    cache = {nid: {"found": {"rewin_years": 10}, "notice_pdf": OLD, "v": pipeline.PARSER_VERSION}}
    pipeline.apply_notice([x], [], client=_client([OLD]), cache=cache)
    assert calls == [] and ("재당첨 제한", "10년") in x.limits
