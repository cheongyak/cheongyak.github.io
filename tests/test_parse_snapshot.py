"""공고문 읽기 결과가 고정 기준과 같다 (2026-10-03 사용자 '최신 수정이 이전 정상값에 영향을 주지 않게').
읽기 규칙을 고쳐 기준과 달라지면 실패하고, 어느 공고의 어느 값이 어떻게 바뀌었는지 보여 준다.
바뀐 값을 원문과 대조해 모두 맞으면 `python -m tools.qa.parse_snapshot --update` 로 기준을 새로 쓰고 WORK.md 에 적는다."""
import json

from tools.qa import parse_snapshot as PS


def test_parse_results_match_snapshot():
    old = json.loads(PS.SNAP.read_text(encoding="utf-8"))
    assert len(old) >= 100
    new = PS.current()
    d = PS.diff(old, new)
    assert not d, "공고문 읽기 결과가 기준과 달라요 (의도한 변경이면 원문 대조 후 --update):\n" + "\n".join(d[:40])
