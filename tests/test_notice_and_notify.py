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


def test_notify_new_and_due():
    cfg = {"notify_grades": ["lotto", "consider"], "remind_days_before": 1}
    lotto, flat = L(), L(id="999-059A", name="패스단지", price=30.0)
    msgs = notify.build_messages([lotto, flat], previous_ids=set(), today=date(2026, 10, 5), cfg=cfg)
    titles = [m["title"] for m in msgs]
    assert any("로또" in t and "1건" in t for t in titles)
    assert any(t.startswith("내일 접수 시작") for t in titles)
    assert "패스단지" not in "".join(m["body"] for m in msgs)
    # 이미 알린 공고는 다시 '새 공고'로 보내지 않고, 첫 실행(previous None)도 보내지 않는다
    assert not notify.build_messages([lotto], {lotto.id}, date(2026, 9, 29), cfg)
    assert not notify.build_messages([lotto], None, date(2026, 9, 29), cfg)


def test_notify_send_payload():
    seen = {}

    def h(req):
        import json
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={})
    out = notify.send([{"title": "t", "body": "b", "priority": "high", "tags": "house"}],
                      {"ntfy_topic": "cheongyak-test", "site_url": "https://example.org/"},
                      httpx.Client(transport=httpx.MockTransport(h)))
    assert seen["topic"] == "cheongyak-test" and seen["priority"] == 4 and seen["click"] == "https://example.org/"
    assert out[0].startswith("알림 전송 200")


def test_notify_deadline_reminder():
    cfg = {"notify_grades": ["lotto", "consider"], "remind_days_before": 1}
    x = L(apply="2026-09-29", apply_end="2026-10-02")
    msgs = notify.build_messages([x], {x.id}, date(2026, 10, 1), cfg)
    assert msgs and msgs[0]["title"].startswith("내일 접수 마감")


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
             sido="서울", district="광진구", limits=[("재당첨 제한", "10년")])
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
