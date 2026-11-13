"""'거주의무기간이 적용되지 않습니다' 문장을 거주의무 없음(0)으로 읽기 (2026-11-13 밤 자동 개선).

2026000530·532 계양신도시 카이브 유보라(AC3BL·AC4BL): 1쪽 표 택지유형 칸이 '대규모 택지개발지구/ 공공택지 / …'라
표 규칙이 못 읽고, 본문 '■ 거주의무에 관한 사항' 문장
'본 주택은 … 「주택법」 제57조의2 및 동법 시행령 제60조의2에 따라 거주의무기간이 적용되지 않습니다.' 도 못 읽어
실거주 의무가 '모름'(확인 필요)으로 남았다.
"""
import json
from pathlib import Path

import pytest

from app.notice_pdf import parse_notice

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("hid", ["2026000530", "2026000532"])
def test_golden_duty_not_applied_sentence(hid):
    src = ROOT / f"evidence/notices/{hid}.txt"
    if not src.exists():
        pytest.skip("원문 없음")
    r = parse_notice(src.read_text(encoding="utf-8"))
    assert r.get("residence_duty") == GOLDEN[hid]["fields"]["residence_duty"] == 0
    assert "거주의무기간이 적용되지 않습니다" in (r.get("quotes") or {}).get("residence_duty", "").replace("\n", " ")


def _wrap(body: str) -> str:
    return "재당첨제한 전매제한 거주의무기간 분양가상한제 택지유형\n10년 3년 없음 적용 대규모 택지개발지구/ 공공택지\n" + "가" * 500 + "\n" + body


def test_sentence_about_this_house():
    t = _wrap("• 본 주택은 수도권 공공택지에서 공급하는 분양가 상한제 적용 민영주택으로, 「주택법」 제57조의2 및 동법 시행령 제60조의2에 따라 거주의무기간이 적용되지 않습니다.")
    assert parse_notice(t).get("residence_duty") == 0


def test_sentence_without_this_house_is_not_read():
    # '본 주택'이 없는 일반 설명(조건문)은 이 주택의 조건으로 읽지 않는다
    t = _wrap("분양가격이 인근지역 주택매매가격의 100% 이상인 경우에는 거주의무기간이 적용되지 않습니다.")
    assert parse_notice(t).get("residence_duty") is None


def test_years_sentence_still_wins():
    t = _wrap("본 주택은 분양가상한제 적용주택으로 거주의무기간은 최초 입주가능일부터 3년간 적용됩니다. 본 주택은 전매제한 …")
    assert parse_notice(t).get("residence_duty") == 3


def test_model_house_or_condition_is_not_read():
    # '견본주택'의 '본주택'이나 조건문('… 경우 거주의무기간이 …')은 이 주택의 조건이 아니다 (다른 눈 검토 11-13)
    assert parse_notice(_wrap("견본주택 방문 시 유의하세요. 분양가격이 인근지역 주택매매가격의 100% 이상인 경우에는 거주의무기간이 적용되지 않습니다.")).get("residence_duty") is None
    assert parse_notice(_wrap("본 주택은 분양가상한제 적용주택입니다. 향후 분양가격이 100% 이상인 경우 거주의무기간이 적용되지 않습니다.")).get("residence_duty") is None
