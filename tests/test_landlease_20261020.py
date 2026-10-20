"""2026-10-20 사용자 '데이터 확인 3건 있는 공고 왜 그런지 확인해서 해결하고 앞으로 해당사항 없도록 전수검증':
고덕강일지구 3단지 토지임대부(본청약) 2026000373 — ① 세대주 요건 추정 ② 60㎡ 이하 일반공급 소득·자산 못 읽음 ③ 청약홈 분양가가 공고문 표에 없음(거짓 경고),
그리고 ④ 토지임대부인데 땅값이 빠진 분양가로 시세 차이(로또 +6억)를 계산. 정답 tests/golden/notices.json 2026000373."""
import json
from datetime import date
from pathlib import Path

from app import notice_pdf as N

ROOT = Path(__file__).resolve().parents[1]
T = (ROOT / "evidence/notices/2026000373.txt").read_text(encoding="utf-8")
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))["2026000373"]["fields"]


def test_sh_landlease_general_limits_and_head():
    pl = N.parse_pub_limits(T)
    assert pl == GOLD["pub_limits"]
    assert pl["amounts"]["pri"]["3"] == [7533763, 10547268] and pl["amounts"]["elig"]["8"] == [11064819, 22129638] and pl["total_asset"] == 36200
    o = N.parse_notice(T)
    assert o["need_head"] is False and "세대주 여부" in o["quotes"]["need_head"]
    # 표 한 칸이 빠지면(칸 수가 다르면) 읽지 않는다
    assert N.need_head_general(N.re.sub(r"\s+", "", T).replace("세대주여부해당없음해당없음해당없음신청자본인", "세대주여부해당없음해당없음신청자본인", 1)) is None


def test_price_seen_accepts_thousand_won_table_truncated():
    f = N.notice_facts(T, {"049.0000H": 29567, "059.0000A": 38670, "049.0000A": 30800})
    assert all(f["price_seen"].values())
    assert N.notice_facts(T, {"049.0000H": 29999})["price_seen"]["049.0000H"] is False


def test_land_lease_skips_margin(monkeypatch):
    from app import pipeline as P
    raw = {"price": 3.08, "address": "서울특별시 강동구 강일동 174 일원", "name": "고덕강일지구 3단지 토지임대부(본청약)", "area": 49.0, "unit": "49A",
           "notice_no": "2026000373", "house_ty": "049.0000A", "category": "general", "notice": "2026-10-16", "apply": "2026-11-02", "apply_end": "2026-11-06",
           "winner": "2026-11-26", "contract": None, "move_in": "2027-05", "house_dtl": "국민", "url": "https://x"}
    class Rt:
        def recent(self, kind, *a):
            return [{"apt": "강동리버스트4단지", "area": 49.9, "build_year": 2021, "amount": 100000, "date": "2026-09-01", "deal_type": "중개거래"}] * 4 if kind == "trade" else []
    monkeypatch.setattr(P, "feature_on", lambda k: k != "land_lease_value" or ON[0])
    ON = [False]   # 땅 몫 계산(land_lease_value)이 꺼져 있으면 시세를 조회하지 않고 차이를 계산하지 않는다 (v1.69.0 동작)
    L = P.build_listing(raw, Rt(), date(2026, 10, 20), {})
    assert L.land_lease is True and L.mkt_low is None and "토지임대부" in L.mkt_note
    ON[0] = True   # 켜져 있으면 주변 시세(땅 포함)는 그대로 조회 — 비교는 화면·engine.grade 가 땅 몫을 더해서
    L = P.build_listing(raw, Rt(), date(2026, 10, 20), {"서울 강동구": {"code": "11740"}})
    assert L.land_lease is True and L.mkt_base == 10.0


def test_check_audit_categories():
    from app.check_audit import audit, category
    from app.models import Listing
    assert category("세대주 요건을 공고문에서 확인하지 못해 규제지역 기준으로 추정했어요") == "unread"
    assert category("공고문 대조: 청약홈 분양가가 모집공고문 공급금액 표에서 확인되지 않아요") == "notice"
    assert category("마진율 -61%는 이례적이에요. 시세 근거를 확인하세요") == "market"
    assert category("어떤 새 문구") == "other"
    L = Listing(id="1-084A", name="가", address="서울특별시 강동구", region="서울", kind="일반", category="general", unit="84A", price=5, apply="2026-11-01",
                notice="2026-10-16", url="https://x", checks=["재당첨 제한 기간을 공고문에서 확인하지 못해 추정했어요", "마진율 -61%는 이례적이에요"])
    count, log = audit([L])
    assert count["unread"] == 1 and any(x.startswith("[경고·전수검증]") for x in log)
    count, log = audit([Listing(**{**L.model_dump(), "checks": ["마진율 -61%는 이례적이에요"]})])
    assert not any(x.startswith("[경고") for x in log)   # 시세 참고만 있으면 알림 없음


def test_land_rent_tables_both_formats():
    """2026-10-20 사용자 '토지임대부는 건물만 사고 토지는 임대료 — 시세 산정을 따로': 공고문 월 토지임대료 표·보증금 전환이율(전환 예시 금액이 맞을 때만)"""
    flat = N.re.sub(r"\s+", "", T)
    assert {k: v for k, v in N.parse_land_rent(flat).items() if k != "m"} == {"by_area": {"49": 426000, "59": 511500}, "rate": 0.025}
    magok = N.re.sub(r"\s+", "", (ROOT / "evidence/qa/notices/2026000041.txt").read_text(encoding="utf-8"))
    assert {k: v for k, v in N.parse_land_rent(magok).items() if k != "m"} == {"by_area": {"59": 663900, "84": 946000}, "rate": 0.0218}
    assert N.parse_land_rent(flat.replace("122,000,000171,830", "122,000,000271,830", 1)) is None   # 전환 예시가 안 맞으면 이율을 믿지 않음


def test_land_lease_grade_uses_land_share():
    from app.engine import grade
    from app.models import Listing
    L = Listing(id="2026000373-049.0000A", name="고덕강일지구 3단지 토지임대부(본청약)", address="서울특별시 강동구 강일동", region="서울", kind="일반", category="general",
                unit="49A", area=49.0, price=3.08, apply="2026-11-02", notice="2026-10-16", url="https://x", land_lease=True, land_rent=426000, land_rent_rate=0.025,
                mkt_low=9.05, mkt_base=9.7)
    g = grade(L)
    assert g["grade"] == "unknown" and g["name"] == "토지임대부"            # 로또·고려 등급을 매기지 않음
    assert abs(g["lease"]["land"] - 2.0448) < 1e-4                         # 426,000 × 12 ÷ 2.5% = 2억 448만
    assert abs(g["lease"]["lo"] - (9.05 - g["cost"] - 2.0448)) < 1e-6
    assert grade(Listing(**{**L.model_dump(), "land_rent": None}))["lease"] is None   # 임대료를 못 읽으면 차이를 내지 않음
