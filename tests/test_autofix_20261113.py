"""2026-11-13 아침 자동 고치기 — 처음 보는 공고문 꼴 (원문 evidence/notices, 정답 tests/golden/notices.json)."""
import json
import pathlib

from app import notice_pdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))


def _t(no):
    return (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_residence_summary_table_gijun_2026000576():
    """아르뮤제자이: 요약 표가 '입주자모집공고일 현재' 대신 '입주자모집공고일 기준 경기도 안산시 거주자' — 해당지역을 못 읽어 '확인 필요'였다."""
    assert notice_pdf.parse_residence(_t("2026000576")) == GOLD["2026000576"]["fields"]["residence"]
    head = "주택유형 해당지역 기타지역 규제지역여부 민영 "
    r = notice_pdf.parse_residence(head + "입주자모집공고일 기준 경기도 안산시 거주자 입주자모집공고일 기준 경기도 및 서울특별시, 인천광역시 거주자 비규제지역 재당첨제한")
    assert r["area"]["sigungu"] == "안산시" and r["months"] == 0 and set(r["others"]) == {"서울", "인천", "경기"}
    # 거주기간 낱말은 있는데 숫자가 없으면 '기간 없음'으로 두지 않고 못 읽음 (기존 원칙 그대로)
    assert notice_pdf.parse_residence(head + "입주자모집공고일 기준 경기도 안산시 년 이상 계속 거주자 입주자모집공고일 기준 경기도 거주자 비규제지역 재당첨제한") is None


def test_nul_spaces_2026910287():
    """더샵 청주그리니티 무순위 2차: PDF 글의 낱말 사이 띄어쓰기가 NUL 글자(\\x00) — '현재\\x00충청북도에\\x00거주하는' 을 못 읽어 거주 요건이 '확인 필요'였다."""
    t = _t("2026910287")
    assert "\x00" in t
    g = GOLD["2026910287"]["fields"]
    o = notice_pdf.parse_notice(t)
    assert notice_pdf.parse_residence(t) == g["residence"] == o["residence"]
    assert (o["need_head"], o["residence_duty"], o["pay_ratio"]) == (g["need_head"], g["residence_duty"], g["pay_ratio"])
    s = "■ 본 주택은 무순위(사후) 입주자모집공고일 현재 충청북도에 거주하는 무주택세대구성원을 대상으로 공급합니다."
    assert notice_pdf.parse_residence(s.replace(" ", "\x00")) == notice_pdf.parse_residence(s)
    # NUL 이 없는 글은 그대로
    assert notice_pdf._nul_space("가 나") == "가 나"
