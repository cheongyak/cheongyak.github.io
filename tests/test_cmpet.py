from datetime import date

import httpx

from app import notify
from app.models import Listing
from app.sources import applyhome, cmpet


def _L(nid, ty, apply="2026-09-22", apply_end="2026-09-23", category="general"):
    return Listing(id=f"{nid}-{ty}", name="테스트 단지", address="서울특별시 광진구 구의동 1", region="서울", sido="서울",
                   kind="k", unit=ty, area=84, price=10, category=category, apply=apply, apply_end=apply_end)


ROWS = [
    {"HOUSE_MANAGE_NO": "2026000001", "HOUSE_TY": "084.0000A", "SUBSCRPT_RANK_CODE": "1", "RESIDE_SENM": "해당지역",
     "SUPLY_HSHLDCO": "40", "REQ_CNT": "1,280", "CMPET_RATE": "32.00"},
    {"HOUSE_MANAGE_NO": "2026000001", "HOUSE_TY": "084.0000A", "SUBSCRPT_RANK_CODE": "1", "RESIDE_SENM": "기타지역",
     "SUPLY_HSHLDCO": "40", "REQ_CNT": "5000", "CMPET_RATE": "-"},
    {"HOUSE_MANAGE_NO": "2026000001", "HOUSE_TY": "059.0000B", "SUBSCRPT_RANK_CODE": "2", "RESIDE_SENM": "해당지역",
     "SUPLY_HSHLDCO": "10", "REQ_CNT": "3", "CMPET_RATE": "(△7)"},
]
SCORES = [{"HOUSE_TY": "084.0000A", "RESIDE_SENM": "해당지역", "LWET_SCORE": "64", "TOP_SCORE": "79", "AVRG_SCORE": "68.5"}]


def test_parse_and_headline_prefers_first_rank_local():
    by = cmpet.parse(ROWS, SCORES)
    a = by["084.0000A"]
    assert len(a["rows"]) == 2 and a["scores"][0] == {"reside": "해당지역", "low": 64.0, "top": 79.0, "avg": 68.5}
    h = cmpet.headline(a)
    assert h["reside"] == "해당지역" and h["rate"] == "32.00" and h["req"] == 1280.0
    b = cmpet.headline(by["059.0000B"])
    assert b["rate"] == "(△7)" and b["rate_num"] is None      # 미달 표기는 글자 그대로 둔다


def test_apply_competition_only_for_started_notices():
    calls = []

    def h(req):
        calls.append((req.url.path, req.url.params["cond[HOUSE_MANAGE_NO::EQ]"]))
        if req.url.path.endswith("Score"):
            return httpx.Response(200, json={"data": SCORES})
        return httpx.Response(200, json={"data": ROWS})

    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(h)))
    a, b = _L("2026000001", "084.0000A"), _L("2026000001", "059.0000B")
    future = _L("2026000002", "084.0000A", apply="2026-10-10", apply_end="2026-10-11")
    log = []
    cmpet.apply_competition([a, b, future], log, "2026-09-30", client=cl)
    assert a.competition["scores"][0]["low"] == 64.0 and b.competition["rows"][0]["rank"] == "2"
    assert future.competition is None
    assert {c[1] for c in calls} == {"2026000001"}
    assert any("[응답 필드] 경쟁률(APT)" in l for l in log) and any("공급 40.0 접수 1280.0 경쟁률 32.00" in l for l in log)


def test_apply_competition_logs_permission_error():
    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))))
    a = _L("2026000001", "084.0000A")
    log = []
    cmpet.apply_competition([a], log, "2026-09-30", client=cl)
    assert a.competition is None and any("활용신청" in l for l in log)


def test_closed_notice_kept_until_two_weeks_after_winner():
    class C:
        def notices(self, category, since):
            if category != "general":
                return []
            return [{"PBLANC_NO": "1", "HOUSE_NM": "a", "RCEPT_BGNDE": "2026-09-01", "RCEPT_ENDDE": "2026-09-02", "PRZWNER_PRESNATN_DE": "2026-09-20"},
                    {"PBLANC_NO": "2", "HOUSE_NM": "b", "RCEPT_BGNDE": "2026-08-01", "RCEPT_ENDDE": "2026-08-02", "PRZWNER_PRESNATN_DE": "2026-08-10"}]

        def models(self, category, no):
            return [{"HOUSE_TY": "084.0000A", "LTTOT_TOP_AMOUNT": "90000"}]

    got = [r["notice_no"] for r in applyhome.iter_open_listings(C(), "2026-09-30", "2026-07-01")]
    assert got == ["1"]


def test_closed_notice_does_not_trigger_new_alert():
    closed = _L("2026000001", "084.0000A", apply="2026-09-20", apply_end="2026-09-22")
    closed.mkt_low, closed.mkt_base = 20, 22      # 로또 등급
    from app import webpush
    ev, _ = webpush.build_events([closed], set(), date(2026, 9, 30), {})
    assert not [e for e in ev if e["kind"] == "new"]


def test_history_and_area_comps():
    class AH:
        def notices(self, category, since):
            if category != "general":
                return []
            return [  # 같은 구, 접수 끝남
                {"PBLANC_NO": "2026000009", "HOUSE_MANAGE_NO": "2026000009", "HOUSE_NM": "옆 단지", "HSSPLY_ADRES": "서울특별시 광진구 자양동 1",
                 "RCRIT_PBLANC_DE": "2026-06-01", "RCEPT_BGNDE": "2026-06-10", "RCEPT_ENDDE": "2026-06-11"},
                # 다른 구
                {"PBLANC_NO": "2026000010", "HOUSE_MANAGE_NO": "2026000010", "HOUSE_NM": "먼 단지", "HSSPLY_ADRES": "서울특별시 강남구 역삼동 1",
                 "RCRIT_PBLANC_DE": "2026-06-01", "RCEPT_BGNDE": "2026-06-10", "RCEPT_ENDDE": "2026-06-11"},
                # 같은 구, 아직 접수 전
                {"PBLANC_NO": "2026000011", "HOUSE_MANAGE_NO": "2026000011", "HOUSE_NM": "예정 단지", "HSSPLY_ADRES": "서울특별시 광진구 구의동 2",
                 "RCRIT_PBLANC_DE": "2026-09-25", "RCEPT_BGNDE": "2026-10-10", "RCEPT_ENDDE": "2026-10-11"},
            ]

    asked = []

    def h(req):
        asked.append(req.url.params["cond[HOUSE_MANAGE_NO::EQ]"])
        if req.url.path.endswith("Score"):
            return httpx.Response(200, json={"data": SCORES})
        return httpx.Response(200, json={"data": ROWS})

    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(h)))
    L = _L("2026000001", "084.0000C", apply="2026-10-06", apply_end="2026-10-07")
    L.sigungu = "광진구"
    L.area = 84.9
    small = _L("2026000001", "039.0000A", apply="2026-10-06", apply_end="2026-10-07")
    small.sigungu, small.area = "광진구", 39.0
    hist = cmpet.update_history(AH(), [L, small], [], date(2026, 9, 30), client=cl, history={})
    assert set(hist) == {"2026000009"} and set(asked) == {"2026000009"}
    u = hist["2026000009"]["units"]["084.0000A"]
    assert u["rate"] == "32.00" and u["low"] == 64.0 and u["unit"] == "84A"
    # 한 번 받은 결과는 다시 받지 않는다
    asked.clear()
    cmpet.update_history(AH(), [L], [], date(2026, 9, 30), client=cl, history=hist)
    assert asked == []
    cmpet.attach_area_comps([L, small], hist, date(2026, 9, 30))
    assert L.area_comps[0]["name"] == "옆 단지" and L.area_comps[0]["rate"] == "32.00"
    assert small.area_comps == []          # 면적이 많이 다르면 붙이지 않는다


def test_house_type_with_trailing_space_matches():
    """실제 응답(2026-09-30 숭의역): 주택형 끝에 공백 '069.7032 ' → 공고 id 에도 공백이 남아 있어 맞춰야 한다."""
    rows = [{"HOUSE_TY": "069.7032 ", "SUBSCRPT_RANK_CODE": "1", "RESIDE_SENM": "해당지역", "SUPLY_HSHLDCO": "7", "REQ_CNT": "9", "CMPET_RATE": "1.29"}]
    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": [] if r.url.path.endswith("Score") else rows}))))
    L = _L("2026000448", "069.7032 ")
    cmpet.apply_competition([L], [], "2026-09-30", client=cl)
    assert L.competition and L.competition["rows"][0]["rate"] == "1.29"


# 실제 응답 (evidence/cmpet/special.txt, 2026-10-01 조회) — 2026000103 066.0000A.
# 공급 세대수는 모집공고문 2026000103 「특별공급 신청자격별・주택형별 공급세대수」 표 066.0000A 행
# (기관추천 6 · 다자녀 - · 신혼부부 8 · 노부모부양 1 · 생애최초 4 · 신생아 5 · 합계 24)과 같다
SP_ROW_103 = {"CRSPAREA_LFE_FRST_CNT": 12, "CRSPAREA_MNYCH_CNT": 0, "CRSPAREA_NWBB_NWBBSHR_CNT": 16, "CRSPAREA_NWWDS_NMTW_CNT": 22,
              "CRSPAREA_OPS_CNT": 0, "CRSPAREA_YGMN_CNT": 0, "CTPRVN_LFE_FRST_CNT": 0, "CTPRVN_MNYCH_CNT": 0, "CTPRVN_NWBB_NWBBSHR_CNT": 0,
              "CTPRVN_NWWDS_NMTW_CNT": 0, "CTPRVN_OPS_CNT": 0, "CTPRVN_YGMN_CNT": 0, "ETC_AREA_LFE_FRST_CNT": 22, "ETC_AREA_MNYCH_CNT": 0,
              "ETC_AREA_NWBB_NWBBSHR_CNT": 17, "ETC_AREA_NWWDS_NMTW_CNT": 36, "ETC_AREA_OPS_CNT": 1, "ETC_AREA_YGMN_CNT": 0,
              "HOUSE_MANAGE_NO": "2026000103", "HOUSE_TY": "066.0000A", "INSTT_RECOMEND_DCSN_CNT": 0, "INSTT_RECOMEND_HSHLDCO": 6,
              "INSTT_RECOMEND_PREPAR_CNT": 2, "LFE_FRST_HSHLDCO": 4, "MNYCH_HSHLDCO": 0, "NWBB_NWBBSHR_HSHLDCO": 5, "NWWDS_NMTW_HSHLDCO": 8,
              "OLD_PARNTS_SUPORT_HSHLDCO": 1, "PBLANC_NO": "2026000103", "SPSPLY_HSHLDCO": 24, "SUBSCRPT_RESULT_NM": "청약접수 종료",
              "TRANSR_INSTT_ENFSN_CNT": 0, "TRANSR_INSTT_ENFSN_HSHLDCO": 0, "YGMN_HSHLDCO": 0}


def test_golden_special_request_fields_match_notice_table():
    by = cmpet.parse_special([SP_ROW_103])
    a = by["066.0000A"]
    assert {t: v["u"] for t, v in a.items()} == {"newborn": 5, "newlywed": 8, "first": 4, "elder": 1}   # 다자녀 0세대는 뺀다
    assert a["newlywed"] == {"u": 8, "req": 58, "local": 22, "sido": 0, "other": 36}
    assert a["first"]["req"] == 34 and a["newborn"]["req"] == 33 and a["elder"]["req"] == 1


def test_parse_special_ignores_rows_without_fields():
    assert cmpet.parse_special(ROWS) == {}          # 일반공급 경쟁률 줄은 특별공급 필드가 없다


def test_apply_sp_competition_after_special_end():
    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [SP_ROW_103]}))))
    a = _L("2026000103", "066.0000A")
    a.special_apply, a.special_apply_end = "2026-09-20", "2026-09-20"
    b = _L("2026000104", "066.0000A")
    b.special_apply, b.special_apply_end = "2026-09-30", "2026-09-30"      # 오늘 끝나는 공고는 아직 결과가 없다
    log = []
    cmpet.apply_sp_competition([a, b], log, "2026-09-30", client=cl)
    assert a.sp_competition["newlywed"]["req"] == 58 and b.sp_competition is None
    assert any("[특별공급 신청] 특별공급 접수가 끝난 공고 1건 중 1건" in l for l in log)


def test_history_special_backfill_and_attach_area_sp():
    hist = {"2026000103": {"name": "옆 단지", "sigungu": "광진구", "category": "general", "apply": "2026-06-10", "notice": "2026-06-01",
                           "units": {"066.0000A": {"area": 66.0}}},
            "2026000200": {"name": "LH 단지", "sigungu": "광진구", "category": "general", "apply": "2026-06-10", "units": {}}}
    asked = []

    def h(req):
        no = req.url.params["cond[HOUSE_MANAGE_NO::EQ]"]
        asked.append((req.url.path.rsplit("/", 1)[1], no))
        return httpx.Response(200, json={"data": [SP_ROW_103] if no == "2026000103" else []})

    cl = cmpet.CmpetClient("k", httpx.Client(transport=httpx.MockTransport(h)))

    class AH:
        def notices(self, category, since):
            return []

    L = _L("2026000001", "059.0000A", apply="2026-10-06", apply_end="2026-10-07")
    L.sigungu, L.area = "광진구", 59.9
    far = _L("2026000001", "114.0000A", apply="2026-10-06", apply_end="2026-10-07")
    far.sigungu, far.area = "광진구", 114.0
    log = []
    cmpet.update_history(AH(), [L], log, date(2026, 9, 30), client=cl, history=hist, special=True)
    assert sorted(asked) == [("getAPTSpsplyReqstStus", "2026000103"), ("getAPTSpsplyReqstStus", "2026000200")]
    assert hist["2026000103"]["sp"]["066.0000A"]["first"]["u"] == 4 and hist["2026000200"]["sp"] == {}
    asked.clear()      # 받은 기록·최근에 빈 기록은 다시 묻지 않는다
    cmpet.update_history(AH(), [L], [], date(2026, 9, 30), client=cl, history=hist, special=True)
    assert asked == []
    cmpet.attach_area_sp([L, far], hist, date(2026, 9, 30))
    assert L.area_sp[0]["name"] == "옆 단지" and L.area_sp[0]["unit"] == "66A" and L.area_sp[0]["sp"]["newlywed"]["req"] == 58
    assert far.area_sp == []
