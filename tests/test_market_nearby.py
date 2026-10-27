"""가까운 곳부터 시세 비교 (기능 market_nearby, 2026-10-28) — 단계 순서·멈춤 기준·좌표 없는 단지·직거래 제외."""
from datetime import date
from types import SimpleNamespace

from app import market_nearby as MN

LAWD = "41135"
ORIGIN = {"lat": 37.3674, "lng": 127.1136, "precision": "exact"}
ADDR = "경기도 성남시 분당구 정자동 90번지"


def t(apt, umd, jibun, amount, area=84.9, year=2020, direct=False):
    return {"apt": apt, "umd": umd, "jibun": jibun, "area": area, "amount": amount, "build_year": year, "deal_type": "직거래" if direct else "중개거래",
            "date": "2026-09-01", "floor": 10}


def at(m_north):   # 원점에서 북쪽으로 m 미터
    return {"lat": ORIGIN["lat"] + m_north / 111320, "lng": ORIGIN["lng"]}


def test_address_prefix():
    assert MN.address_prefix(ADDR) == "경기도 성남시 분당구"
    assert MN.address_prefix("부산광역시 해운대구 반여동 610-5번지 일원") == "부산광역시 해운대구"
    assert MN.address_prefix("경기도 화성특례시 동탄구 반송동 99번지[동탄(1) M1-2-2블록]") == "경기도 화성특례시 동탄구"


def test_same_dong_first_and_stop_at_five():
    tr = [t("정자A", "정자동", str(i), 150000 + i * 1000) for i in range(5)] + [t("대장B", "대장동", str(10 + i), 120000) for i in range(30)]
    res, info = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, {}, LAWD)
    assert res["mkt_basis"] == "dong_newbuild" and res["mkt_count"] == 5
    assert res["mkt_base"] == 15.2 and res["mkt_low"] == 15.1
    assert res["mkt_note"].startswith("같은 동(정자동) 준공 10년 이내 같은 평형(84㎡) 매매 5건")


def test_dong_short_then_radius_widens():
    tr = [t("정자A", "정자동", "1", 150000) for _ in range(3)]                       # 같은 동 3건 → 부족
    tr += [t("백현C", "백현동", "2", 160000)]                                          # 0.8km
    tr += [t("백현D", "백현동", "3", 170000) for _ in range(4)]                       # 1.3km
    tr += [t("대장B", "대장동", "4", 120000) for _ in range(20)]                      # 4km
    coords = {f"{LAWD}|정자동|1": at(300), f"{LAWD}|백현동|2": at(800), f"{LAWD}|백현동|3": at(1300), f"{LAWD}|대장동|4": at(4000)}
    res, info = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, coords, LAWD)
    assert [s for s, _ in info["steps"]] == ["dong", "r1000", "r1500"]
    assert dict(info["steps"]) == {"dong": 3, "r1000": 4, "r1500": 8}
    assert res["mkt_basis"] == "near_newbuild" and res["mkt_count"] == 8 and res["mkt_note"].startswith("공고 위치 반경 1.5km 안")
    assert all(c["m"] <= 1500 for c in res["mkt_comps"])


def test_pending_coords_keep_district_and_missing_coords_excluded():
    tr = [t("정자A", "정자동", "1", 150000) for _ in range(3)] + [t("백현C", "백현동", "2", 160000) for _ in range(6)]
    res, info = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, {f"{LAWD}|정자동|1": at(100)}, LAWD)
    assert res is None and "좌표 확인 중" in str(info["steps"][-1])        # 일부만 찾은 채로 비교하지 않음
    coords = {f"{LAWD}|정자동|1": at(100), f"{LAWD}|백현동|2": {"none": "못 찾음", "date": "2026-10-28"}}
    res, info = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, coords, LAWD)
    assert res is None and info["no_coord"] == 6 and dict(info["steps"])["r2000"] == 3   # 못 찾은 단지는 빼고 → 같은 구 그대로


def test_direct_and_old_excluded_and_other_basis_untouched():
    tr = [t("정자A", "정자동", "1", 150000) for _ in range(5)] + [t("정자A", "정자동", "1", 90000, direct=True), t("정자옛", "정자동", "9", 80000, year=2001)]
    res, _ = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, {}, LAWD)
    assert res["mkt_count"] == 5 and res["mkt_direct_excluded"] == 1 and res["mkt_base"] == 15.0
    for basis in ("same_complex", "same_complex_ppa", None):
        assert MN.estimate_nearby(ADDR, 84.0, basis, tr, 2026, ORIGIN, {}, LAWD)[0] is None


def test_large_ppa_rule_kept():
    tr = [t("반여A", "반여동", "1", 100000 + i * 2000, area=110.0) for i in range(5)] + [t("우동B", "우동", "2", 300000, area=120.0) for _ in range(9)]
    res, _ = MN.estimate_nearby("부산광역시 해운대구 반여동 610-5번지 일원", 114.9763, "district_large_ppa", tr, 2026, None, {}, "26350")
    assert res["mkt_basis"] == "dong_large_ppa" and res["mkt_count"] == 5
    assert res["mkt_note"].startswith("이 면적대 거래가 없어 같은 동(반여동) 준공 10년 이내 전용 100㎡ 이상 매매 5건의 ㎡당 가격")
    assert res["mkt_base"] == 10.87          # ㎡당 중앙값 104,000/110 × 114.98㎡


def test_apply_sets_fields_and_geocodes_once(tmp_path):
    tr = [t("정자A", "정자동", "1", 150000) for _ in range(2)] + [t("백현C", "백현동", "2", 160000) for _ in range(5)] + [t("대장B", "대장동", "4", 120000) for _ in range(20)]
    rt = SimpleNamespace(recent=lambda kind, lawd, months: tr)
    L = SimpleNamespace(id="X-84", address=ADDR, area=84.0, sido="경기", mkt_basis="district_newbuild", rental=False, geo=ORIGIN,
                        mkt_low=11.0, mkt_base=12.0, mkt_count=27, mkt_note="같은 구", mkt_comps=[], mkt_direct_excluded=0)
    asked = []

    def fake_geocode(keys, prefix_of, sido_of, coords, today, log, http=None, key=None, budget=0):
        asked.extend(keys)
        pos = {"정자동": at(200), "백현동": at(900), "대장동": at(4000)}
        for k in keys:
            coords[k] = pos[k.split("|")[1]] | {"date": today.isoformat()}
        return len(keys)
    orig = MN.geocode_keys
    MN.geocode_keys = fake_geocode
    try:
        log = []
        stat = MN.apply([L], rt, date(2026, 10, 28), {"경기 성남시 분당구": LAWD}, log, coord_path=tmp_path / "c.json")
        assert L.mkt_basis == "near_newbuild" and L.mkt_count == 7 and stat["r1000"] == 1
        assert sorted(asked) == [f"{LAWD}|대장동|4", f"{LAWD}|백현동|2", f"{LAWD}|정자동|1"]
        L.mkt_basis = "district_newbuild"
        asked.clear()
        MN.apply([L], rt, date(2026, 10, 28), {"경기 성남시 분당구": LAWD}, log, coord_path=tmp_path / "c.json")
        assert asked == []          # 두 번째는 저장한 좌표를 씀
    finally:
        MN.geocode_keys = orig


def test_independent_check_agrees():
    """tools/qa/market_check 의 따로 옮긴 계산(expect_nearby)이 수집 코드와 같은 단계·값을 낸다"""
    from tools.qa import market_check as MC
    tr = [t("정자A", "정자동", "1", 150000) for _ in range(3)] + [t("백현C", "백현동", "2", 160000)] + [t("백현D", "백현동", "3", 170000 + i * 500) for i in range(4)] \
        + [t("대장B", "대장동", "4", 120000) for _ in range(20)] + [t("백현D", "백현동", "3", 90000, direct=True)]
    coords = {f"{LAWD}|정자동|1": at(300), f"{LAWD}|백현동|2": at(800), f"{LAWD}|백현동|3": at(1300), f"{LAWD}|대장동|4": at(4000)}
    app, _ = MN.estimate_nearby(ADDR, 84.0, "district_newbuild", tr, 2026, ORIGIN, coords, LAWD)
    raw = [{"apt": r["apt"], "umd": r["umd"], "jibun": r["jibun"], "area": r["area"], "amount": r["amount"], "build": r["build_year"], "floor": r["floor"],
            "date": r["date"], "cancel": False, "direct": r["deal_type"] == "직거래"} for r in tr]
    district = MC.expect("분당하이스트", 84.0, raw, [], 2026, address=ADDR)
    assert district["basis"] == "district_newbuild"
    e = MC.expect_nearby(district, 84.0, raw, 2026, ADDR, ORIGIN, coords, LAWD)
    assert (e["basis"], e["count"], e["base"], e["low"]) == (app["mkt_basis"], app["mkt_count"], app["mkt_base"], app["mkt_low"])
    assert all(MC.comp_in(c, e["rows"]) for c in app["mkt_comps"])
