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
    msgs = notify.build_messages([closed], set(), date(2026, 9, 30), {})
    assert not any("새로" in m["title"] for m in msgs)


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
