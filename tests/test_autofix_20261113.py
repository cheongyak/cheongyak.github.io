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


def test_pub_limits_reference_mark_2026000457():
    """부천대장 하우스토리 디센트: 요약 표 소득 줄이 '(맞벌이 200%) ※ 전용면적 60㎡ 이하만 적용' — '*' 대신 '※' 라 60㎡ 이하 일반공급 소득·자산 기준을 못 읽었다."""
    assert notice_pdf.parse_pub_limits(_t("2026000457")) == GOLD["2026000457"]["fields"]["pub_limits"]
    row = "소득 해당 없음 (세대) 월평균소득 100% 이하 (맞벌이 200%) {mark} 전용면적 60㎡ 이하만 적용 자산(부동산, 자동차) 해당 없음 (세대) 부동산 215,500천원 이하 자동차 45,420천원 이하 <표2> 구분 자산보유기준 부동산 (건물+토지) 215,500천원 이하 건축물 자동차 45,420천원 이하 "
    for mark in ("*", "※"):
        pl = notice_pdf.parse_pub_limits(row.format(mark=mark))
        assert pl and pl["cap"] == [100, 200] and pl["area_max"] == 60 and (pl["real_estate"], pl["car"]) == (21550, 4542)
    # 다른 표시(■)는 받지 않는다 — 소득 칸과 자산 줄 사이에 모르는 글이 끼면 읽지 않음
    assert notice_pdf.parse_pub_limits(row.format(mark="■")) is None
