"""공고문 해석 정확도 점검 (2026-10-09 사용자 요청 '공고문을 잘못 읽거나 조건을 잘못 연결하는 문제').
지금 접수 중인 공고 60건을 파서 결과를 보지 않은 검토자가 원문만 읽고 적은 값(evidence/audit/2026-10-09-blind/)과 화면 데이터를 대조해 찾은 오류를 고정한다.
- P0 세대주 요건이 특별공급 문장에 연결됨 (재공급 2026930031·034: 일반공급은 무주택세대주인데 '가능')
- P1 거주기간 숫자가 밀린 글에서 '요건 없음(0)'으로 읽음 (2026000471: 광주 1년 이상)
- P2 분양가상한제를 법 설명 문장에서 읽음(2026000402) / 무순위 1쪽 표 미해석(2026910248) / '현재 전매제한기간 도과' 놓침(2026930041)
정답 값은 tests/golden/notices.json (원문을 직접 읽어 확인)."""
import json
import re
from pathlib import Path

from app.notice_pdf import _in_special_section, need_head_general, parse_notice, parse_residence, parse_resale

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _p(n):
    return parse_notice((ROOT / "evidence/notices" / f"{n}.txt").read_text(encoding="utf-8"))


def test_need_head_reads_general_supply_not_special():
    for n in ("2026930031", "2026930034"):
        o = _p(n)
        assert o["need_head"] is True, n
        assert "일반공급은" in o["quotes"]["need_head"], o["quotes"]["need_head"]   # 근거 문장도 일반공급 문장
    # 특별공급만 있는 재공급(일반공급 없음)은 특별공급 문장으로 일반공급 조건을 만들지 않는다
    for n in ("2026930039", "2026930041"):
        assert "need_head" not in _p(n), n


def test_need_head_private_table_second_rank_cell():
    """민영 '신청자격' 표 세대주 요건: 머리 칸 수 = 값 칸 수일 때만, 2순위 칸으로 (1순위 '필요'는 규제지역 규칙이 따로 본다)"""
    o = _p("2026000453")   # 광명(투기과열) '- - - 필요 필요 필요 필요 -' → 1순위만 세대주
    assert o["need_head"] is False and "세대주 요건" in o["quotes"]["need_head"]
    flat = "신청자격특별공급일반공급기관추천다자녀가구신혼부부노부모부양생애최초신생아1순위2순위청약통장…세대주요건---필요--필요필요소득또는"
    assert need_head_general(flat)[0] is True                            # 2순위도 필요 → 공급 전체 세대주
    flat_bad = "신청자격특별공급일반공급기관추천다자녀가구신혼부부노부모부양생애최초신생아1순위2순위청약통장…세대주요건---필요---소득또는"
    assert need_head_general(flat_bad) is None                          # 칸이 하나 모자람 → 어느 칸인지 모름 → 읽지 않음


def test_need_head_lh_public_sale():
    for n in ("2026000414", "2026000409", "2026000416", "2026000437"):
        assert _p(n).get("need_head") is False, n   # '공급신청자격자 • 주택공급신청은 무주택세대구성원 중 1인만 가능'


def test_special_section_detector():
    flat = "4-1생애최초특별공급(「주택공급에관한규칙」제43조)구분내용대상자■입주자모집공고일현재해당주택건설지역인대전광역시에거주하는무주택세대구성원"
    assert _in_special_section(flat, flat.find("거주하는"))
    flat2 = "5일반공급(「주택공급에관한규칙」제47조의3)구분내용대상자■입주자모집공고일현재해당주택건설지역인대전광역시에거주하는무주택세대주"
    assert not _in_special_section(flat2, flat2.find("거주하는"))


def test_residence_digit_after_since_and_no_silent_zero():
    r = _p("2026000471")["residence"]
    assert (r["months"], r["since"]) == (12, "2025-10-08")
    assert {k: r[k] for k in GOLD["2026000471"]["fields"]["residence"]} == GOLD["2026000471"]["fields"]["residence"]
    # '년 이상' 낱말은 있는데 숫자가 없으면 '요건 없음(0)'이 아니라 못 읽음(None) → 화면 '확인 필요'
    t = "해당지역 기타지역 규제지역여부 민영 광주광역시 년 이상 계속 거주자 이전부터 계속 거주 (2025.10.08. ) 광주광역시 년 미만 거주자 및 전라남도 거주자 비규제지역 재당첨제한"
    assert parse_residence(t) is None


def test_price_cap_from_this_house_only():
    assert "price_cap" not in _p("2026000402")                         # '분양가상한제 적용주택 등에 이미 당첨되어…' 는 법 설명
    o = _p("2026910248")
    assert o["price_cap"] is True and o["residence_duty"] == 0 and "1쪽" in o["quotes"]["price_cap"]
    for n in ("2026000409", "2026000437", "2026930041", "2026910249"):
        assert _p(n)["price_cap"] is True, n                              # '…분양가상한제 적용주택으로' · 당첨 시 재당첨 표


def test_resale_passed_when_text_says_expired():
    r = _p("2026930041")["resale"]
    assert r["passed"] is True and r["months"] == 12
    assert parse_resale(re.sub(r"\s+", "", "전매제한기간 최초 당첨자발표일로부터 1년간 적용되어 현재 전매제한기간 도과"))["passed"] is True
    assert parse_resale("전매제한기간당첨자발표일로부터6개월")["passed"] is False


def test_golden_scalar_fields_match_parser():
    """정답 데이터의 공고문 값(세대주·분양가상한제·거주의무·재당첨·통장)과 파서 결과가 같다. 예외는 공고문에 없어 수집이 규칙으로 채우는 값뿐."""
    allowed = {("2026820010", "need_head"), ("2026930036", "rewin_years"), ("2026930037", "rewin_years")}
    bad = []
    for n, v in GOLD.items():
        f = ROOT / "evidence/notices" / f"{n}.txt"
        if not f.exists():
            continue
        o = parse_notice(f.read_text(encoding="utf-8"))
        for k in ("need_head", "price_cap", "residence_duty", "rewin_years", "account_months", "deposit_count"):
            if k in v["fields"] and o.get(k) != v["fields"][k] and (n, k) not in allowed:
                bad.append((n, k, v["fields"][k], o.get(k)))
    assert not bad, bad


def test_validate_flags_head_quote_from_special_section():
    from datetime import date
    from app import validate
    from app.models import Listing
    base = dict(id="2026930034-124.0000", name="도안 푸르지오 디아델 31블록", address="대전광역시 유성구", region="지방", kind="불법행위 재공급", category="remainder",
                unit="124", price=5.3, households=2, apply="2026-10-12", notice="2026-10-06", url="https://www.applyhome.co.kr/x", from_notice=["세대주 요건"])
    bad = Listing(**base, notice_quotes={"세대주 요건": "…4-1 생애최초 특별공급 … 대상자 ■ 입주자모집공고일 현재 해당 주택건설지역인 대전광역시에 거주하는 무주택세대구성원 ■ 생애최초로…"})
    ok = Listing(**base, notice_quotes={"세대주 요건": "…■ 본 입주자모집공고의 일반공급은 해당 주택건설지역 거주자 중 무주택세대주(무주택세대의 세대주)를 대상으로…"})
    msg = "세대주 요건의 근거 문장이 특별공급 대상자 문장"
    assert any(msg in c for c in validate.listing_checks(bad, date(2026, 10, 9)))
    assert not any(msg in c for c in validate.listing_checks(ok, date(2026, 10, 9)))
