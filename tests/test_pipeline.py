"""가짜 API 응답(형태만 실제와 같게 만든 목업)으로 수집 → 시세 → 등급 → API 서버까지 끝까지 돌려본다."""
import json
from pathlib import Path
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
            "dealDay": "10", "ownershipGbn": "분", "cdealType": ""} for a in ("220,000", "215,000", "205,000", "225,000")]
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


def test_direct_deals_excluded():
    from app.market import estimate_market
    t = [{"apt": "A", "area": 84.9, "amount": a, "deal_type": d, "build_year": 2024, "date": "2026-09-01"}
         for a, d in ((100000, "중개거래"), (101000, "중개거래"), (99000, "중개거래"), (50000, "직거래"))]
    t.append({"apt": "C", "area": 59.9, "amount": 30000, "deal_type": "직거래", "build_year": 2024, "date": "2026-09-01"})
    m = estimate_market("B", 84.9, t, [], 2026)
    assert m["mkt_count"] == 3 and m["mkt_direct_excluded"] == 1 and m["mkt_base"] == 10.0   # 다른 평형 직거래는 안 센다
    assert all(not c["direct"] for c in m["mkt_comps"])


def test_trade_dong():
    rows = parse_items(xml([{"aptNm": "A", "excluUseAr": "84.9", "dealAmount": "100,000", "floor": "7", "aptDong": "101동",
                             "dealYear": "2026", "dealMonth": "9", "dealDay": "1"}]))
    assert rows[0]["dong"] == "101동" and rows[0]["floor"] == 7


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
    out = pipeline.run(today=date(2026, 9, 29), read_notices=False)
    assert len(out) == 1
    assert "로또" in (tmp_path / "run-log.txt").read_text(encoding="utf-8")
    import re
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d\n", pipeline.FRESH.read_text(encoding="utf-8"))   # 정상 수집이면 시각을 남긴다
    L = out[0]
    assert L.regulated and L.land_permit and L.sigungu == "광진구"
    assert L.mkt_base == 21.75 and L.mkt_low == 21.25
    assert L.jeonse == 7.2
    assert L.mkt_basis == "same_complex" and L.mkt_count == 4 and len(L.mkt_comps) == 4
    assert L.mkt_comps[0]["kind"] == "분양권" and "dong" in L.mkt_comps[0] and L.mkt_comps[0]["amount"] in (22.0, 21.5, 20.5, 22.5)
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


def test_prefetch_budget_freezes():
    import time
    def slow(req):
        time.sleep(0.3)
        return httpx.Response(200, text=xml([]))
    rt = RtmsClient("T", httpx.Client(transport=httpx.MockTransport(slow)))
    keys = [("trade", "11215", f"2026{m:02d}") for m in range(1, 13)]
    r = rt.prefetch(keys, budget_sec=0.5, workers=2)
    assert r["skipped"] > 0 and rt.frozen
    import pytest
    from app.sources.rtms import RtmsError
    with pytest.raises(RtmsError):
        rt.fetch("rent", "11215", "202601")


def test_empty_api_result_keeps_previous_listings(tmp_path, monkeypatch):
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": []})))
    monkeypatch.setattr(pipeline, "ApplyhomeClient", lambda: ApplyhomeClient("T", http))
    monkeypatch.setattr(pipeline, "RtmsClient", lambda: RtmsClient("T", http))
    prev = tmp_path / "prev.json"
    prev.write_text('[{"id": "1-084.0000A", "name": "지난 공고"}]', encoding="utf-8")
    monkeypatch.setattr(pipeline.notify, "PREVIOUS", prev)
    monkeypatch.setattr(pipeline, "DATA", tmp_path / "l.json")
    monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "run-log.txt")
    sent = []
    fresh = pipeline.FRESH
    fresh.write_text("2026-09-29 05:31\n", encoding="utf-8")
    assert pipeline.run(today=date(2026, 9, 30)) == []
    assert fresh.read_text(encoding="utf-8") == "2026-09-29 05:31\n"   # 0건 실행은 마지막 정상 갱신 시각을 바꾸지 않는다
    assert "지난 공고" in (tmp_path / "l.json").read_text(encoding="utf-8")
    assert "[경고]" in (tmp_path / "run-log.txt").read_text(encoding="utf-8") and not sent


def test_feature_switch(monkeypatch):
    monkeypatch.setattr(pipeline.notify, "load_config", lambda: {"features": {"competition": False}})
    assert pipeline.feature_on("competition") is False
    assert pipeline.feature_on("nearby") is True          # 적혀 있지 않으면 켜짐


def test_special_units_from_model():
    # 2026-09-30 실행 기록 [응답 필드] general 주택형 의 실제 필드 이름
    from app.sources.applyhome import normalize, special_units
    model = {"HOUSE_TY": "084.9800A", "LTTOT_TOP_AMOUNT": "90000", "SUPLY_HSHLDCO": "40", "SPSPLY_HSHLDCO": "52",
             "NWBB_HSHLDCO": "5", "NWWDS_HSHLDCO": "8", "LFE_FRST_HSHLDCO": "4", "MNYCH_HSHLDCO": "5",
             "OLD_PARNTS_SUPORT_HSHLDCO": "1", "INSTT_RECOMEND_HSHLDCO": "5", "TRANSR_INSTT_ENFSN_HSHLDCO": "0",
             "YGMN_HSHLDCO": "0", "ETC_HSHLDCO": "0"}
    su = special_units(model)
    assert su["newborn"] == 5 and su["newlywed"] == 8 and su["first"] == 4 and su["multichild"] == 5
    assert su["elder"] == 1 and su["agency"] == 5 and su["total"] == 52
    assert normalize(DETAIL, model, "general")["special_units"] == su
    # 무순위 주택형 응답에는 유형별 필드가 없다 → None
    assert special_units({"HOUSE_TY": "059.99A", "SPSPLY_HSHLDCO": "0", "SUPLY_HSHLDCO": "1"}) is None


def test_market_fallback_uses_last_success(tmp_path):
    from datetime import date
    from app.pipeline import market_fallback, MARKET_FAIL_NOTE
    from app.models import Listing
    base = dict(name="가", address="서울특별시 광진구 구의동 1", region="서울", kind="일반", category="general", unit="84A", price=10.0)
    ok = Listing(id="1-84A", mkt_low=12.0, mkt_base=13.0, mkt_note="같은 구 매매 20건", mkt_count=20, **base)
    cache = tmp_path / "m.json"
    log = []
    market_fallback([ok], date(2026, 9, 29), log, cache)          # 성공 → 기록
    bad = Listing(id="1-84A", mkt_note=MARKET_FAIL_NOTE, **base)
    fresh = Listing(id="2-59A", mkt_note=MARKET_FAIL_NOTE, **base)
    market_fallback([bad, fresh], date(2026, 9, 30), log, cache)  # 실패 → 지난 값
    assert bad.mkt_base == 13.0 and bad.mkt_low == 12.0 and "09월 29일 조회값" in bad.mkt_note
    assert fresh.mkt_base is None
    assert any("지난 조회값 사용 1건" in m for m in log)


def test_rtms_error_hides_key():
    from app.sources.rtms import safe_msg
    e = RuntimeError("Client error '500' for url 'https://apis.data.go.kr/x?serviceKey=SECRET123&LAWD_CD=11740'")
    m = safe_msg(e)
    assert "SECRET123" not in m and "serviceKey=***" in m


def test_rtms_retries_transient_errors(monkeypatch):
    import app.sources.rtms as rtms_mod
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}
    ok_xml = "<response><header><resultCode>000</resultCode></header><body><items></items></body></response>"
    def h(req):
        calls["n"] += 1
        return httpx.Response(500, text="err") if calls["n"] < 3 else httpx.Response(200, text=ok_xml)
    c = rtms_mod.RtmsClient("T", httpx.Client(transport=httpx.MockTransport(h)))
    assert c.fetch("trade", "11740", "202609") == [] and calls["n"] == 3


def test_market_cache_kept_when_no_listings(tmp_path):
    """청약홈이 0건을 준 실행에서 시세 기록(market-cache.json)을 비우지 않는다."""
    p = tmp_path / "market-cache.json"
    p.write_text('{"a": {"mkt_low": 1, "date": "2026-09-30"}}', encoding="utf-8")
    pipeline.market_fallback([], __import__("datetime").date(2026, 10, 1), [], path=p)
    assert "a" in __import__("json").loads(p.read_text(encoding="utf-8"))


def _row(i, cat, apply_end, winner):
    from app.models import Listing
    L = Listing(id=f"{i}-084.0000A", name=f"공고{i}", address="서울특별시 광진구", region="서울", sigungu="광진구",
                category=cat, kind="무순위" if cat == "remainder" else "민영", unit="84A", price=10.0, mkt_low=11.0, mkt_base=12.0, apply=apply_end, apply_end=apply_end,
                winner=winner, url="https://www.applyhome.co.kr/x")
    return L.model_dump()


def test_restore_category_when_one_category_returns_zero():
    """일반분양만 받고 무순위가 0건이면, 아직 접수·발표 중인 지난 무순위 결과를 유지한다 (00:59 실행 재현)."""
    from app.models import Listing
    today = date(2026, 10, 1)
    out = [Listing(**_row(1, "general", "2026-10-02", "2026-10-10"))]
    prev = [_row(1, "general", "2026-10-02", "2026-10-10"), _row(2, "remainder", "2026-10-06", "2026-10-12"),
            _row(3, "remainder", "2026-09-01", "2026-09-05")]   # 3번은 발표 후 14일 지남 → 되살리지 않음
    log = []
    n = pipeline.restore_missing_category(out, prev, today, log)
    assert n == 1 and {L.id for L in out} == {"1-084.0000A", "2-084.0000A"}
    assert any("무순위" in l and "0건" in l for l in log)


def test_no_restore_when_category_really_empty():
    """지난 무순위 공고가 모두 보관 기간을 지났으면 0건이 정상일 수 있어 되살리지 않는다."""
    from app.models import Listing
    today = date(2026, 10, 1)
    out = [Listing(**_row(1, "general", "2026-10-02", "2026-10-10"))]
    prev = [_row(3, "remainder", "2026-09-01", "2026-09-05")]
    assert pipeline.restore_missing_category(out, prev, today, []) == 0 and len(out) == 1


def test_no_restore_when_category_present():
    from app.models import Listing
    today = date(2026, 10, 1)
    out = [Listing(**_row(1, "general", "2026-10-02", "2026-10-10")), Listing(**_row(4, "remainder", "2026-10-06", "2026-10-12"))]
    prev = [_row(2, "remainder", "2026-10-06", "2026-10-12")]
    assert pipeline.restore_missing_category(out, prev, today, []) == 0 and len(out) == 2


def test_bad_api_response_does_not_overwrite_previous(tmp_path, monkeypatch):
    """청약홈이 HTML·500·타임아웃을 주면 실행이 실패하고(워크플로 저장 단계가 돌지 않음) 지난 결과·갱신 시각을 덮어쓰지 않는다."""
    import pytest
    for handler in (lambda r: httpx.Response(200, text="<html>error</html>"),
                    lambda r: httpx.Response(500, text="err")):
        http = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(pipeline, "ApplyhomeClient", lambda: ApplyhomeClient("T", http))
        monkeypatch.setattr(pipeline, "RtmsClient", lambda: RtmsClient("T", http))
        monkeypatch.setattr(pipeline, "DATA", tmp_path / "l.json")
        monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "run-log.txt")
        with pytest.raises(Exception):
            pipeline.run(today=date(2026, 10, 1), read_notices=False)
        assert not (tmp_path / "l.json").exists() and not pipeline.FRESH.exists()


def test_crosscheck_all_evidence_notices_match_app_constants():
    """공고문 대조 (기능: notice_crosscheck) — 보관된 모집공고문 원문 전체의 소득 기준표·예치금 표·자산 기준이 화면 고정 수치와 같다."""
    import glob
    from app import notice_pdf, crosscheck
    C = crosscheck.app_constants()
    assert C["relax"] == {"부동산": [23705, 25860], "자동차": [4996, 5451]}
    n_rows = 0
    for f in sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "evidence" / "notices" / "*.txt"))):
        facts = notice_pdf.notice_facts(Path(f).read_text(encoding="utf-8"), {})
        n_rows += len(facts["income_rows"]) + len(facts["deposit_rows"])
        assert crosscheck.notice_problems(facts, C) == [], f
    assert n_rows >= 250   # 2026-10-01 기준 287줄 (공고문 57건)


def test_crosscheck_detects_wrong_constant_and_price():
    """앱 수치가 틀리면 잡아낸다 (소득 기준 1원, 예치금, 분양가)."""
    from app import notice_pdf, crosscheck
    t = (Path(__file__).resolve().parent.parent / "evidence" / "notices" / "2026000453.txt").read_text(encoding="utf-8")
    C = crosscheck.app_constants()
    bad = dict(C, income=[C["income"][0] + 1] + C["income"][1:])
    assert any("소득 기준" in p for p in crosscheck.notice_problems(notice_pdf.notice_facts(t, {}), bad))
    bad2 = dict(C, deposit=dict(C["deposit"], other=[250, 300, 400, 500]))
    assert any("예치금" in p for p in crosscheck.notice_problems(notice_pdf.notice_facts(t, {}), bad2))
    facts = notice_pdf.notice_facts(t, {"059.9742A": 99999})
    assert facts["price_seen"] == {"059.9742A": False}


def test_crosscheck_run_flags_listing():
    from app import crosscheck
    from app.models import Listing
    L = Listing(id="2026000453-059.9742A", name="광명", address="경기 광명시", region="경기", sido="경기", kind="k", unit="59A", area=59, price=5.0,
                category="general")
    log = crosscheck.run([L], {"2026000453": {"income_rows": {}, "deposit_rows": {}, "asset_thousand": {}, "price_seen": {"059.9742A": False}}})
    assert L.checks and "분양가" in L.checks[0] and any("[검증·공고문 불일치]" in l for l in log)


def test_judge_cases_are_current_and_enough():
    """판정 검증 사례 (기능: judge_cases) — 생성기와 저장본이 같고 100건 이상이다 (화면 대조는 tools/judge_check.cjs · Actions)."""
    import importlib
    gen = importlib.import_module("tools.make_judge_cases")
    saved = (gen.OUT).read_text(encoding="utf-8")
    tmp = gen.OUT.with_suffix(".tmp.json")
    orig = gen.OUT
    gen.OUT = tmp
    try:
        gen.main()
        assert tmp.read_text(encoding="utf-8") == saved, "tests/judge/cases.json 이 생성기와 달라요 — python -m tools.make_judge_cases 로 다시 만드세요"
    finally:
        gen.OUT = orig
        tmp.unlink(missing_ok=True)
    cases = json.loads(saved)
    assert len(cases) >= 100 and len({c["id"] for c in cases}) == len(cases)
    assert {c["fn"] for c in cases} >= {"score", "sp", "acct", "pubgen", "town", "residence"}
    assert all(c.get("basis") for c in cases)


def test_oracle_matches_notice_table_amounts():
    """검증 사례의 기대값 계산(oracle)이 공고문 금액표와 같은 숫자를 낸다 — 2026000414 <표5> 130% 3인 이하 9,793,892원 등."""
    from tools.make_judge_cases import amt
    assert amt(3, 130) == 9793892 and amt(5, 130) == 12125081 and amt(3, 150) == 11300645 and amt(5, 90) == 8394287 and amt(8, 220) == 24342602


def test_static_guides_use_notice_numbers():
    """정적 가이드 페이지 (기능: static_pages) — 공고문 원문 표의 숫자 그대로 나온다."""
    from tools import build_static
    inc = build_static.guide_income()
    assert "9,793,892" in inc and "7,533,763" in inc and "24,342,602" in inc
    dep = build_static.guide_deposit()
    assert "<td>1,500</td><td>1,000</td><td>500</td>" in dep
    sc = build_static.guide_score()
    assert "<td>15년 이상</td><td>32</td>" in sc and "<td>15년 이상</td><td>17</td>" in sc
