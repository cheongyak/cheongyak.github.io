"""청약홈 공공지원 민간임대 (app/pvt_rental.py, 기능 pvt_rental, 2026-10-21) — evidence/qa/pvt-rent-probe.json 의 실제 응답으로 레코드 만들기.
금액 뜻은 청약홈 공고 화면(울산반구 수자인 더센트럴 2026850052)과 대조: 84A 공급금액 39,060만원·청약신청금 10만원, 84A-1 특별공급 청년 1·신혼부부 1."""
import json
from pathlib import Path

from app.pvt_rental import record

ROOT = Path(__file__).resolve().parents[1]


def test_record_matches_applyhome_screen():
    d = json.loads((ROOT / "evidence/qa/pvt-rent-probe.json").read_text(encoding="utf-8"))["공공지원 민간임대"]
    row = next(x for x in d["open"] + d.get("first_rows", []) if str(x["PBLANC_NO"]) == "2026850052")
    r = record(row, d["models"]["2026850052"])
    assert r["id"] == "PVT-2026850052" and r["org"] == "PVT" and r["region"] == "울산광역시" and not r["judge_type"]
    assert r["schedule"][0]["apply_start"] == "2026-10-20" and r["schedule"][0]["apply_end"] == "2026-10-21" and r["schedule"][0]["winner"] == "2026-10-26"
    U = {u["type"]: u for u in r["units"]}
    assert (U["84A"]["supply_amount"], U["84A"]["apply_fee"], U["84A"]["households"]) == (39060, 10, 58)
    assert U["84A-1"]["special"] == {"청년": 1, "신혼부부": 1, "고령자": 0} and U["84A-1"]["supply_amount"] == 33870
    assert all(u["deposit"] is None and u["rent"] is None for u in r["units"])   # 임대보증금·월세는 API 에 없음 — 지어내지 않음
