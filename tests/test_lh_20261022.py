"""2026-10-22 LH 임대 수집 복구 때 새로 들어온 공고 (원문: evidence/lh/0000061187.txt — 대구 대곡·옥포·테크노4 10년 공공임대 예비입주자)."""
import json
from pathlib import Path

from app.lh_terms import parse_lh_rents, parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
DAEGU = "0000061187"


def _texts(i):
    out = {"pypdf": (ROOT / "evidence/lh" / f"{i}.txt").read_text(encoding="utf-8")}
    for k in ("pdfium", "plumber"):
        p = ROOT / "evidence/lh" / k / f"{i}.txt"
        if p.exists():
            out[k] = p.read_text(encoding="utf-8")
    return out


def test_daegu_10yr_public_eligibility_all_tools():
    """신청자격: 대구·경북 무주택세대구성원 성년자, 청약저축·세대주·과거 당첨·소득·자산 불문 — 세 도구 글 모두 같은 값"""
    for tool, t in _texts(DAEGU).items():
        r = parse_lh_terms(t, "공공임대", "대곡", "대구광역시")
        assert r["regions"] == ["경북", "대구"], tool
        assert r["account"] == "none", tool
        (g,) = r["groups"]
        assert (g["homeless"], g["income_pct"], g["asset_manwon"], g["car_manwon"]) == ("household", "excluded", "excluded", "excluded"), tool
        assert "불문" in r["quotes"]["일반"]["income"], tool


def test_daegu_rents_by_complex_and_no_conversion_row():
    """임대조건은 단지별로(같은 59A 라도 단지마다 다름), '(-) 18,000,000 12,000,000 482,500'(최대 전환 시 칸)은 줄로 읽지 않는다"""
    rows = parse_lh_rents(_texts(DAEGU)["pypdf"], [])
    got = {(r["complex"], r["type"], r["deposit"], r["rent"]) for r in rows}
    assert ("수목원 호정포레스트", "59A", 46415000, 485740) in got
    assert ("수목원 풍경그린", "59A", 51500000, 463500) in got
    assert ("대구옥포 르상트레빌", "84A", 53000000, 490000) in got
    assert all(r["deposit"] != 18000000 for r in rows)
    assert all(r["complex"] for r in rows)
    assert len(rows) == 9


def test_org_target_notice_is_not_listed():
    """기관·기업을 모집하는 공고는 개인이 신청할 수 없어 목록에서 뺀다 (기장군 중소기업 근로자 기관공급 대상기업 모집)"""
    from app.lh_rental import org_target
    assert org_target("LH임대주택 기장군 중소기업 근로자 공공임대주택 기관공급 사업 대상기업 모집계획 공고")
    names = {n["name"] for n in json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"] if n.get("name")}
    for n in names | {"창원 행복주택 기관추천 예비입주자 모집", "산업단지 근로자 국민임대 입주자 모집", "[경기북부] 청년 매입임대주택 선착순 예비입주자 모집공고"}:
        assert not org_target(n), n


def test_apply_dates_from_text_when_date_cells_empty():
    """접수일 칸이 비어 있으면 접수 일시 글('2026.10.27 10:00 ~ 2026.10.29 17:00')에서 읽는다 — 안 그러면 공고 중인데 '접수 중'으로 보임"""
    from app.lh_rental import notice_record
    r = notice_record({"PAN_ID": "x"}, [{"dsSplScdl": [{"ACP_DTTM": "2026.10.27 10:00 ~ 2026.10.29 17:00"}]}], [])
    assert (r["schedule"][0]["apply_start"], r["schedule"][0]["apply_end"]) == ("2026-10-27", "2026-10-29")
    r = notice_record({"PAN_ID": "x"}, [{"dsSplScdl": [{"ACP_DTTM": "2026.10.27 10:00 ~ 17:00"}]}], [])
    assert r["schedule"][0]["apply_start"] is None   # 날짜 둘이 아니면 짐작하지 않음
