"""공공임대 공고 (기능: rental_rules, 2026-10-02 MASTER QA QA-02·03) — 실제 공고문 원문으로 검증."""
import json
import pathlib
from datetime import date

from app import notice_pdf, pipeline

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))


def text(no):
    return (ROOT / "evidence" / "qa" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_golden_rental_limits_from_real_notice():
    """2026000307 원문의 일반공급 소득(외벌이·맞벌이·1인·2인)·우선공급·총자산·출산가구 완화가 정답과 같다."""
    got = notice_pdf.parse_notice(text("2026000307"))
    want = GOLD["2026000307"]["fields"]
    assert got["pub_limits"] == want["pub_limits"]
    assert got["account_months"] == want["account_months"] and got["deposit_count"] == want["deposit_count"]


def test_total_asset_parse_does_not_touch_other_notices():
    """총자산형 읽기를 더해도 다른 공고문(공공분양·신혼희망타운·민영)의 소득·자산 기준은 그대로다."""
    for f in sorted([*(ROOT / "evidence" / "notices").glob("*.txt"), *(ROOT / "evidence" / "qa" / "notices").glob("*.txt")]):
        if f.stem == "2026000307":
            continue
        pl = notice_pdf.parse_pub_limits(f.read_text(encoding="utf-8"))
        assert not pl or pl.get("kind") != "total", f.stem


def test_is_rental():
    assert pipeline.is_rental({"rent_secd": "분양전환 가능임대", "name": "x"})
    assert not pipeline.is_rental({"rent_secd": "분양주택", "name": "군산 세경아파트 우선분양전환 후 잔여세대"})   # 분양 (2026000274 원문)
    assert pipeline.is_rental({"name": "이천시 장호원읍 5년 공공건설임대주택(카사펠리스이천) 임차인모집"})          # 2025000645 원문 '임차인모집'
    assert not pipeline.is_rental({"name": "마곡지구 17단지 토지임대부(본청약)"})                                # 토지임대부는 분양 (2026000041)
    assert not pipeline.is_rental({"name": "인천계양지구 A6블록 공공분양주택(본청약)"})


def test_rental_listing_has_no_margin(monkeypatch):
    """임대 공고는 청약홈 금액이 임대보증금이라 시세 차익을 계산하지 않는다."""
    raw = {"notice_no": "2026000307", "name": "군포대야미지구 A-1블록 6년 분양전환공공임대주택(본청약)", "address": "경기도 군포시 대야미동 일원",
           "kind": "APT", "category": "general", "house_ty": "055.0000A", "unit": "55A", "area": 55.0, "households": 1, "special_units": None,
           "notice": "2026-06-30", "apply": "2026-07-22", "apply_end": "2026-07-24", "winner": "2026-08-05", "contract": None, "move_in": None,
           "price": 0.8561, "rent_secd": "분양전환 가능임대", "house_dtl": "국민", "supply_type": "APT"}
    called = []
    class R:
        def recent(self, *a):
            called.append(a); return []
    L = pipeline.build_listing(raw, R(), date(2026, 7, 1), {})
    assert L.rental and L.mkt_low is None and "임대보증금" in L.mkt_note and not called
    monkeypatch.setattr(pipeline, "feature_on", lambda n: n != "rental_rules")
    L2 = pipeline.build_listing(raw, None, date(2026, 7, 1), {})
    assert not L2.rental


def test_rental_sp_table_only_when_consistent():
    """공공임대 특별공급 소득표 (기능: rental_special). 원문 2026000307 은 5개 유형을 모두 읽고(정답은 golden pub_limits.sp),
    단계 비율 합이 100이 아니거나 금액 칸 수가 맞지 않으면 그 유형은 읽지 않는다 (추측 금지). 공공분양·민영 공고문에는 이 표가 없다."""
    import re
    t = (ROOT / "evidence" / "qa" / "notices" / "2026000307.txt").read_text(encoding="utf-8")
    f = re.sub(r"\s+", "", t)
    sp = notice_pdf._rental_sp_table(f)
    assert set(sp) == {"newlywed", "newborn", "first", "elder", "multichild"}
    assert "2" not in sp["multichild"]["amt"]   # 다자녀는 2인 표에 없음
    broken = f.replace("신혼부부특별공급우선공급(70%)", "신혼부부특별공급우선공급(60%)")   # 비율 합 90
    assert "newlywed" not in (notice_pdf._rental_sp_table(broken) or {})
    cut = f.replace("11,064,819도시근로자가구원수별가구당월평균소득액의120%", "도시근로자가구원수별가구당월평균소득액의120%", 1)   # 8인 칸 하나 빠짐
    assert notice_pdf._rental_sp_table(cut) != sp
    for g in sorted((ROOT / "evidence" / "notices").glob("*.txt")):
        assert notice_pdf._rental_sp_table(re.sub(r"\s+", "", g.read_text(encoding="utf-8"))) is None, g.stem
