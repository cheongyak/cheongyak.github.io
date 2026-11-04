"""2026-11-02 주간 원문 대조(evidence/audit/2026-11-02-blind) P1: 제주 삼도이동 1·2지구 토지임대부(2026000434·435)
공고문은 '거주의무 최초 입주가능일 5년 「주택법」제57조의2' 인데 수집이 '거주의무는 수도권 분양가상한제 주택에만' 규칙으로 0 으로 덮어
화면이 '실거주 의무 없음'으로 안내하던 것. 공고문이 기간을 적었으면 지역과 관계없이 그 값을 쓴다. 정답 tests/golden/notices.json."""
import json
from datetime import date
from pathlib import Path

import pytest

from app import notice_pdf, validate
from app.models import Listing
from app.pipeline import apply_notice

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _jeju(nid, **kw):
    base = dict(id=f"{nid}-059.9783A", name="삼도이동 토지임대부 공공분양주택", address="제주특별자치도 제주시", region="지방",
                kind="공공분양", category="general", unit="59A", price=3.0, households=10, apply="2026-11-16",
                notice="2026-10-27", url=f"https://www.applyhome.co.kr/{nid}", capital=False, price_cap=True, land_lease=True)
    base.update(kw)
    return Listing(**base)


def _apply(L, found, monkeypatch):
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "받기 생략(시험)", None))
    from app import pipeline
    monkeypatch.setattr(pipeline, "recheck_attachments", lambda cached, client=None, budget=60: {})   # 청약홈 첨부 확인(네트워크) 생략
    cache = {L.id.split("-")[0]: {"found": found, "notice_pdf": "https://x/p.pdf", "v": pipeline.PARSER_VERSION}}
    apply_notice([L], [], previous={}, cache=cache)
    return L


@pytest.mark.parametrize("nid", ["2026000434", "2026000435"])
def test_jeju_landlease_duty_from_notice(nid, monkeypatch):
    found = notice_pdf.parse_notice((ROOT / "evidence/notices" / f"{nid}.txt").read_text(encoding="utf-8"))
    assert found["residence_duty"] == 5 == GOLD[nid]["fields"]["residence_duty"]
    L = _apply(_jeju(nid), found, monkeypatch)
    assert L.residence_duty == 5 and ("실거주 의무", "5년") in L.limits
    assert not any("실거주 의무가 수도권" in c for c in validate.listing_checks(L, date(2026, 11, 4)))
    assert not [m for m in validate.golden_mismatches([L]) if "residence_duty" in m]


def test_non_capital_without_duty_stays_none(monkeypatch):
    """공고문에 기간이 없거나 '없음'이면 예전처럼 0(수도권 분양가상한제가 아니면 거주의무 없음)."""
    assert _apply(_jeju("2026939998"), {"price_cap": True}, monkeypatch).residence_duty == 0
    assert _apply(_jeju("2026939997"), {"price_cap": True, "residence_duty": 0}, monkeypatch).residence_duty == 0
    x = _apply(_jeju("2026939996", land_lease=False, price_cap=False), {"price_cap": False, "residence_duty": 0}, monkeypatch)
    assert x.residence_duty == 0 and ("실거주 의무", "없음") in x.limits


def test_validator_still_flags_duty_not_from_notice():
    """공고문에서 읽지 않았는데 비수도권에 거주의무가 붙어 있으면 여전히 경고."""
    L = _jeju("2026939995", residence_duty=3, from_notice=[])
    assert any("실거주 의무가 수도권" in c for c in validate.listing_checks(L, date(2026, 11, 4)))


@pytest.mark.parametrize("text", [
    "전매제한 1년 거주의무 없음",
    "전매제한기간 3년 거주의무기간 해당없음",
    "※ 수도권 공공택지 분양가상한제 적용주택은 거주의무기간은 최대 5년 적용됩니다.",
    "수도권 분양가상한제 적용주택의 경우 3년 거주의무가 있으나 본 주택은 해당되지 않습니다",
])
def test_non_landlease_non_capital_ignores_misread_duty(text, monkeypatch):
    """토지임대부가 아닌 비수도권 공고는 공고문 읽기가 기간을 잘못 읽어도(다른 눈 검토 11-05 재현 문장) 예전처럼 0 이고, 검증 경고도 그대로."""
    found = notice_pdf.parse_notice(text)
    L = _apply(_jeju("2026939990", name="어느 지방 공공분양주택", land_lease=False), dict(found, price_cap=True), monkeypatch)
    assert L.residence_duty == 0
    L2 = _jeju("2026939989", name="어느 지방 공공분양주택", land_lease=False, residence_duty=3, from_notice=["실거주 의무"])
    assert any("실거주 의무가 수도권" in c for c in validate.listing_checks(L2, date(2026, 11, 4)))
