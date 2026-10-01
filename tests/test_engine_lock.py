"""청약봇(기능 chatbot)을 붙이면서 판정 엔진 함수가 바뀌지 않았는지 (tools/engine_lock.py)."""
from tools.engine_lock import check, ENGINE, bodies, ROOT


def test_engine_functions_unchanged():
    assert check() == [], "판정 함수가 바뀌었어요. 의도한 판정 수정이면 판정 사례·회귀 검사 후 python -m tools.engine_lock --update"


def test_engine_functions_found():
    b = bodies((ROOT / "docs" / "index.html").read_text(encoding="utf-8"))
    assert all(b[k] for k in ENGINE)
