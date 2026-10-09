"""공고문 추출과 알림 메시지."""
from datetime import date

import httpx

from app import notice_pdf, notify
from app.models import Listing
from app.pipeline import apply_notice

# 강변역 센트럴 아이파크 불법행위재공급 공고문(2026.09.23)에서 판정에 쓰이는 부분 발췌
GANGBYEON_TEXT = """
주택유형 규제지역여부 거주요건 재당첨제한
민영 투기과열지구/청약과열지역 서울특별시 거주자 10년
전매제한 거주의무기간 분양가상한제 택지유형
최초 당첨자발표일(2024.06.19.)로부터
3년간 적용 없음 미적용 민간택지
■ 본 입주자모집공고의 일반공급은 해당 주택건설지역 거주자 중 무주택세대주(무주택세대의 세대주)를 대상으로 추첨의 방법으로 공급합니다.
- "무주택세대구성원"이란, 세대원 전원이 주택을 소유하고 있지 않은 세대의 구성원을 말하며
■ 본 주택은 수도권 투기과열지구 및 청약과열지역의 민간택지에서 공급하는 분양가상한제 미적용 민영주택으로
■ 입주지정기간 : 2026년 9월 7일~2026년 11월 30일(입주지정기간 내 잔금 납부 시 즉시 입주 가능)
대상자 ■ 입주자모집공고일 현재 서울특별시에 거주하는 무주택세대의 세대주
84C 101동 402호 유상 발코니확장 발코니 확장 위치(거실+주방+침실2) 21,780,000
2,178,000 19,602,000 무상 현관 일반형 수납장 기본형(일반 현관 신발 수납장) -
"""

MEMBER_TEXT = """
■ 입주자모집공고일 현재 서울특별시에 거주하는 무주택세대구성원 (청약통장 가입여부 무관)
■ 본 주택은 분양가상한제 적용 주택으로 3년의 거주의무기간이 적용됩니다.
"""


def test_parse_gangbyeon():
    f = notice_pdf.parse_notice(GANGBYEON_TEXT)
    assert f["need_head"] is True
    assert f["price_cap"] is False and f["residence_duty"] == 0
    assert f["balance"] == "2026-11-30"
    assert f["ext"] == 0.2178


def test_parse_member_and_duty():
    f = notice_pdf.parse_notice(MEMBER_TEXT)
    assert f["need_head"] is False
    assert f["price_cap"] is True and f["residence_duty"] == 3


def test_find_pdf_links():
    html = '''<a href="/ai/aia/getAtchmnfl.do?fileId=123">모집공고문</a>
              <button onclick="fn_download('https://static.applyhome.co.kr/files/notice.pdf')">PDF</button>'''
    links = notice_pdf.find_pdf_links(html, "https://www.applyhome.co.kr/ai/aia/view.do")
    assert "https://www.applyhome.co.kr/ai/aia/getAtchmnfl.do?fileId=123" in links
    assert "https://static.applyhome.co.kr/files/notice.pdf" in links


def L(**kw):
    base = dict(id="2026930040-084.9811C", name="강변역 센트럴 아이파크", address="서울특별시 광진구", region="서울",
                sigungu="광진구", kind="무순위", category="remainder", unit="84C", price=12.2202, mkt_low=20, mkt_base=22,
                apply="2026-10-06", url="https://www.applyhome.co.kr/x")
    base.update(kw)
    return Listing(**base)


def test_apply_notice_updates_listing(monkeypatch):
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (GANGBYEON_TEXT * 3, "PDF 읽음", "https://static.applyhome.co.kr/x.pdf"))
    x = L(need_head=False)
    log = []
    apply_notice([x], log)
    assert x.need_head and x.balance == "2026-11-30" and x.ext == 0.2178
    assert ("실거주 의무", "없음") in x.limits and any("PDF 읽음" in l for l in log)
    assert x.notice_pdf.endswith("x.pdf") and "잔금일" in x.from_notice and "세대주 요건" in x.from_notice
    assert x.limits[0] == ("재당첨 제한", "10년") and "재당첨 제한" in x.from_notice


def test_alert_new_and_due():
    """알림 이벤트(웹 푸시): 새 공고·내일 접수 시작·마감 (예전 ntfy 알림 테스트를 옮김)."""
    from app import webpush
    cfg = {"notify_grades": ["lotto", "consider"], "remind_days_before": 1}
    lotto = L()
    ev, _ = webpush.build_events([lotto], previous_ids=set(), today=date(2026, 10, 5), cfg=cfg)
    assert {e["kind"] for e in ev} == {"new", "start"} and all(e["good"] for e in ev)
    assert not [e for e in webpush.build_events([lotto], {lotto.id}, date(2026, 9, 29), cfg)[0] if e["kind"] == "new"]
    assert not [e for e in webpush.build_events([lotto], None, date(2026, 9, 29), cfg)[0] if e["kind"] == "new"]
    x = L(apply="2026-09-29", apply_end="2026-10-02")
    ev, _ = webpush.build_events([x], {x.id}, date(2026, 10, 1), cfg)
    assert [e["kind"] for e in ev] == ["end"]


def test_duty_ignores_unrelated_years():
    t = "재당첨제한 10년 전매제한 거주의무기간 분양가상한제 적용 ... 거주의무기간은 3년입니다"
    assert notice_pdf.parse_notice(t).get("residence_duty") == 3
    t2 = "거주의무기간 10년 ... 분양가상한제 미적용"
    assert notice_pdf.parse_notice(t2).get("residence_duty") == 0


def test_newlywed_only():
    from app.engine import eligibility
    from app.models import Profile
    x = L(target="신혼부부", need_head=False)
    e = eligibility(x, Profile(seoul=True, household="parents", parents60=True, parentsOwn=True, married=False))
    assert not e["ok"] and "신혼부부" in e["reason"]


def test_rewin_from_notice():
    assert notice_pdf.parse_notice(GANGBYEON_TEXT)["rewin_years"] == 10
    assert notice_pdf.parse_notice("본 주택은 재당첨제한을 적용받지 않으며")["rewin_years"] == 0


def test_golden_gangbyeon_parse():
    """사람이 모집공고문 원문으로 확인한 정답과 공고문 추출 결과가 같은지."""
    import json, pathlib
    gold = json.loads((pathlib.Path(__file__).parent / "golden" / "notices.json").read_text(encoding="utf-8"))["2026930040"]["fields"]
    f = notice_pdf.parse_notice(GANGBYEON_TEXT)
    for k in ("need_head", "price_cap", "residence_duty", "balance", "ext", "rewin_years"):
        assert f[k] == gold[k], k


def test_validate_flags_and_golden(monkeypatch):
    from datetime import date as d
    from app import validate
    x = L(notice="2026-10-10", apply="2026-10-06", sido="서울", mkt_count=1)
    checks = validate.listing_checks(x, d(2026, 9, 29))
    assert any("날짜 순서" in c for c in checks) and any("근거 거래가 1건" in c for c in checks)
    good = L(id="2026930040-084.9811C", price=12.2202, notice="2026-09-23", apply="2026-10-06", winner="2026-10-12",
             contract="2026-10-23", balance="2026-11-30", ext=0.2178, need_head=True, price_cap=False, residence_duty=0,
             sido="서울", district="광진구", limits=[("재당첨 제한", "10년")],
             residence={"area": {"name": "서울특별시", "sido": "서울"}, "months": 0, "since": None, "others": [], "equal": True}, mc_quota=None)
    assert validate.golden_mismatches([good]) == []
    bad = good.model_copy(update={"limits": [("재당첨 제한", "5년")], "balance": "2026-12-01"})
    mm = validate.golden_mismatches([bad])
    assert any("rewin_years" in m for m in mm) and any("balance" in m for m in mm)


def test_snippets():
    sn = notice_pdf.snippets("앞 문장입니다. 당첨자는 재당첨 제한 규정을 적용받습니다. 뒤", "재당첨")
    assert sn and "재당첨 제한 규정" in sn[0]


def test_rewin_scrambled_pdf_text():
    """충정로역자이르네 공고문에서 실제로 뽑힌 뒤섞인 문장 (2026-09-29 실행 기록)."""
    t1 = "( ) 1660-1245 구분 내용 재당첨제한 년 적용10 본 입주자모집공고의 당첨자로 선정 시"
    t2 = "「 」 당첨자발표일로부터 년간 재당첨 10 제한을 적용받습니다 계약의사가 없는"
    assert notice_pdf.parse_notice(t1)["rewin_years"] == 10
    assert notice_pdf.parse_notice(t2)["rewin_years"] == 10


def test_apply_notice_keeps_previous_when_download_fails(monkeypatch):
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "PDF 받기 실패(ReadTimeout)", None))
    x = L(need_head=False, id="2026939999-084.9811C")   # 원문 사본(evidence/notices)이 없는 공고 — 사본이 있으면 사본으로 읽는다(아래 테스트)
    prev = {x.id: {"from_notice": ["세대주 요건", "잔금일", "발코니 확장비", "재당첨 제한", "분양가상한제", "실거주 의무"],
                   "need_head": True, "price_cap": False, "residence_duty": 0, "balance": "2026-11-30", "ext": 0.2178,
                   "limits": [["재당첨 제한", "10년"], ["실거주 의무", "없음"]], "notice_pdf": "https://static.applyhome.co.kr/x.pdf"}}
    log = []
    apply_notice([x], log, previous=prev)
    assert x.need_head and x.balance == "2026-11-30" and x.ext == 0.2178 and x.limits[0] == ("재당첨 제한", "10년")
    assert "재당첨 제한" in x.from_notice and x.notice_pdf.endswith("x.pdf")
    assert any("지난 실행" in l for l in log)


def test_parse_account_months_real_sentences():
    """2026-09-30 실제 공고문 문장들 (docs/rules-evidence.txt)."""
    from app.notice_pdf import parse_notice
    cases = {
        "※ 1순위 : 입주자저축에 가입하여 가입기간이 24개월이 경과하고 지역별·면적별 예치금액 이상 납입한 분": 24,   # 광명
        "※ 1순위 : 입주자저축에 가입하여 가입 기간이 6개월이 경과하고 지역별·면적별 예치금액 이상 납입한 분": 6,     # 삼천
        "※ 1순위 : 입주자저축에 가입한 후 12개월이 경과하고 지역별·면적별 예치금액 이상 납입한 분": 12,              # 화서역
        "순위 1 :※ 입주자저축에 가입하여 가입기간이 개월6 이 경과하고 지역별 면적별 · 예치금액 이상 납입한 분": 6,   # 더샵 시에르네 (뒤섞임)
    }
    for text, want in cases.items():
        assert parse_notice(text).get("account_months") == want, text
    assert "account_months" not in parse_notice("청약통장 가입기간 6개월 경과(지역별·면적별 예치금액 이상)한 분")  # 기관추천 특공 문장은 1순위 기준이 아님


def test_apply_notice_uses_cache_when_listing_was_missing_last_run(monkeypatch):
    """직전 실행에서 공고가 빠졌다 돌아왔고 이번 PDF 도 실패 → 보관 기록으로 되살린다 (2026-09-30 강변역)."""
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "PDF 받기 실패(형식 아님)", None))
    x = L(need_head=False)
    nid = x.id.split("-")[0]
    cache = {nid: {"found": {"need_head": True, "balance": "2026-11-30", "ext": 0.2178, "rewin_years": 10}, "notice_pdf": "https://x/y.pdf"}}
    log = []
    apply_notice([x], log, previous={}, cache=cache)
    assert x.need_head and x.balance == "2026-11-30" and x.ext == 0.2178 and ("재당첨 제한", "10년") in x.limits
    assert any("보관" in l for l in log)


def test_apply_notice_saves_to_cache(monkeypatch):
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: ("재당첨 제한 10년 적용 1순위 : 입주자저축에 가입하여 가입기간이 24개월이 경과하고", "PDF 읽음", "https://x/p.pdf"))
    x = L()
    cache = {}
    apply_notice([x], [], cache=cache)
    assert cache[x.id.split("-")[0]]["found"]["account_months"] == 24


def test_apply_notice_skips_already_read_notice(monkeypatch):
    """같은 읽기 규칙으로 이미 읽은 공고문은 다시 받지 않는다 (2026-09-30 공고문 56건이 시간 제한 300초를 넘김)."""
    from app import pipeline
    calls = []
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: calls.append(url) or (None, "x", None))
    x = L()
    nid = x.id.split("-")[0]
    cache = {nid: {"found": {"need_head": True, "rewin_years": 10}, "notice_pdf": "https://x/p.pdf", "v": pipeline.PARSER_VERSION}}
    apply_notice([x], [], cache=cache)
    assert calls == [] and x.need_head and ("재당첨 제한", "10년") in x.limits and x.notice_pdf == "https://x/p.pdf"
    old = {nid: {"found": {"need_head": True}, "notice_pdf": None, "v": 1}}
    apply_notice([L()], [], cache=old)
    assert len(calls) == 1                                  # 규칙이 바뀌었으면 다시 읽는다


def test_apply_notice_timeout_uses_cache(monkeypatch):
    """시간 제한으로 못 읽어도 보관 기록 값은 쓴다."""
    from app import pipeline
    import time as _t
    monkeypatch.setattr(pipeline, "NOTICE_BUDGET_SEC", 0.05)
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (_t.sleep(0.3), (None, "x", None))[1])
    x = L(need_head=False)
    nid = x.id.split("-")[0]
    log = []
    apply_notice([x], log, cache={nid: {"found": {"need_head": True}, "notice_pdf": None, "v": 0}})
    assert x.need_head and any("보관" in l for l in log)


def test_ntfy_removed():
    """ntfy 알림은 삭제됨 (2026-10-01): 설정·화면에 남은 것이 없어야 한다."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    cfg = json.loads((root / "docs" / "config.json").read_text(encoding="utf-8"))
    assert "ntfy_topic" not in cfg and "ntfy_alerts" not in cfg["features"]
    assert "ntfy.sh" not in (root / "docs" / "index.html").read_text(encoding="utf-8")



def test_golden_score_ratio_from_real_notices():
    """민영 '전용면적별 1순위 가점제/추첨제 적용비율' 표를 원문과 같게 읽는다 (기능: region_first_score)."""
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    gold = json.loads((root / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
    nos = [k for k, v in gold.items() if "score_ratio" in v["fields"]]
    assert len(nos) >= 4
    for no in nos:
        f = root / "evidence" / "notices" / f"{no}.txt"
        f = f if f.exists() else root / "evidence" / "qa" / "notices" / f"{no}.txt"   # 지난 공고 원문
        text = f.read_text(encoding="utf-8")
        assert notice_pdf.parse_notice(text).get("score_ratio") == gold[no]["fields"]["score_ratio"], no


def test_score_ratio_unknown_and_absent():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "evidence" / "notices"
    # 2026000436: 표 글자가 뒤섞여도 줄마다 면적·비율이 맞고 줄이 이어지면 읽는다 (2026-10-03, 정답 데이터에 있음)
    assert notice_pdf.parse_score_ratio((root / "2026000436.txt").read_text(encoding="utf-8")) == {"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60}]}
    # 뒤섞인 줄을 잘못 짝지어 면적이 이어지지 않으면 추측하지 않고 unknown
    assert notice_pdf.parse_score_ratio("전용면적별 1순위 가점제/추첨제 적용비율 구분 가점제 추첨제 전용면적 60㎡ 이하 40% 60% 전용면적 85㎡ 초과 80% 20%") == {"unknown": True}
    # 공공분양(국민주택) 공고문에는 표가 없다
    assert notice_pdf.parse_score_ratio((root / "2026000409.txt").read_text(encoding="utf-8")) is None
    # 합이 100% 가 아니면 못 읽은 것으로 본다
    assert notice_pdf.parse_score_ratio("전용면적별 1순위 가점제/추첨제 적용비율 구분 가점제 추첨제 전용면적 60㎡ 이하 40% 50%") == {"unknown": True}


def test_pdf_fail_reason_names_file_kind():
    """공고문 PDF 를 못 읽었을 때 원인(스캔 PDF·HWP 등)을 기록에 남긴다 (2026-10-02 오남역 여의재 1단지)."""
    import httpx
    from app import notice_pdf
    page = '<a href="https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do?x=1">모집공고문</a>'
    def handler(req):
        if "getAtchmnfl" in str(req.url):
            return httpx.Response(200, content=bytes.fromhex("d0cf11e0a1b11ae1") + b"0" * 100, headers={"content-type": "application/octet-stream"})
        return httpx.Response(200, text=page)
    c = httpx.Client(transport=httpx.MockTransport(handler))
    text, msg, link = notice_pdf.fetch_notice_text("https://www.applyhome.co.kr/x", client=c)
    assert text is None and "HWP" in msg


def test_pdf_retry_with_referer():
    """첨부 서버가 Referer 없이 받으면 작은 HTML 을 주는 경우 공고 페이지를 Referer 로 다시 받는다."""
    import httpx
    from app import notice_pdf
    page = '<a href="https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do?x=1">모집공고문</a>'
    def handler(req):
        if "getAtchmnfl" in str(req.url):
            if req.headers.get("referer"):
                from io import BytesIO
                return httpx.Response(200, content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf"})
            return httpx.Response(200, text="<script>history.back()</script>", headers={"content-type": "text/html"})
        return httpx.Response(200, text=page)
    c = httpx.Client(transport=httpx.MockTransport(handler))
    seen = []
    orig = notice_pdf.pdf_text
    notice_pdf.pdf_text = lambda b: (seen.append(b), "가" * 600)[1]
    try:
        text, msg, link = notice_pdf.fetch_notice_text("https://www.applyhome.co.kr/x", client=c)
    finally:
        notice_pdf.pdf_text = orig
    assert text and seen and seen[0].startswith(b"%PDF")


def test_unread_notice_warns():
    """공고문을 한 번도 못 읽은 공고는 [경고] 로 남아 운영자 이슈가 열린다 (2026-10-02)."""
    from app import pipeline
    from app.models import Listing
    L = Listing.model_construct(id="2026999999-084.0000A", name="테스트 단지", url="https://www.applyhome.co.kr/x")
    orig = pipeline._fetch_text
    pipeline._fetch_text = lambda url, L0, client=None: (None, "PDF 받기 실패(PDF가 아닌 파일(HTML, text/html, 59바이트))", None)
    try:
        log = []
        try:
            pipeline.apply_notice([L], log, previous={}, cache={})
        except Exception:
            pass
    finally:
        pipeline._fetch_text = orig
    assert any(l.startswith("[경고] 공고문을 읽지 못한 공고: 테스트 단지") for l in log), log


def test_notice_chunks_keep_document_section():
    """청약봇 공고문 조각: 쪽 번호 줄을 빼고, 서류 문단은 머리말과 함께 남는다 (기능: chatbot_notice)."""
    from app.notice_chunks import chunk_text
    text = "■ 입주대상자 자격검증서류 제출\n○ 주민등록표등본\n○ 가족관계증명서\n- 12 -\n" + "가" * 900 + "\n■ 계약 체결\n계약금 10%"
    ch = chunk_text(text)
    assert any("주민등록표등본" in c["t"] and "자격검증서류" in c["h"] for c in ch)
    assert not any("- 12 -" in c["t"] for c in ch)


def test_apply_notice_reads_archived_text_when_download_fails(monkeypatch):
    """받기 실패면 저장해 둔 원문 사본(evidence/notices)으로 읽는다 — 읽기 규칙을 바꾼 뒤 옛 보관 값(거주의무 모름)이 남지 않게 (2026-10-02 2026000438 'URL was not found')."""
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "PDF 받기 실패(PDF가 아닌 파일)", None))
    x = L(id="2026930037-099.9842B", name="과천 푸르지오 벨라르테", address="경기도 과천시", region="경기", sigungu="과천시", unit="99B",
          capital=True, price_cap=True, residence_duty=None)
    log = []
    apply_notice([x], log, cache={"2026930037": {"found": {"need_head": True}, "v": 1}})
    assert x.residence_duty == 0 and "실거주 의무" in x.from_notice
    assert any("원문 사본" in l for l in log)


def test_merge_alt_fills_missing_and_flags_disagreement():
    """두 읽기 도구 합치기 (기능 pdf_dual_read, 2026-10-02 pdf_audit: 과천 벨라르테 '재당첨제한 10년'을 pypdf 는 못 읽고 pypdfium2 는 읽음)."""
    found = {"price_cap": True, "residence_duty": None, "duty_silent": True, "account_months": 6}
    notes = notice_pdf.merge_alt(found, {"price_cap": True, "rewin_years": 10, "residence_duty": 0, "account_months": 12, "residence": {"area": {"name": "과천시"}}})
    assert found["rewin_years"] == 10 and found["residence_duty"] == 0 and "duty_silent" not in found and found["residence"]["area"]["name"] == "과천시"
    assert found["account_months"] == 6 and any("account_months" in c for c in found["conflicts"])   # 둘 다 읽혔는데 다르면 첫 값 유지 + 사람 확인
    assert len(notes) == 3


def test_pdf_text_reads_all_pages_with_both_tools():
    """쪽수 상한(예전 80쪽)과 두 번째 도구 — 법령 별표 PDF 로 두 도구가 모두 글을 읽는지만 본다 (공고문 PDF 는 작업 환경에서 받을 수 없음)."""
    from pathlib import Path
    data = (Path(__file__).parent.parent / "evidence" / "law" / "byeolpyo_1.pdf").read_bytes()
    a, b = notice_pdf.pdf_text(data), notice_pdf.pdf_text_alt(data)
    assert notice_pdf.PAGE_CAP >= 200 and len(a) > 500 and (b is None or len(b) > 500)


def test_pdf_text_alt_is_safe_from_many_threads():
    """수집은 공고문을 6개 스레드로 받는다. pypdfium2 는 동시에 쓰면 깨져(2026-10-02 수집 실패) 잠금으로 한 번에 하나씩 — 여러 스레드에서 같은 결과."""
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    data = (Path(__file__).parent.parent / "evidence" / "law" / "byeolpyo_1.pdf").read_bytes()
    if notice_pdf.pdf_text_alt(data) is None:
        return
    with ThreadPoolExecutor(8) as ex:
        assert len(set(ex.map(lambda _: notice_pdf.pdf_text_alt(data), range(12)))) == 1


def test_pdf_text_alt_runs_outside_collector_process():
    """PDFium 이 죽어도(2026-10-02 21:24 수집 exit 139 segfault) 수집 프로세스는 살아 있어야 한다 — 따로 띄운 프로세스에서 읽고, 실패하면 None."""
    assert "subprocess" in notice_pdf.pdf_text_alt.__code__.co_names or "subprocess" in notice_pdf.pdf_text_alt.__code__.co_varnames
    assert notice_pdf.pdf_text_alt(b"%PDF-1.4 broken") is None
    assert notice_pdf.pdf_text_alt(b"") is None


def test_every_saved_original_score_ratio_reads():
    """모아 둔 민영 공고문 원문의 가점제·추첨제 비율 표는 모두 읽는다 (2026-10-03 사용자 '원인 찾아봐' — 못 읽음 7건 → 0)."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "evidence"
    miss = [f.name for f in sorted([*(root / "notices").glob("*.txt"), *(root / "qa" / "notices").glob("*.txt")])
            if notice_pdf.parse_score_ratio(f.read_text(encoding="utf-8")) == {"unknown": True}]
    assert miss == []


def test_merge_alt_fills_unknown_struct():
    """첫 도구가 '못 읽음' 표시만 남겼으면 두 번째 도구 값으로 채운다 (예전엔 표시가 막았다)."""
    found = {"score_ratio": {"unknown": True}}
    notice_pdf.merge_alt(found, {"score_ratio": {"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60}]}})
    assert found["score_ratio"]["rows"][0]["score"] == 40
    found = {"score_ratio": {"rows": [{"over": 0, "upto": 60, "score": 40, "lottery": 60}]}}
    notice_pdf.merge_alt(found, {"score_ratio": {"unknown": True}})
    assert found["score_ratio"]["rows"][0]["upto"] == 60


def test_golden_resale_from_real_notices():
    """전매제한 기간을 원문과 같게 읽는다 (기능: resale_limit). 정답은 원문 문장을 읽고 적은 칸만 비교."""
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    gold = json.loads((root / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
    nos = [k for k, v in gold.items() if "resale" in v["fields"]]
    assert len(nos) >= 20
    for no in nos:
        f = root / "evidence" / "notices" / f"{no}.txt"
        f = f if f.exists() else root / "evidence" / "qa" / "notices" / f"{no}.txt"
        got = notice_pdf.parse_notice(f.read_text(encoding="utf-8")).get("resale") or {}
        want = gold[no]["fields"]["resale"]
        assert {k: got.get(k) for k in want} == want, (no, got)


def test_every_saved_original_resale_reads():
    """모아 둔 분양 공고문은 전매제한을 모두 읽는다 — 못 읽는 것은 원문에 전매제한이 아예 없는 공고(공공임대 2026000307, 2025000645, 2026000402)뿐"""
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parent.parent
    seen, miss = set(), []
    for d in (root / "evidence" / "notices", root / "evidence" / "qa" / "notices"):
        for f in sorted(d.glob("*.txt")):
            if f.stem in seen:
                continue
            seen.add(f.stem)
            if notice_pdf.parse_resale(re.sub(r"\s+", "", f.read_text(encoding="utf-8"))) is None:
                miss.append(f.stem)
    assert set(miss) <= {"2026000307", "2025000645", "2026000402"}, miss   # 402: 익산 부송에코르 10년 공공임대 — 원문에 전매제한 문장 없음(2026-10-09 확인)


def test_resale_cell_conflict_and_garbled():
    flat = "재당첨제한전매제한거주의무기간분양가상한제택지유형없음1년없음미적용민간택지 본주택의전매제한은최초당첨자발표일로부터적용되며기간은아래와같습니다.구분특별공급일반공급전매제한기간당첨자발표일로부터6개월"
    r = notice_pdf.parse_notice(flat)
    assert r["resale"]["months"] == 6 and any("전매제한" in c for c in r.get("conflicts", []))
    # 숫자 뒤 쪽 번호('3 공급대상')를 기간으로 붙여 읽지 않는다 (2026000436 '로부터개월63')
    assert notice_pdf.parse_resale("전매제한기간당첨자발표일로부터개월63공급대상")["months"] == 6


def test_golden_youth_from_real_notices():
    """청년 특별공급 소득(1인 140%)·총자산(본인·부모) 기준을 원문과 같게 읽는다 (기능: youth_special)."""
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    gold = json.loads((root / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
    nos = [k for k, v in gold.items() if "youth" in v["fields"]]
    assert len(nos) >= 3
    for no in nos:
        f = root / "evidence" / "notices" / f"{no}.txt"
        f = f if f.exists() else root / "evidence" / "qa" / "notices" / f"{no}.txt"
        assert notice_pdf.parse_notice(f.read_text(encoding="utf-8")).get("youth") == gold[no]["fields"]["youth"], no
    assert notice_pdf.parse_youth("신혼부부특별공급 140% 5,338,708") is None   # 청년 특별공급이 없는 공고


def test_rent_noincome_reads_only_matching_table():
    """민간 5년 공공건설임대(국민주택) — 신청자격 표의 소득·자산기준이 모두 '-'면 kind 'none' (기능 rent_noincome). 분양전환 후 잔여세대(2026000022)는 아님"""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    t = (root / "evidence" / "qa" / "notices" / "2025000645.txt").read_text(encoding="utf-8")
    assert notice_pdf.parse_notice(t).get("pub_limits") == {"kind": "none"}
    f = root / "evidence" / "notices" / "2026000022.txt"
    f = f if f.exists() else root / "evidence" / "qa" / "notices" / "2026000022.txt"
    assert (notice_pdf.parse_notice(f.read_text(encoding="utf-8")).get("pub_limits") or {}).get("kind") != "none"
