"""2026-11-27 운영자 요청 (기능 analysis_pages)
- /analysis/{공고ID}/ 단지 분석 리포트: ①핵심 결론 ②분양가·시세 비교 ③계약금·중도금·잔금과 연봉별 대출·필요 현금 ④체크리스트, 공고 정리·판정 원칙 링크
- 공고 정리 페이지에는 리포트가 있는 공고에만 링크 1개
숫자는 화면 엔진 결과(seo_engine.json 의 rows·sim)만 쓴다."""
import copy
import json
import re

import pytest

from tools import seo_pages as S
from tools.qa import seo_static

UNIT = {"id": "2099000001-084.0000A", "name": "시험마을 푸른아파트", "address": "경기도 시험시 시험동", "sido": "경기", "district": "시험시", "house_dtl": "민영", "kind": "일반분양 (특별공급·1순위)",
        "unit": "84A", "area": 84.5, "households": 100, "price": 6.0, "notice": "2099-01-02", "special_apply": "2099-01-12", "apply": "2099-01-13", "apply_end": "2099-01-14", "winner": "2099-01-20",
        "contract": "2099-02-01", "pay_ratio": {"contract": 0.1, "mid": 0.6, "balance": 0.3}, "from_notice": ["계약금 비율"], "mkt_low": 6.5, "mkt_base": 7.0, "mkt_count": 34,
        "mkt_note": "같은 동 준공 10년 이내 같은 평형 매매 34건 기준 (최근 6개월)", "mkt_comps": [{"apt": "이웃단지", "date": "2098-12-01"}], "regulated": True, "capital": True, "price_cap": True,
        "limits": [["재당첨 제한", "10년"], ["실거주 의무", "공고문 확인"], ["전매 제한", "없음"]], "residence": {"area": {"name": "경기도 시험시"}, "months": 12, "others": ["서울", "인천", "경기"]},
        "account_months": 24, "need_account": True, "need_head": False, "rental": False, "land_lease": False, "score_ratio": {"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60}]}}
ROW = {"g": "consider", "label": "고려", "margin": "마진 +3,000만~8,000만", "lo": 0.3, "hi": 0.8, "rate": 0.05, "cost": 6.2, "tax": 0.07, "base": 6.13, "lease": None, "how": "기준 시세는 중앙값, 보수 시세는 하위 25% 값이에요."}
SIM = [{"income": 5000, "total": 6.2, "contract": 0.6, "loan": 2.505, "by": "DSR(소득)", "loanDsr": 2.505, "loanLtv": 3.6, "ltv": 0.6, "ltvWhy": "서민·실수요자", "cap": 6, "need": 3.695, "monthly": 0.012, "test": 7, "add": 3},
       {"income": 7000, "total": 6.2, "contract": 0.6, "loan": 3.507, "by": "DSR(소득)", "loanDsr": 3.507, "loanLtv": 3.6, "ltv": 0.6, "ltvWhy": "서민·실수요자", "cap": 6, "need": 2.693, "monthly": 0.0167, "test": 7, "add": 3},
       {"income": 10000, "total": 6.2, "contract": 0.6, "loan": 2.4, "by": "집값의 40%", "loanDsr": 5.01, "loanLtv": 2.4, "ltv": 0.4, "ltvWhy": "", "cap": 6, "need": 3.8, "monthly": 0.0115, "test": 7, "add": 3}]


def _rec(**over):
    u = dict(copy.deepcopy(UNIT), **over)
    return {"live": True, "closed": False, "type": "민영", "units": [u], "eng": {u["id"]: dict(ROW)}, "res": {}, "recap": None}


def _eng(sim=True):
    return {"rows": {UNIT["id"]: dict(ROW)}, "sim": {UNIT["id"]: copy.deepcopy(SIM)} if sim else {}, "sim_assume": {"incomes": [5000, 7000, 10000], "rate": 4, "years": 30, "dsr": 0.4},
            "rules": {}, "names": {"lotto": "로또", "consider": "고려", "flat": "마진없음", "pass": "비추천", "unknown": "판단보류"}}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(S, "feature", lambda k: True)


def test_only_notices_with_grade_and_simulation_get_a_report(on, monkeypatch):
    assert S.analysis_ok(_rec(), _eng())
    assert not S.analysis_ok(_rec(), _eng(sim=False))                      # 자금 계산이 없으면 안 만듦
    assert not S.analysis_ok(_rec(rental=True), _eng()) and not S.analysis_ok(_rec(land_lease=True), _eng())
    r = _rec(); r["eng"][UNIT["id"]]["g"] = "unknown"
    assert not S.analysis_ok(r, _eng())                                    # 시세를 못 구한 공고
    r = _rec(); r["live"] = False
    assert not S.analysis_ok(r, _eng())                                    # 목록에서 빠진 마감 공고
    monkeypatch.setattr(S, "feature", lambda k: k != "analysis_pages")
    assert not S.analysis_ok(_rec(), _eng())                               # 스위치 끔


def test_report_has_four_parts_links_and_engine_numbers(on):
    title, desc, body, head, crumbs = S.analysis_page("2099000001", _rec(), _eng(), "2099-01-05")
    for h in ("한눈에 보는 핵심 결론", "분양가와 주변 실거래 시세", "연봉별 예상 대출과 필요 현금", "신청 전 체크리스트"):
        assert h in body, h
    assert 'href="/notice/2099000001/"' in body and 'href="/about/policy/"' in body
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", body))
    for must in ("3,000만 원", "6.20억 원", "2억 5,050만 원", "소득 기준(DSR)", "집값 기준(40%)", "3억 6,950만 원", "약 167만 원", "계약금 약 6,000만 원", "가점제 40%·추첨제 60%",
                 "전매 제한 — 이 공고에는 없어요", "실거주 의무 — 청약패스가 공고문에서 값을 읽지 못했어요", "재당첨 제한 — 10년"):
        assert must in text, must
    assert not S.FORBID.search(text) and not seo_static.FORBID.search(text)
    assert len(seo_static.prose("<main>" + body + "</main>")) >= seo_static.MIN_PROSE
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S).group(1))
    assert ld["@type"] == "Article" and ld["mainEntityOfPage"].endswith("/analysis/2099000001/") and ld["dateModified"] == "2099-01-05"
    assert crumbs[-2] == ("/notice/2099000001/", UNIT["name"])


def test_no_midpayment_notice_is_not_described_as_group_loan(on):
    body = S.analysis_page("2099000001", _rec(pay_ratio={"contract": 0.1, "mid": 0, "balance": 0.9}), _eng(), "2099-01-05")[2]
    assert "중도금 없이 계약금과 잔금으로" in body and "집단대출" not in body


def test_notice_page_gets_exactly_one_link_only_when_report_exists(on, monkeypatch):
    r, eng = _rec(), _eng()
    recs = S.OrderedDict([("2099000001", r)])
    monkeypatch.setattr(S, "ANALYSIS_IDS", {"2099000001"})
    body = S.notice_page("2099000001", r, recs, eng)[2]
    assert body.count('href="/analysis/2099000001/"') == 1 and S.ANALYSIS_LINK in body
    assert body.index("한눈에 보기") < body.index("/analysis/2099000001/")
    monkeypatch.setattr(S, "ANALYSIS_IDS", set())
    assert "/analysis/" not in S.notice_page("2099000001", r, recs, eng)[2]
