"""수집 멈춤 감시(tools/qa/freshness.py)·저장 재시도(tools/qa/push_retry.sh) — 2026-10-22 LH 임대 수집이 이틀 올라가지 않은 일."""
import json
import re
from datetime import datetime
from pathlib import Path

from tools.qa.freshness import KST, check, lines

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 22, 7, 0, tzinfo=KST)


def _repo(tmp_path, lh="2026-10-20 12:41", sh="2026-10-22 06:51", sale="2026-10-22 05:40", feats=None):
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "updated.txt").write_text(sale + "\n", encoding="utf-8")
    (d / "lh-rental.json").write_text(json.dumps({"updated": lh, "notices": []}), encoding="utf-8")
    (d / "sh-rental.json").write_text(json.dumps({"updated": sh, "notices": []}), encoding="utf-8")
    (d / "gh-rental.json").write_text(json.dumps({"updated": "2026-10-01 07:00"}), encoding="utf-8")
    (d / "config.json").write_text(json.dumps({"features": feats if feats is not None else {"gh_rental": False, "pvt_rental": False, "lh_welfare": False}}), encoding="utf-8")
    return tmp_path


def test_lh_stall_of_10_20_is_caught(tmp_path):
    r = check(_repo(tmp_path), NOW)
    assert r["stale"] == 1
    assert [i["name"] for i in r["items"] if i["stale"]] == ["LH 임대"]
    assert "42시간" in r["warnings"][0] and "2026-10-20 12:41" in r["warnings"][0]
    out = lines(r)
    assert out[0].startswith("[경고·수집 멈춤]")   # 수집 알림 이슈는 '[경고' 로 시작하는 줄을 모은다 (collect.yml)
    assert out[-1].startswith("[수집 신선도]")


def test_daily_run_is_fresh(tmp_path):
    r = check(_repo(tmp_path, lh="2026-10-21 06:45"), NOW)   # 하루 한 번 + 예약 지연은 26시간 안
    assert r["stale"] == 0 and r["warnings"] == []
    assert lines(r)[-1].endswith("정상")


def test_switched_off_sources_are_not_watched(tmp_path):
    r = check(_repo(tmp_path, lh="2026-10-21 06:45"), NOW)
    assert "GH 임대" not in [i["name"] for i in r["items"]]   # gh_rental 꺼짐 → 오래돼도 경고 없음
    r = check(_repo(tmp_path / "on", lh="2026-10-21 06:45", feats={}), NOW)   # 적혀 있지 않으면 켜짐
    assert "GH 임대" in [i["name"] for i in r["items"] if i["stale"]]
    assert "공공지원 민간임대" in [i["name"] for i in r["items"] if i["stale"]]   # 켰는데 파일이 없으면 그것도 경고


def test_unreadable_time_is_a_warning(tmp_path):
    root = _repo(tmp_path)
    (root / "docs" / "sh-rental.json").write_text("{", encoding="utf-8")
    r = check(root, NOW)
    assert any("SH 임대" in w and "읽지 못함" in w for w in r["warnings"])


def test_rental_workflows_use_safe_push():
    """저장 단계가 커밋하지 않은 파일 때문에 받기(pull --rebase)에서 멈추지 않게 — push_retry.sh 를 쓴다"""
    for f in ("lh-rental.yml", "sh-rental.yml", "gh-rental.yml", "pvt-rental.yml", "lh-probe.yml"):
        t = (ROOT / ".github" / "workflows" / f).read_text(encoding="utf-8")
        assert "bash tools/qa/push_retry.sh" in t, f
        assert not re.search(r"git push \|\| \(git pull --rebase", t), f
    s = (ROOT / "tools" / "qa" / "push_retry.sh").read_text(encoding="utf-8")
    assert "git stash" in s and "exit 1" in s


def test_verify_status_carries_warnings():
    t = (ROOT / "tools" / "verify_status.py").read_text(encoding="utf-8")
    assert '"warnings": fresh["warnings"]' in t and "[경고·수집 멈춤]" in t
