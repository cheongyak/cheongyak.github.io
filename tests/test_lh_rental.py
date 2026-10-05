"""LH 임대 수집(app/lh_rental.py) — 실제 API 응답 고정본(tests/qa/lh/, 2026-10-05 lh-probe)으로 변환을 확인한다.
기존 청약 판정과 분리돼 있는지도 본다(파이프라인이 이 모듈을 가져오지 않음)."""
import json
from pathlib import Path

from app.lh_rental import notice_record, _d

D = Path(__file__).parent / "qa" / "lh"


def _rec(kind):
    dtl = next(D.glob(f"상세-{kind}-*.json")); pid = dtl.stem.split("-")[-1]
    row = next(r for r in json.loads((D / "list.json").read_text(encoding="utf-8")) if r["PAN_ID"] == pid)
    return notice_record(row, json.loads(dtl.read_text(encoding="utf-8")), json.loads((D / f"공급-{kind}-{pid}.json").read_text(encoding="utf-8")))


def test_integrated_rental_record():
    r = _rec("통합공공임대")
    assert r["type"] == "통합공공임대" and r["judge_type"]
    assert len(r["schedule"]) == 2 and r["schedule"][0]["apply_start"] == "2026-10-13" and r["schedule"][0]["winner"] == "2027-04-02"
    assert {c["households"] for c in r["complexes"]} == {622, 526}
    u = r["units"][0]
    assert (u["type"], u["area"], u["households"]) == ("31A", 31.86, 262)
    # API 가 '공고문 참조'로 준 금액은 만들지 않는다
    assert u["deposit"] is None and u["rent"] is None and u["money_note"] == "공고문 참조"
    assert r["notice_pdf"].startswith("https://apply.lh.or.kr/") and "fileid=68787450" in r["notice_pdf"]


def test_happy_house_record():
    r = _rec("행복주택")
    assert r["type"] == "행복주택" and r["region"] == "전북특별자치도" and r["units"]


def test_date():
    assert _d("2026.10.13") == "2026-10-13" and _d("20261013") == "2026-10-13" and _d("") is None


def test_pipeline_does_not_import_lh_rental():
    for f in ("app/pipeline.py", "app/notice_pdf.py", "app/validate.py"):
        assert "lh_rental" not in Path(f).read_text(encoding="utf-8")
