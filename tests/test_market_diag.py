"""시세 부족 원인 기록·같은 실행 시군구 코드 재조회 (2026-10-15 사용자 '시세부족 공고 원인 파악해서 개선')."""
from datetime import date

from app import pipeline as P
from app.market import market_diag
from app.models import Listing


def _t(area, year, amount=50000, apt="다른단지"):
    return {"apt": apt, "area": area, "build_year": year, "amount": amount, "date": "2026-09-01", "deal_type": "중개거래"}


def test_diag_counts_and_reason():
    trades = [_t(84.9, 2020)] * 30 + [_t(59.9, 2000)] * 10
    d = market_diag("새단지", 147.9, trades, [], 2026)
    assert (d["trades"], d["newbuild"], d["band_any"], d["wide_new"], d["max_area_new"]) == (40, 30, 0, 0, 84.9)
    P.MARKET_DIAG.append(("새단지", "147P", 147.9, "41591", d))
    line = P.market_diag_lines()[0]
    assert "신축 매매 중 이 면적대가 없음" in line and not P.MARKET_DIAG
    P.MARKET_DIAG.append(("작은곳", "84A", 84.9, "12860", market_diag("작은곳", 84.9, [_t(84.9, 2020)] * 3, [], 2026)))
    assert "구 전체 매매가 적음" in P.market_diag_lines()[0]


class FakeRt:
    def recent(self, kind, lawd, months):
        assert lawd == "41595"
        return [_t(84.9, 2022, 48000)] * 4 if kind == "trade" else []


def test_refill_market_when_code_found_in_same_run():
    L = Listing(id="2026910262-084.9631A", name="화성 송산 동원로얄듀크 포레(2차)", address="경기도 화성시 병점구 화산로 9", region="경기", sido="경기",
                kind="무순위", category="remainder", unit="84A", area=84.9631, price=4.82, apply="2026-10-20", notice="2026-10-13", url="https://x",
                mkt_note="시군구 코드를 아직 확인하지 못해 시세를 조회하지 못했어요 (지도 좌표로 확인되면 다음 수집부터 조회).")
    log = []
    P.refill_market([L], FakeRt(), date(2026, 10, 15), {"경기 화성시 병점구": {"code": "41595"}}, log)
    assert L.mkt_basis == "district_newbuild" and L.mkt_count == 4 and L.mkt_low and any("바로 조회" in x for x in log)
