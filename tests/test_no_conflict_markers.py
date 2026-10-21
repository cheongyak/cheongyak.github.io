"""병합 충돌 표시가 커밋되지 않게 (2026-10-22 두 세션이 PARSER_VERSION 을 같은 번호로 올려 app/pipeline.py·tests/qa/parse_snapshot.json 에
'<<<<<<< Updated upstream' 이 그대로 올라감 → 수집이 import 에서 멈출 뻔함)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = re.compile(r"^(<<<<<<< |>>>>>>> )", re.M)


def test_no_merge_conflict_markers_in_tracked_text():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    bad = []
    for f in files:
        if not f.endswith((".py", ".json", ".yml", ".yaml", ".md", ".html", ".js", ".mjs", ".cjs", ".sh", ".txt", ".toml")) or f.startswith("evidence/"):
            continue
        try:
            t = (ROOT / f).read_text(encoding="utf-8")
        except Exception:
            continue
        if MARK.search(t):
            bad.append(f)
    assert not bad, bad
