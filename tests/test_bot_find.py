"""청약봇 '공고 찾기' (기능 bot_find, 2026-10-21): 화면이 부르는 엔진 복사본(docs/bot/v2)이 chat/v2 와 같은지 (tools/sync_bot.py 로만 바꾼다)."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bot_engine_copy_in_sync():
    from tools.sync_bot import FILES, DST, copied
    for f in FILES:
        assert (DST / f).read_text(encoding="utf-8") == copied(f), f"docs/bot/v2/{f} 가 chat/v2 와 다름 — python -m tools.sync_bot"


def test_bot_profile_parser_tests_pass():
    r = subprocess.run(["node", "--test", "tests/bot/profile.test.mjs"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_screen_hooks():
    h = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    for k in ("function botFindBox", "function vBot", "function botAct", "bot:vBot", "'cy-bot-preview'", "import('./bot/find.mjs')"):
        assert k in h, k
    import json
    assert json.loads((ROOT / "docs/config.json").read_text(encoding="utf-8"))["features"]["bot_find"] is False   # 미리보기(?bot=1) 확인 뒤 켬
