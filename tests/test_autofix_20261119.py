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


def test_resale_digit_pushed_back_checked_by_table_2026910295_2026930046():
    """연제갤러리자이 무순위·광주 송정 중흥S-클래스 파크뷰 재공급: 전매제한 문장의 숫자(·날짜)가 뒤로 밀린 꼴 —
    '모든 저장 원문 전매제한' 시험이 실패해 수집이 멈출 뻔했다. 1쪽 표와 숫자가 맞을 때만 읽는다."""
    import re
    for no in ("2026910295", "2026930046"):
        got = notice_pdf.parse_notice(_t(no))["resale"]
        want = GOLD[no]["fields"]["resale"]
        assert {k: got.get(k) for k in want} == want, (no, got)
    body = "■본아파트의전매제한은최초입주자모집공고의당첨자발표일(2026.10.27.)로부터개월간6적용됩니다."
    table = "재당첨제한전매제한거주의무기간분양가상한제없음최초당첨자발표일(2026.10.27.)로부터개월6없음미적용"
    assert notice_pdf.parse_resale(table + body)["months"] == 6
    # 1쪽 표가 없거나 숫자·날짜가 다르면 밀린 숫자를 기간으로 읽지 않는다
    assert notice_pdf.parse_resale(body) is None
    assert notice_pdf.parse_resale(table.replace("개월6", "개월3") + body) is None
    assert notice_pdf.parse_resale(table.replace("10.27", "10.28") + body) is None
    body2 = "본주택의전매제한은최초입주자모집공고의당첨자발표일로부터개월간적용되어현재전매제한기간이도과하였습니다(2022.12.20.)6.■"
    table2 = "전매제한거주의무기간분양가상한제택지유형최초당첨자발표일로부터(2022.12.20.)개월간적용되어현재기간도과6없음미적용민간택지"
    r = notice_pdf.parse_resale(table2 + body2)
    assert (r["months"], r["base"], r["passed"]) == (6, "2022-12-20", True)
    assert notice_pdf.parse_resale(body2) is None
    assert re.search("도과6", table2)
