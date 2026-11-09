"""무순위 1쪽 '단지 주요정보' 표의 거주의무 칸이 뒤섞인 꼴 (2026910283 영종하늘도시 A25블록 대성베르힐(5차), 2026-11-09 주간 원문 대조 P1).
원문: '재당첨제한 전매제한 거주의무기간 분양가상한제 없음 최초 당첨자 발표일 로부터 년간 (2021.12.15.) 3 적용되어 현재 전매제한 기간 도과 년 3 적용 구분'
— 거주의무 칸 '3년'이 '년 3' 으로 나와 표 전체를 못 읽었고, 화면이 '실거주 의무 없음(추정)'·분양가상한제 '미적용'(청약홈 값)을 보였다.
정답 데이터에는 아직 넣지 않음 — 본문에 거주의무 문장이 없고 청약홈 값(미적용)과 달라 운영자 확인(최초 공고 2021000897·사업주체) 뒤에 넣는다."""
import json
from pathlib import Path

from app.notice_pdf import _summary_table, parse_notice

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _t(n):
    return (ROOT / "evidence/notices" / f"{n}.txt").read_text(encoding="utf-8")


def test_golden_mu_summary_scrambled_duty():
    o = parse_notice(_t("2026910283"))
    assert (o.get("residence_duty"), o.get("price_cap")) == (3, True)   # 칸 순서로 읽은 값(확인 전)
    assert "1쪽" in o["quotes"]["residence_duty"] and "년 3 적용" in o["quotes"]["residence_duty"]
    # 전매제한은 그대로 (3년, 2021-12-15 부터, 이미 지남)
    assert (o["resale"]["months"], o["resale"]["base"], o["resale"]["passed"]) == (36, "2021-12-15", True)


def test_scrambled_duty_only_right_before_price_cap_cell():
    head = "재당첨제한 전매제한 거주의무기간 분양가상한제 "
    assert _summary_table(head + "없음 최초 당첨자 발표일 로부터 년간 (2021.12.15.) 3 적용되어 현재 전매제한 기간 도과 년 3 적용 구분")["residence_duty"] == 3
    assert _summary_table(head + "없음 6개월 년 2 미적용 구분")["residence_duty"] == 2
    # 예전 꼴은 그대로
    assert _summary_table(head + "없음 최초 당첨자발표일(2026.09.01.)로부터 1년 없음 적용 구분")["residence_duty"] == 0
    assert _summary_table(head + "없음 3년 (다만, 기간 내 소유권 이전 등기 시 해제) 없음 적용 구분")["residence_duty"] == 0
    # 전매 칸의 '년 (날짜) 3' 은 거주의무로 읽지 않는다 (2026910251 '년10 … 로부터 년 (2026.08.31.) 3 없음 미적용')
    assert _summary_table(head + "년10 최초 당첨자 발표일 로부터 년 (2026.08.31.) 3 없음 미적용 구분")["residence_duty"] == 0
    # 분양가상한제 칸(적용|미적용)·'구분'이 바로 뒤에 없으면 읽지 않는다
    assert _summary_table(head + "없음 최초 당첨자 발표일 로부터 년 3 적용되어 현재 도과 구분") is None
    assert _summary_table(head + "없음 없음 년 6 적용 구분") is None   # 거주의무는 1~5년


def test_pipeline_shows_duty_and_price_cap(monkeypatch):
    """수집 단계: 청약홈 값(분양가상한제 미적용·거주의무 0)을 공고문 값으로 바꿔 화면이 '실거주 의무 3년'을 보인다."""
    from app import notice_pdf, pipeline, validate
    from app.models import Listing
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "받기 생략(시험)", None))
    monkeypatch.setattr(pipeline, "recheck_attachments", lambda cached, client=None, budget=60: {})
    nid = "2026910283"
    L = Listing(id=f"{nid}-084.1579D", name="인천 영종하늘도시 A25블록 대성베르힐(5차)", address="인천광역시 영종구 운남동", region="인천",
                kind="무순위", category="remainder", unit="84D", price=4.004, households=1, apply="2026-11-11", notice="2026-11-06",
                url=f"https://www.applyhome.co.kr/{nid}", capital=True, price_cap=False, residence_duty=0)
    found = parse_notice(_t(nid))
    pipeline.apply_notice([L], [], previous={}, cache={nid: {"found": found, "notice_pdf": "https://x/p.pdf", "v": pipeline.PARSER_VERSION}})
    assert (L.price_cap, L.residence_duty) == (True, 3)
    assert ("실거주 의무", "3년") in L.limits
    assert not [m for m in validate.golden_mismatches([L]) if nid in m]
    assert "실거주 의무" in (L.notice_quotes or {}) and "분양가상한제" in (L.notice_quotes or {})
