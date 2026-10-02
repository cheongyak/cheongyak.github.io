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
    assert MC.check([L], date(2026, 10, 2), get)["fails"] == 0
    bad = dict(L, mkt_base=L["mkt_base"] + 0.1)
    assert "mkt_base" in MC.check([bad], date(2026, 10, 2), get)["items"][0]["bad"][0]
    fake = dict(L, mkt_comps=L["mkt_comps"] + [{"apt": "다른신축", "area": 53.0, "floor": 5.0, "amount": 9.99, "date": "2026-06-12"}])   # 해제된 거래를 근거로 쓰면
    assert any("원자료" in b and "없음" in b for b in MC.check([fake], date(2026, 10, 2), get)["items"][0]["bad"])
