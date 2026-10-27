"""시세 원자료 대조 도구 (tools/qa/market_check.py, 2026-10-02) — 따로 구현한 계산이 수집 코드(app/market.py)와 같은 결과를 내는지,
그리고 화면 값이 틀리면 잡는지 원자료 XML 모양으로 확인한다 (실제 원자료 대조는 Actions 에서 인증키로)."""
from datetime import date

from app import market
from app.sources import rtms
from tools.qa import market_check as MC


def xml(items):
    tags = ("aptNm", "excluUseAr", "floor", "dealAmount", "buildYear", "dealYear", "dealMonth", "dealDay", "cdealType", "dealingGbn", "umdNm", "aptDong")
    body = "".join("<item>" + "".join(f"<{t}>{it.get(t, '')}</{t}>" for t in tags) + "</item>" for it in items)
    return f"<response><header><resultCode>000</resultCode></header><body><items>{body}</items></body></response>"


def row(apt, area, amt, d, floor=5, build=2022, cancel="", direct="중개거래"):
    y, m, dd = d.split("-")
    return {"aptNm": apt, "excluUseAr": area, "floor": floor, "dealAmount": f"{amt:,}", "buildYear": build, "dealYear": y, "dealMonth": str(int(m)),
            "dealDay": str(int(dd)), "cdealType": cancel, "dealingGbn": direct, "umdNm": "작전동"}


TRADES = [row("힐스테이트자이계양", 53.8, 54000, "2026-09-08"), row("힐스테이트자이계양", 53.8, 54500, "2026-08-21", 10),
          row("다른신축", 55.0, 61000, "2026-08-01"), row("다른신축", 52.0, 60000, "2026-07-01", 3), row("옛단지", 54.0, 40000, "2026-07-02", build=2001),
          row("다른신축", 51.0, 59000, "2026-06-11", 2), row("다른신축", 53.0, 99999, "2026-06-12", cancel="O"), row("다른신축", 53.0, 30000, "2026-06-13", direct="직거래")]


def run(name, area, trades):
    x = xml(trades)
    app_rows, raw_rows = rtms.parse_items(x), MC.rows_of(x)
    return market.estimate_market(name, area, app_rows, [], 2026), MC.expect(name, area, raw_rows, [], 2026)


def test_independent_calc_matches_collector():
    for name, area, tr in [("계양 힐스테이트자이계양(본청약)", 54.0, TRADES), ("새 단지", 53.0, TRADES), ("새 단지", 53.0, TRADES[:3]), ("새 단지", 53.0, TRADES[2:6])]:
        app_v, raw = run(name, area, tr)
        assert (app_v["mkt_basis"], app_v["mkt_base"], app_v["mkt_low"]) == (raw["basis"], raw["base"], raw["low"]), name
        assert all(MC.comp_in(c, raw["rows"]) for c in app_v["mkt_comps"])


def test_check_flags_wrong_numbers_and_fake_comps():
    app_v, _ = run("새 단지", 53.0, TRADES)
    L = {"id": "x-1", "name": "새 단지", "area": 53.0, "address": "인천광역시 계양구 작전동", "sido": "인천", **app_v}
    get = lambda kind, lawd, ym: MC.rows_of(xml(TRADES)) if kind == "trade" and ym == "202609" else []
    assert MC.check([L], date(2026, 10, 2), get, nearby=False)["fails"] == 0
    bad = dict(L, mkt_base=L["mkt_base"] + 0.1)
    assert "mkt_base" in MC.check([bad], date(2026, 10, 2), get, nearby=False)["items"][0]["bad"][0]
    fake = dict(L, mkt_comps=L["mkt_comps"] + [{"apt": "다른신축", "area": 53.0, "floor": 5.0, "amount": 9.99, "date": "2026-06-12"}])   # 해제된 거래를 근거로 쓰면
    assert any("원자료" in b and "없음" in b for b in MC.check([fake], date(2026, 10, 2), get, nearby=False)["items"][0]["bad"])


# 기능 mkt_area_fallback (2026-10-07): 같은 평형(±3㎡) 거래가 3건 미만이면 ±10㎡ 같은 구 신축 매매 5건 이상의 ㎡당 가격 × 면적
WIDE = [row("가신축", 102.66, 53000, "2026-09-30"), row("가신축", 102.66, 49500, "2026-09-08"), row("가신축", 102.66, 55500, "2026-08-20"),
        row("나신축", 115.14, 73500, "2026-08-04"), row("다신축", 99.0, 51000, "2026-07-10"), row("다신축", 99.0, 52000, "2026-06-10", direct="직거래"),
        row("옛단지", 108.0, 40000, "2026-07-02", build=2001), row("라신축", 84.9, 60000, "2026-07-01")]


def test_area_fallback_off_by_default_and_matches_independent_calc():
    x = xml(WIDE)
    app_rows, raw_rows = rtms.parse_items(x), MC.rows_of(x)
    off = market.estimate_market("향남 새 단지", 107.97, app_rows, [], 2026)
    assert off["mkt_base"] is None and MC.expect("향남 새 단지", 107.97, raw_rows, [], 2026)["basis"] is None
    on = market.estimate_market("향남 새 단지", 107.97, app_rows, [], 2026, area_fallback=True)
    raw = MC.expect("향남 새 단지", 107.97, raw_rows, [], 2026, fallback=True)
    assert on["mkt_basis"] == raw["basis"] == "district_area_ppa"
    assert (on["mkt_base"], on["mkt_low"], on["mkt_count"]) == (raw["base"], raw["low"], raw["count"]) and on["mkt_count"] == 5   # 직거래·옛 단지·84㎡ 뺌
    assert on["mkt_direct_excluded"] == 1 and on["mkt_low"] <= on["mkt_base"]
    assert all(MC.comp_in(c, raw["rows"]) for c in on["mkt_comps"]) and "추정" in on["mkt_note"]


def test_area_fallback_needs_five_and_exact_band_first():
    x = xml(WIDE[:4])   # ±10㎡ 4건 → 추정하지 않음
    assert market.estimate_market("향남 새 단지", 107.97, rtms.parse_items(x), [], 2026, area_fallback=True)["mkt_base"] is None
    x = xml(TRADES)     # 같은 평형 거래가 있으면 예전 방식 그대로
    assert market.estimate_market("새 단지", 53.0, rtms.parse_items(x), [], 2026, area_fallback=True)["mkt_basis"] == "district_newbuild"


def test_large_fallback_same_complex_and_big_newbuild():
    """기능 mkt_large_fallback (2026-10-15 시세 부족 원인 분석): 큰 평형은 ① 같은 단지 다른 평형 3건+ ② 같은 구 신축 100㎡ 이상 5건+ 의 ㎡당 가격.
    펜트하우스(P)는 추정하지 않음. 수집 코드와 독립 대조 도구가 같은 값을 낸다."""
    own = [row("힐스테이트거제시그니처", a, amt, d) for a, amt, d in ((84.9, 52000, "2026-09-01"), (99.8, 61000, "2026-08-02"), (84.9, 51000, "2026-07-03"), (110.0, 70000, "2026-06-04"))]
    big = [row(f"신축{i}", 101.0 + i * 3, 70000 + i * 2000, f"2026-0{6 + i % 3}-1{i}") for i in range(6)]
    for name, area, tr, unit, want in [("힐스테이트 거제시그니처(1회차)", 132.98, own + big, "132A", "same_complex_ppa"),
                                       ("진주 판문지구 레이크써밋 웰가", 182.93, big, "182", "district_large_ppa"),
                                       ("상동역 롯데캐슬 시그니처", 187.51, own + big, "187P", None),
                                       ("작은 단지", 84.0, big[:2], "84A", None)]:
        x = xml(tr)
        a = market.estimate_market(name, area, rtms.parse_items(x), [], 2026, area_fallback=True, large_fallback=True, unit=unit)
        r = MC.expect(name, area, MC.rows_of(x), [], 2026, fallback=True, large=True, unit=unit)
        assert a["mkt_basis"] == r["basis"] == want, (name, a["mkt_basis"], r["basis"])
        assert (a["mkt_base"], a["mkt_low"]) == (r["base"], r["low"]), name
        if want is None and unit.endswith("P"):
            assert "펜트하우스" in a["mkt_note"]
    many = big + [row("국평신축", 84.9, 50000, "2026-09-02")] * 10
    off = market.estimate_market("진주 판문지구 레이크써밋 웰가", 182.93, rtms.parse_items(xml(many)), [], 2026, area_fallback=True, large_fallback=False, unit="182")
    assert off["mkt_base"] is None and "전용 116㎡까지만" in off["mkt_note"]   # 스위치 끄면 예전처럼 시세 부족 + 이유


def test_shortage_reasons():
    few = rtms.parse_items(xml([row("어느단지", 84.9, 30000, "2026-09-01", build=2010)] * 3))
    assert "매매가 3건뿐" in market.estimate_market("진도 새단지", 84.9, few, [], 2026)["mkt_note"]
    old = rtms.parse_items(xml([row("옛단지", 74.0, 130000, "2026-09-01", build=1993)] * 12))
    assert "준공 10년이 넘은 단지" in market.estimate_market("분당 새단지", 74.0, old, [], 2026)["mkt_note"]


def test_same_name_other_dong_is_not_same_complex():
    """'힐스테이트 거제시그니처'(옥포동)에 상동동 '힐스테이트거제' 거래가 같은 단지로 붙어 84A 시세 2.56억(분양가 5.88억)이 되던 문제 (2026-10-15)"""
    from app.market import dong_of
    addr = "경상남도 거제시 옥포동 1670번지 일원"
    assert dong_of(addr) == "옥포동" and dong_of("경기도 화성시 병점구 화산로 9") == "" and dong_of("서울특별시 종로구 종로1가 1") == "종로1가"
    tr = [dict(row("힐스테이트거제", 84.96, 25500 + i * 100, f"2026-09-0{i + 1}"), umdNm="상동동") for i in range(5)]
    x = xml(tr)
    a = market.estimate_market("힐스테이트 거제시그니처(1회차)", 84.9, rtms.parse_items(x), [], 2026, dong="옥포동")
    r = MC.expect("힐스테이트 거제시그니처(1회차)", 84.9, MC.rows_of(x), [], 2026, address=addr)
    assert a["mkt_basis"] != "same_complex" and r["basis"] != "same_complex"
    assert market.estimate_market("힐스테이트 거제시그니처(1회차)", 84.9, rtms.parse_items(x), [], 2026)["mkt_basis"] == "same_complex"   # 주소 동을 모르면 예전처럼
