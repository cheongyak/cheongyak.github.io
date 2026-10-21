"""청약봇 V2 엔진(chat/v2)을 화면이 부를 수 있게 docs/bot/v2/ 로 복사한다 (기능 bot_find, 2026-10-21).
고칠 때는 chat/v2 를 고치고 이 도구를 돌린다 — docs/bot/v2 를 직접 고치지 않는다(tests/test_bot_find.py 가 같은지 확인).
실행: python -m tools.sync_bot"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC, DST = ROOT / "chat/v2", ROOT / "docs/bot/v2"
FILES = ["index.mjs", "extract.mjs", "search.mjs", "answer.mjs", "llm.mjs", "lexicon.mjs", "browser.mjs", "data/lines.json"]
HEAD = "// 자동 복사본 — chat/v2/{} 를 고치고 python -m tools.sync_bot 으로 다시 복사하세요 (기능 bot_find)\n"


def copied(name: str) -> str:
    t = (SRC / name).read_text(encoding="utf-8")
    return t if name.endswith(".json") else HEAD.format(name) + t


def main() -> None:
    for f in FILES:
        p = DST / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(copied(f), encoding="utf-8")
    print(f"[청약봇 엔진 복사] {len(FILES)}개 → docs/bot/v2")


if __name__ == "__main__":
    main()
