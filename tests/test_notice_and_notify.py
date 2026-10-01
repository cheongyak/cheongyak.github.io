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
    x = L(need_head=False)
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
        text = (root / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")
        assert notice_pdf.parse_notice(text).get("score_ratio") == gold[no]["fields"]["score_ratio"], no


def test_score_ratio_unknown_and_absent():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "evidence" / "notices"
    # 2026000436: 표 글자가 뒤섞여 추출돼 비율을 확실히 못 읽는다 → 추측하지 않고 unknown
    assert notice_pdf.parse_score_ratio((root / "2026000436.txt").read_text(encoding="utf-8")) == {"unknown": True}
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
