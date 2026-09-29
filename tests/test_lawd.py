from app import lawd as LW


class R:
    def __init__(self, code, js): self.status_code, self._js = code, js
    def json(self): return self._js


class H:
    def __init__(self, r): self.r = r
    def get(self, *a, **k): return self.r


def gc(code, a1, a2, a3=""):
    return {"results": [{"code": {"id": code}, "region": {"area1": {"name": a1}, "area2": {"name": a2}, "area3": {"name": a3}}}]}


def test_key_and_table():
    assert LW.key_of("경상남도 진주시 충무공동 1") == "경남 진주시"
    assert LW.lawd_for("서울특별시 강동구 천호동 1", {}) == "11740"
    assert LW.lawd_for("경상남도 진주시 충무공동 1", {}) is None
    assert LW.lawd_for("경상남도 진주시 충무공동 1", {"경남 진주시": {"code": "48170"}}) == "48170"


def test_reverse_ok_and_match():
    info, msg = LW.reverse(35.1, 128.1, H(R(200, gc("4817012300", "경상남도", "진주시", "충무공동"))), ("a", "b"))
    assert info["code"] == "48170" and msg == "ok"
    assert LW.matches("경상남도 진주시 충무공동 1", info)
    assert not LW.matches("경상남도 사천시 사남면 1", info)


def test_reverse_forbidden():
    info, msg = LW.reverse(35.1, 128.1, H(R(403, {})), ("a", "b"))
    assert info is None and "Reverse Geocoding" in msg
