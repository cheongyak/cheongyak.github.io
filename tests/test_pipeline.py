"""가짜 API 응답(형태만 실제와 같게 만든 목업)으로 수집 → 시세 → 등급 → API 서버까지 끝까지 돌려본다."""
import json
from datetime import date

import httpx
from fastapi.testclient import TestClient

from app import pipeline
from app.sources.applyhome import ApplyhomeClient, normalize, to_date, unit_label
from app.sources.rtms import RtmsClient, parse_items

DETAIL = {"PBLANC_NO": "2026930040", "HOUSE_MANAGE_NO": "2026930040", "HOUSE_NM": "강변역 센트럴 아이파크",
          "HSSPLY_ADRES": "서울특별시 광진구 구의동 592-39번지 일원", "HOUSE_SECD_NM": "불법행위 재공급",
          "RCRIT_PBLANC_DE": "2026-09-23", "SUBSCRPT_RCEPT_BGNDE": "2026-10-06", "SUBSCRPT_RCEPT_ENDDE": "2026-10-06",
          "PRZWNER_PRESNATN_DE": "2026-10-12", "PBLANC_URL": "https://www.applyhome.co.kr/"}
MODEL = {"PBLANC_NO": "2026930040", "HOUSE_TY": "084.9811C", "LTTOT_TOP_AMOUNT": "122,202", "SUPLY_HSHLDCO": "1"}


def xml(items: list[dict]) -> str:
    body = "".join("<item>" + "".join(f"<{k}>{v}</{k}>" for k, v in it.items()) + "</item>" for it in items)
    return (f"<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
            f"<body><items>{body}</items></body></response>")


PRESALE = [{"aptNm": "강변역센트럴아이파크", "excluUseAr": "84.98", "dealAmount": a, "dealYear": "2026", "dealMonth": "8",
            "dealDay": "10", "ownershipGbn": "분양권", "cdealType": ""} for a in ("220,000", "215,000", "205,000", "225,000")]
PRESALE.append({**PRESALE[0], "dealAmount": "150,000", "cdealType": "O"})  # 해제 거래는 빠져야 함
RENT = [{"aptNm": "강변역센트럴아이파크", "excluUseAr": "84.98", "deposit": d, "monthlyRent": "0", "buildYear": "2026",
         "dealYear": "2026", "dealMonth": "9", "dealDay": "1"} for d in ("80,000", "78,000", "85,000")]


def handler(req: httpx.Request) -> httpx.Response:
    u = str(req.url)
    if "odcloud" in u:
        if "getRemndrLttotPblancDetail" in u:
            return httpx.Response(200, json={"data": [DETAIL]})
        if "getRemndrLttotPblancMdl" in u:
            return httpx.Response(200, json={"data": [MODEL]})
        return httpx.Response(200, json={"data": []})
    if "SilvTrade" in u:
        return httpx.Response(200, text=xml(PRESALE if "202608" in u else []))
    if "AptRent" in u:
        return httpx.Response(200, text=xml(RENT if "202609" in u else []))
    return httpx.Response(200, text=xml([]))


def clients():
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ApplyhomeClient("TEST", http), RtmsClient("TEST", http)


# 2026-09-29 실제 무순위 개요 응답 1건 (브라우저로 받은 것 그대로)
REAL_REMNDR = {"BSNS_MBY_NM": "(주)이노디앤씨", "CNTRCT_CNCLS_BGNDE": "2026-10-17", "CNTRCT_CNCLS_ENDDE": "2026-10-17",
    "GNRL_RCEPT_BGNDE": None, "GNRL_RCEPT_ENDDE": None, "HMPG_ADRES": "https://충정로역자이르네.com",
    "HOUSE_MANAGE_NO": "2026910251", "HOUSE_NM": "충정로역자이르네", "HOUSE_SECD": "04", "HOUSE_SECD_NM": "무순위",
    "HSSPLY_ADRES": "서울특별시 중구 중림동 157-2번지 일원", "HSSPLY_ZIP": "04504", "MDHS_TELNO": "16601245",
    "MVN_PREARNGE_YM": "203005", "NSPRC_NM": None, "PBLANC_NO": "2026910251",
    "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectAPTRemndrLttotPblancDetailView.do?houseManageNo=2026910251&pblancNo=2026910251",
    "PRZWNER_PRESNATN_DE": "2026-10-12", "RCRIT_PBLANC_DE": "2026-09-28", "SPSPLY_RCEPT_BGNDE": None,
    "SPSPLY_RCEPT_ENDDE": None, "SUBSCRPT_AREA_CODE": "100", "SUBSCRPT_AREA_CODE_NM": "서울",
    "SUBSCRPT_RCEPT_BGNDE": "2026-10-06", "SUBSCRPT_RCEPT_ENDDE": "2026-10-06", "TOT_SUPLY_HSHLDCO": 35}


def test_real_remainder_record():
    n = normalize(REAL_REMNDR, {"HOUSE_TY": "059.9900A", "LTTOT_TOP_AMOUNT": "100000"}, "remainder")
    assert n["name"] == "충정로역자이르네" and n["kind"] == "무순위"
    assert n["notice"] == "2026-09-28" and n["apply"] == "2026-10-06" and n["winner"] == "2026-10-12"
    assert n["contract"] == "2026-10-17" and n["move_in"] == "2030-05" and n["total_households"] == 35
    assert n["speculative"] is None      # 무순위 개요엔 규제 필드가 없다 → 주소로 판정
    from app import region
    assert region.sigungu_of(n["address"]) == "중구" and region.is_regulated(n["address"])


def test_parsers():
    n = normalize(DETAIL, MODEL, "remainder")
    assert n["price"] == 12.2202 and n["unit"] == "84C" and n["notice"] == "2026-09-23"
    assert unit_label("059.9222") == "59"
    rows = parse_items(xml(PRESALE))
    assert len(rows) == 4 and rows[0]["amount"] == 220000


def test_end_to_end(tmp_path, monkeypatch):
    ah, rt = clients()
    monkeypatch.setattr(pipeline, "ApplyhomeClient", lambda: ah)
    monkeypatch.setattr(pipeline, "RtmsClient", lambda: rt)
    monkeypatch.setattr(pipeline, "DATA", tmp_path / "listings.json")
    monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "run-log.txt")
    monkeypatch.setattr(pipeline.notify, "send", lambda msgs, cfg: [f"sent {len(msgs)}"])
    out = pipeline.run(today=date(2026, 9, 29), read_notices=False)
    assert len(out) == 1
    assert "로또" in (tmp_path / "run-log.txt").read_text(encoding="utf-8")
    L = out[0]
    assert L.regulated and L.land_permit and L.sigungu == "광진구"
    assert L.mkt_base == 21.75 and L.mkt_low == 21.25
    assert L.jeonse == 7.2
    assert L.mkt_basis == "same_complex" and L.mkt_count == 4 and len(L.mkt_comps) == 4
    assert L.mkt_comps[0]["kind"] == "분양권" and L.mkt_comps[0]["amount"] in (22.0, 21.5, 20.5, 22.5)
    assert all(c["amount"] != 15.0 for c in L.mkt_comps)          # 해제 거래는 근거에서도 빠진다
    assert len(L.jeonse_comps) == 3 and L.jeonse_comps[0]["kind"] == "전세"

    monkeypatch.setenv("LISTINGS_PATH", str(tmp_path / "listings.json"))
    from app.api import app
    c = TestClient(app)
    rows = c.get("/listings").json()
    assert rows[0]["grade"]["name"] == "로또"
    body = {"profile": {"household": "parents", "parents60": True, "parentsOwn": True, "cash": 32500, "income": 4000}}
    j = c.post(f"/listings/{L.id}/judge", json=body).json()
    assert j["verdict"] == "신청 불가"
    assert j["funding"]["jeonse_check"]["status"] == "cond"


def test_rtms_forbidden_keeps_listing(tmp_path, monkeypatch):
    def h(req):
        u = str(req.url)
        if "getRemndrLttotPblancDetail" in u:
            return httpx.Response(200, json={"data": [DETAIL]})
        if "getRemndrLttotPblancMdl" in u:
            return httpx.Response(200, json={"data": [MODEL]})
        if "odcloud" in u:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(403, text="Forbidden")
    http = httpx.Client(transport=httpx.MockTransport(h))
    monkeypatch.setattr(pipeline, "ApplyhomeClient", lambda: ApplyhomeClient("T", http))
    monkeypatch.setattr(pipeline, "RtmsClient", lambda: RtmsClient("T", http))
    monkeypatch.setattr(pipeline, "DATA", tmp_path / "l.json")
    monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "run-log.txt")
    monkeypatch.setattr(pipeline.notify, "send", lambda msgs, cfg: [])
    out = pipeline.run(today=date(2026, 9, 29), read_notices=False)
    assert len(out) == 1 and out[0].mkt_base is None
    assert "실패" in out[0].mkt_note


def test_incheon_lawd():
    from app import region
    a = "인천광역시 계양구 계양동 일원"
    assert region.sigungu_of(a) == "인천 계양구" and region.lawd_of("인천 계양구") == "28245"
    assert not region.is_regulated(a) and region.is_capital(a)


def test_sido_and_district():
    from app import region
    assert region.sido_of("서울특별시 광진구 구의동") == "서울"
    assert region.sido_of("전북특별자치도 전주시 완산구 삼천동") == "전북"
    assert region.sigungu_any("전북특별자치도 전주시 완산구 삼천동") == "전주시 완산구"
    assert region.sigungu_any("경상남도 진주시 판문동") == "진주시"
    assert region.sigungu_any("인천광역시 계양구 계양동") == "계양구"
    assert region.sigungu_any("세종특별자치시 어진동") is None


def test_api_filters(tmp_path, monkeypatch):
    ah, rt = clients()
    monkeypatch.setattr(pipeline, "ApplyhomeClient", lambda: ah)
    monkeypatch.setattr(pipeline, "RtmsClient", lambda: rt)
    monkeypatch.setattr(pipeline, "DATA", tmp_path / "listings.json")
    monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "run-log.txt")
    monkeypatch.setattr(pipeline.notify, "send", lambda msgs, cfg: [])
    out = pipeline.run(today=date(2026, 9, 29), read_notices=False)
    L = out[0]
    assert L.sido == "서울" and L.district == "광진구" and L.supply_type == "불법행위 재공급"
    assert "[응답 필드] remainder 개요" in (tmp_path / "run-log.txt").read_text(encoding="utf-8")
    monkeypatch.setenv("LISTINGS_PATH", str(tmp_path / "listings.json"))
    from app.api import app
    c = TestClient(app)
    assert len(c.get("/listings", params={"sido": "서울", "district": "광진구"}).json()) == 1
    assert len(c.get("/listings", params={"sido": "부산"}).json()) == 0
    assert len(c.get("/listings", params={"date_field": "apply", "date_from": "2026-10-01", "date_to": "2026-10-31"}).json()) == 1
    assert len(c.get("/listings", params={"date_field": "apply", "date_to": "2026-09-30"}).json()) == 0
    assert c.get("/listings", params={"date_field": "bad"}).status_code == 400
