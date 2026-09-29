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
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (GANGBYEON_TEXT * 3, "PDF 읽음"))
    x = L(need_head=False)
    log = []
    apply_notice([x], log)
    assert x.need_head and x.balance == "2026-11-30" and x.ext == 0.2178
    assert ("실거주 의무", "없음") in x.limits and "PDF 읽음" in log[0]


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
