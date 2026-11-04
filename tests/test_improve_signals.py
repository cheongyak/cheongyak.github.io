"""자동 개선 루프 신호 모으기(tools/qa/improve_signals.py) — 네트워크 없이."""
import json

from tools.qa.improve_signals import collect, group_issues, loop_prs


def _repo(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "verify-status.json").write_text(json.dumps({
        "ok": False,
        "flagged": {"SH-1": ["자동 검증(임대 공고문 못 읽음): 청년 소득 기준을 공고문에서 읽지 못함"], "2026000001": ["시세 근거 부족"]},
        "judge": {"total": 10, "passed": 10, "failed": []},
        "crosscheck": {"mismatches": []}, "golden": {"mismatches": []},
        "qa": {"gate": True, "filter_fails": 0, "snapshot_diffs": 2},
        "freshness": [{"name": "LH 임대", "hours": 30, "stale": True}, {"name": "분양", "hours": 3, "stale": False}],
        "warnings": [],
    }), encoding="utf-8")
    (d / "run-log.txt").write_text("[수집] 공고 10건\n[검증·정답 불일치] 2026000001 분양가\n[청약봇] 2026-11-03 질문 2건 · 👍0 👎1 · 7일 질문 2건\n", encoding="utf-8")
    (d / "config.json").write_text(json.dumps({"features": {"a": True, "b": False}}), encoding="utf-8")
    a = tmp_path / "evidence" / "audit"
    (a / "2026-10-26-blind").mkdir(parents=True)
    (a / "2026-11-02-blind").mkdir(parents=True)
    (a / "2026-10-26-blind" / "README.md").write_text("| 옛 공고 | 값 | x | **앱 오류** | A | **P1** |\n", encoding="utf-8")
    (a / "2026-11-02-blind" / "README.md").write_text(
        "| 공고 | 항목 |\n| --- | --- |\n| 2026000434 제주 | 실거주 의무 | 없음 | 원문 | **앱 오류** | B | **P1** 설명 |\n| 2026000999 | 세대주 | 같음 | **같은 뜻** |\n",
        encoding="utf-8")
    (tmp_path / "HANDOFF.md").write_text("# 인계\n## 진행 중인 일 (기준)\n- 운영자가 켤 것: x\n## 최근 끝난 일\n- y\n", encoding="utf-8")
    return tmp_path


def test_collects_without_network(tmp_path):
    r = collect(_repo(tmp_path))
    keys = {s["key"]: s for s in r["signals"]}
    assert keys["flagged:SH-1"]["owner"] == "아침 자동 고치기"      # 못 읽은 공고는 아침 자동 고치기 몫
    assert keys["flagged:2026000001"]["owner"] is None
    assert "qa:snapshot_diffs" in keys and "qa:filter_fails" not in keys
    assert "stale:LH 임대" in keys and "stale:분양" not in keys
    assert any(k.startswith("runlog:[검증·정답 불일치]") for k in keys)
    assert any(k.startswith("bot-down:") for k in keys)
    audit = [s for s in r["signals"] if s["key"].startswith("audit:")]
    assert len(audit) == 1 and "2026-11-02-blind" in audit[0]["key"] and audit[0]["severity"] == "P1"   # 가장 최근 보고의 '앱 오류'만
    assert "b" in keys["features-off"]["detail"]
    assert "운영자가 켤 것" in r["handoff"]["text"] and "최근 끝난 일" not in r["handoff"]["text"]
    assert r["loop_prs"] == [] and r["gh"] is False


def test_keys_are_stable(tmp_path):
    root = _repo(tmp_path)
    assert [s["key"] for s in collect(root)["signals"]] == [s["key"] for s in collect(root)["signals"]]


def test_issue_groups_and_loop_prs():
    issues = [{"number": n, "title": f"판정 검증 실패 2026-11-0{n % 5}"} for n in range(1, 6)] + [{"number": 9, "title": "PR", "pull_request": {}}]
    g = group_issues(issues)
    assert len(g) == 1 and g[0]["title"] == "열린 이슈 '판정 검증 실패' 5건" and g[0]["severity"] == "P1"
    prs = [{"number": 3, "title": "t", "labels": [{"name": "auto-improve"}], "head": {"ref": "auto/x"}, "state": "closed", "merged_at": "2026-11-05"},
           {"number": 4, "title": "u", "labels": [], "head": {"ref": "y"}, "state": "open"}]
    assert [p["number"] for p in loop_prs(prs)] == [3]
