"""단지 규모(총세대·동 수)·나홀로 3상태 (기능: complex_size, 청약봇 V2 STEP 0-2). 정답은 모집공고문 원문 '공급규모' 문장을 사람이 읽고 넣은 값."""
import json
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))


def test_golden_complex_from_real_notices():
    cases = {k: v["fields"]["complex"] for k, v in GOLD.items() if "complex" in v.get("fields", {})}
    assert len(cases) >= 10
    for nid, want in cases.items():
        got = notice_pdf.parse_complex((ROOT / "evidence" / "notices" / f"{nid}.txt").read_text(encoding="utf-8"))
        if want["households"] is None:
            assert got is None, nid          # 숫자가 흐트러진 공고문은 읽지 않는다 (확인 불가)
        else:
            assert got and (got["households"], got["buildings"]) == (want["households"], want["buildings"]), nid


def test_scrambled_numbers_are_not_guessed():
    t = "■ 공급규모 아파트 지하 층 지상 층 개동 총 세대 중 : 3 , 30~38 , 7 1,191 잔여 세대2"
    assert notice_pdf.parse_complex(t) is None


def test_public_and_newlywed_town_wording():
    assert notice_pdf.parse_complex("1. 공급규모 ■ 의정부우정지구 A-2블록 : 공공분양주택 19∼20층 6개동 전용면적 60㎡ 이하 463세대 2. 공급대상")["households"] == 463
    c = notice_pdf.parse_complex("1. 공급규모 ■ 남양주진접2지구 A-4블록 448세대 중 신혼희망타운(공공분양) 전용면적 60㎡이하 5세대")
    assert c == {"households": 448, "buildings": None, "quote": c["quote"]}


def test_single_status_three_states():
    s = notice_pdf.single_status
    assert s({"households": 1149, "buildings": 17}) == "no"
    assert s({"households": 2, "buildings": 2}) == "no"
    assert s({"households": 118, "buildings": 1}) == "maybe"     # 1개 동: 가능성 있음(단정하지 않음)
    assert s({"households": 99, "buildings": None}) == "maybe"
    assert s({"households": 100, "buildings": None}) == "unknown"
    assert s({"households": 448, "buildings": None}) == "unknown"
    assert s(None) == "unknown"
