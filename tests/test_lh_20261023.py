"""2026-10-23 아침 자동 고치기 — 구리갈매 S1블록 10년 공공임대 예비입주자(0000061190, 원문 evidence/lh/0000061190.txt).
새 꼴: '신청자격 ▌예비입주자모집공고일(…) 현재 수도권(서울특별시, 경기도, 인천광역시)에 거주(주민등록표등본 기준)하는 성년자(만19세 이상)인 무주택세대구성원'
+ '신청자의 소득기준 및 자산기준 충족 여부는 불문' + 순위별 자격요건 표(1순위 2년·24회, 2순위 6월·6회)."""
from pathlib import Path

from app.lh_terms import _rank_account, flat, parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
GURI = "0000061190"


def _texts(i):
    out = {"pypdf": (ROOT / "evidence/lh" / f"{i}.txt").read_text(encoding="utf-8")}
    for k in ("pdfium", "plumber"):
        p = ROOT / "evidence/lh" / k / f"{i}.txt"
        if p.exists():
            out[k] = p.read_text(encoding="utf-8")
    return out


def test_guri_capital_area_eligibility_all_tools():
    """세 도구 글 모두: 거주지역 서울·경기·인천, 1순위 24개월·24회·2순위 6개월·6회, 소득·자산 불문, 세대 무주택"""
    for tool, t in _texts(GURI).items():
        r = parse_lh_terms(t, "공공임대", "구리갈매", "경기도")
        assert r["regions"] == ["경기", "서울", "인천"], tool
        assert r["account"] == {"months": 24, "count": 24, "rank2_any": False, "rank2": {"months": 6, "count": 6}}, tool
        (g,) = r["groups"]
        assert (g["homeless"], g["income_pct"], g["asset_manwon"], g["car_manwon"]) == ("household", "excluded", "excluded", "excluded"), tool
        assert "불문" in r["quotes"]["일반"]["income"], tool


def test_rank_table_rejects_bad_shapes():
    """순위 표는 1순위·2순위 한 줄씩, 1순위 기준이 2순위 이상일 때만 받는다 — 아니면 None(화면 '청약통장 요건 공고문 확인')"""
    row = "{r}순위 입주자저축(주택청약종합저축, 청약저축)에 가입하여 {m}이 경과된 분으로서 매월 약정납입일에 월 납입금을 {c}회 이상 납입한 자 "
    ok = row.format(r=1, m="2년", c=24) + row.format(r=2, m="6월", c=6)
    assert _rank_account(flat(ok))[0] == {"months": 24, "count": 24, "rank2_any": False, "rank2": {"months": 6, "count": 6}}
    assert _rank_account(flat(row.format(r=1, m="2년", c=24)))[0] is None                                  # 한 줄뿐
    assert _rank_account(flat(row.format(r=2, m="6월", c=6) + row.format(r=1, m="2년", c=24)))[0] is None   # 순서 뒤바뀜
    assert _rank_account(flat(row.format(r=1, m="6월", c=6) + row.format(r=2, m="2년", c=24)))[0] is None   # 1순위가 더 낮음
    assert _rank_account(flat(row.format(r=1, m="2년", c=24) + row.format(r=2, m="6월", c=6) + row.format(r=2, m="6월", c=6)))[0] is None   # 세 줄


def test_capital_rule_needs_sido_names_and_no_income_sentence():
    """괄호 안이 시·도 이름이 아니거나(시·군 섞임) 소득·자산 불문 문장이 없으면 읽지 않는다"""
    t = flat(_texts(GURI)["pypdf"])
    assert parse_lh_terms(t.replace("경기도, 인천광역시", "구리시, 인천광역시"), "공공임대", "구리갈매", "경기도")["groups"] == []
    assert parse_lh_terms(t.replace("자산기준 충족 여부는 불문", "자산기준 충족 여부를 확인"), "공공임대", "구리갈매", "경기도")["groups"] == []
