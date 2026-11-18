"""2026-11-19 아침 자동 고치기 — 처음 보는 공고문 꼴 (원문 evidence/notices, 정답 tests/golden/notices.json)."""
import json
import pathlib

from app import notice_pdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))


def _t(no):
    return (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_pay_audit_split_header_with_gyeyak_hu_2026910292():
    """검암역 푸르지오 프라베뉴 무순위: 계약금 머리 '계약 시 (5%) 계약 후 15일 이내 (5%)' — 점검 도구가 '계약 후'를 몰라 5%+5% 줄을 5% 로만 세어
    '표 줄과 안 맞음'(수집 첫 시험 실패) 거짓 경보를 냈다. 읽은 값(10%)은 원문 그대로."""
    from tools.qa import pay_audit as PA
    t = _t("2026910292")
    assert notice_pdf.parse_notice(t)["pay_ratio"] == GOLD["2026910292"]["fields"]["pay_ratio"]
    assert PA.row_rates(t).get(10, 0) > 0
    row = " 605,900,000 30,295,000 30,295,000 60,590,000"
    assert PA.row_rates("계약금(10%) 중도금(60%) 잔금(30%) 계약 시 (5%) 계약 후 15일 이내 (5%)" + row).get(10, 0) == 1
    # 두 칸 머리가 없으면 그대로 5% 줄로만 센다 (머리 글자 없이 합쳐 보지 않음)
    assert PA.row_rates("계약금(10%) 중도금(60%) 잔금(30%)" + row).get(10, 0) == 0
