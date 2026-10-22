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


def test_urbty_bundle_keeps_only_private_rental(tmp_path, monkeypatch):
    """청약홈 '오피스텔·도시형·민간임대' 묶음에서 민간임대만 담는다 (기능 pvt_rental_urbty, 2026-10-22). 오피스텔·도시형생활주택은 분양이라 뺀다"""
    import json
    from datetime import datetime
    from app import pvt_rental as P
    base = {"RCRIT_PBLANC_DE": "2026-10-08", "SUBSCRPT_RCEPT_BGNDE": "2026-10-19", "SUBSCRPT_RCEPT_ENDDE": "2026-10-20", "PRZWNER_PRESNATN_DE": "2026-10-23",
            "HSSPLY_ADRES": "경기도 양주시 옥정동", "TOT_SUPLY_HSHLDCO": 100}
    urbty = [dict(base, PBLANC_NO="2026950077", HOUSE_NM="옥정 민간임대", HOUSE_DTL_SECD_NM="민간임대"),
             dict(base, PBLANC_NO="2026950086", HOUSE_NM="오산 오피스텔", HOUSE_DTL_SECD_NM="오피스텔"),
             dict(base, PBLANC_NO="2026950087", HOUSE_NM="당산 도시형", HOUSE_DTL_SECD_NM="도시형생활주택")]

    class C:
        def _get(self, path, **kw):
            if path == P.URBTY_DETAIL:
                return {"data": urbty if kw.get("page", 1) == 1 else []}
            if path == P.URBTY_MODEL:
                return {"data": [{"TP": "84A", "EXCLUSE_AR": "84.9", "SUPLY_HSHLDCO": 10}]}
            return {"data": []}
    monkeypatch.setattr(P, "ApplyhomeClient", C)
    monkeypatch.setattr(P, "OUT", tmp_path / "pvt.json")
    monkeypatch.setattr(P, "LOG", tmp_path / "log.txt")

    class D(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 22, 9, 0, tzinfo=tz)
    monkeypatch.setattr(P, "datetime", D)
    P.main()
    out = json.loads((tmp_path / "pvt.json").read_text(encoding="utf-8"))
    assert [n["name"] for n in out["notices"]] == ["옥정 민간임대"] and out["notices"][0]["type"] == "민간임대"
    assert out["notices"][0]["units"][0]["type"] == "84A" and out["notices"][0]["units"][0]["supply_amount"] is None   # 금액 칸이 없으면 지어내지 않음
    log = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert "민간임대 1건만 담음" in log and "[응답 필드] 민간임대 주택형" in log
