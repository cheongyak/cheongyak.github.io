"""오늘 고칠 '못 읽음' 목록 (tools/qa/unread_queue.py, 2026-10-22 아침 자동 고치기)."""
import json
import subprocess
from pathlib import Path

from tools.qa import unread_queue as U

ROOT = Path(__file__).resolve().parent.parent


def test_queue_replays_20261022_morning(tmp_path, monkeypatch):
    """10-22 07:40 실제 상태(474570dc)를 다시 보면, 그날 손으로 고친 4건(영흥숲·향남 롯데캐슬·LH 2건)을 모두 잡는다"""
    for f in ("docs/listings.json", "docs/verify-status.json", "docs/run-log.txt", "evidence/qa/lh-unread.json", "evidence/qa/lh-invariants.json"):
        r = subprocess.run(["git", "show", f"474570dc:{f}"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            import pytest
            pytest.skip("얕은 clone")
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text(r.stdout, encoding="utf-8")
    monkeypatch.setattr(U, "ROOT", tmp_path)
    q = U.build()
    assert {i["nid"] for i in q["items"]} == {"2026930044", "2026000502", "0000061187", "2015122300020930"}
    yh = next(i for i in q["items"] if i["nid"] == "2026930044")
    assert any("세대주" in p["msg"] for p in yh["problems"])


def test_market_notes_are_not_queued(tmp_path, monkeypatch):
    """시세 참고(마진율 이례적 등)는 읽기 규칙 일이 아니라 넣지 않는다"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "listings.json").write_text(json.dumps([{"id": "2026000001-084.0000A", "name": "가", "checks": ["마진율 -63%는 이례적이에요. 시세 근거를 확인하세요"]}]), encoding="utf-8")
    monkeypatch.setattr(U, "ROOT", tmp_path)
    assert U.build()["count"] == 0
