"""거주 지역 요건 (기능: residence_v2) — 실제 모집공고문 원문으로 확인한 정답과 추출 결과 비교.

정답(tests/golden/notices.json 의 fields.residence)은 evidence/notices/*.txt(공고문 PDF 원문 텍스트)의
'해당지역·기타지역' 표, LH '지역우선 공급기준' 표, 무순위 '대상자' 문장을 읽고 확인한 값이다.
"""
import json
import pathlib

from app import notice_pdf, pipeline
from app.models import Listing

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
RES = {k: v for k, v in GOLD.items() if "residence" in v["fields"]}


def text(no):
    return (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_golden_residence_from_real_notices():
    assert len(RES) >= 15
    for no, g in RES.items():
        assert notice_pdf.parse_residence(text(no)) == g["fields"]["residence"], no
        assert notice_pdf.parse_notice(text(no)).get("residence") == g["fields"]["residence"], no


def test_residence_quotes_in_originals():
    """정답이 기대는 원문 문장이 실제 공고문에 있다 (공백만 정리)."""
    q = {
        "2026000399": "서울특별시 2년 이상 계속 거주자 (2024.08.28. 이전부터 계속 거주) 서울특별시 2년 미만 거주자, 경기도 및 인천광역시 거주자",
        "2026000437": "경기도 6개월 이상 거주자 (2026.03.11. 이전부터 계속 거주) 경기도 6개월 미만 거주자 및 전국 거주자",
        "2026000445": "전주시 1년 미만 계속 거주자 및 전북특별자치도 거주자",
        "2026820008": "해당 주택건설지역 (성남시) 100%",
        "2026910220": "입주자모집공고일 현재 전국에 거주하는 무주택세대구성원",
        "2026910234": "입주자모집공고일 현재 부산광역시 및 울산광역시, 경상남도에 거주하는 무주택세대구성원",
    }
    import re
    for no, s in q.items():
        assert s in re.sub(r"\s+", " ", text(no)), no


def test_every_evidence_notice_reads_or_none():
    """모아 둔 공고문 56건 모두 오류 없이 읽고, 읽은 값은 형식이 맞다 (못 읽으면 None — 추측하지 않음)."""
    n = 0
    for f in sorted((ROOT / "evidence" / "notices").glob("*.txt")):
        r = notice_pdf.parse_residence(f.read_text(encoding="utf-8"))
        if r is None:
            continue
        n += 1
        assert r["area"] is None or r["area"].get("sido") or r["area"].get("sigungu"), f.name
        assert r["months"] in (0, 6, 12, 24, 36), f.name
        assert (r["since"] is None) == (r["months"] == 0), f.name
        assert all(x in ("전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
                         "전북", "전남", "경북", "경남", "제주") for x in r["others"]), f.name
    assert n >= 50


def test_pipeline_keeps_residence_from_previous_run():
    prev = {"from_notice": ["거주 지역 요건"], "residence": {"area": {"name": "서울특별시", "sido": "서울"}, "months": 24}}
    found, _ = pipeline._from_previous(prev)
    assert found["residence"]["months"] == 24


def test_listing_has_residence_field():
    assert "residence" in Listing.model_fields
