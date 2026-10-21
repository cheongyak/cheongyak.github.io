"""청약홈 공고 누락 점검 (tools/qa/coverage.py, 2026-10-21) — 가짜 API 로 판정 규칙만 확인한다 (실제 점검은 Actions 수집에서)."""
import json
from datetime import date, timedelta

import tools.qa.coverage as cov


class Fake:
    def __init__(self, rows, models):
        self.rows, self.models = rows, models

    def _get(self, path, page=1, **kw):
        if "Mdl" in path:
            return {"data": self.models.get(kw.get("cond[PBLANC_NO::EQ]"), [])}
        if page > 1:
            return {"data": []}
        return {"data": self.rows.get(path, [])}


def _d(no, name, days_end, days_notice=-5):
    t = date.today()
    return {"HOUSE_MANAGE_NO": no, "PBLANC_NO": no, "HOUSE_NM": name, "RCRIT_PBLANC_DE": (t + timedelta(days=days_notice)).isoformat(),
            "RCEPT_BGNDE": (t + timedelta(days=days_end - 2)).isoformat(), "RCEPT_ENDDE": (t + timedelta(days=days_end)).isoformat()}


def test_missing_and_excluded(tmp_path, monkeypatch):
    rows = {"/getAPTLttotPblancDetail": [_d("A1", "화면에 있음", 3), _d("A2", "빠진 공고", 3), _d("A3", "공급 0", 3), _d("A4", "끝난 공고", -40)],
            "/getRemndrLttotPblancDetail": [], "/getOPTLttotPblancDetail": [_d("O1", "임의공급", 2)],
            "/getUrbtyOfctlLttotPblancDetail": [], "/getPblPvtRentLttotPblancDetail": []}
    models = {"A2": [{"SUPLY_HSHLDCO": "10", "SPSPLY_HSHLDCO": "5"}], "A3": [{"SUPLY_HSHLDCO": "0", "SPSPLY_HSHLDCO": "0"}]}
    monkeypatch.setattr(cov, "ApplyhomeClient", lambda: Fake(rows, models))
    (tmp_path / "docs").mkdir(); (tmp_path / "evidence/qa").mkdir(parents=True)
    (tmp_path / "docs/listings.json").write_text(json.dumps([{"id": "A1-084.0000A"}]), encoding="utf-8")
    monkeypatch.setattr(cov, "ROOT", tmp_path)
    assert cov.main() == 1
    r = json.loads((tmp_path / "evidence/qa/coverage.json").read_text(encoding="utf-8"))
    assert [m.split()[1] for m in r["missing"]] == ["A2"]
    assert [m.split()[1] for m in r["excluded"]] == ["A3"]
    assert len(r["uncollected"]["임의공급"]) == 1
