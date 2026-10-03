"""공고문 읽기 결과 고정 (2026-10-03 사용자 '최신 수정이 이전 정상값에 영향을 주지 않게').
모아 둔 공고문 원문(evidence/notices, evidence/qa/notices)마다 parse_notice 결과를 tests/qa/parse_snapshot.json 에 고정해 두고,
tests/test_parse_snapshot.py 가 매번 같은지 본다. 읽기 규칙을 고쳐 값이 바뀌면 테스트가 실패하며 어느 공고의 어느 값이 어떻게 바뀌었는지 보여 준다.
바뀐 값이 모두 원문과 대조해 맞는(의도한) 변경일 때만 기준을 새로 쓴다:
  python -m tools.qa.parse_snapshot           # 지금 기준과 다른 곳 보기
  python -m tools.qa.parse_snapshot --update  # 기준 새로 쓰기 (WORK.md 에 바뀐 공고·값을 적는다)
새로 모인 원문(기준에 없는 파일)과 글이 바뀐 원문(다시 받아 글자가 달라진 파일, 원문 글 지문 sha 로 확인)은 비교하지 않는다 —
읽기 규칙이 아니라 원문이 바뀐 것이라서. 매일 수집 첫 단계의 pytest 를 막지 않게 하려는 것 (--update 때 새 지문으로 기준을 쓴다)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "tests" / "qa" / "parse_snapshot.json"
DIRS = (ROOT / "evidence" / "notices", ROOT / "evidence" / "qa" / "notices")


def originals() -> dict[str, Path]:
    out = {}
    for d in DIRS:
        for f in sorted(d.glob("*.txt")):
            out.setdefault(f.stem, f)   # 지금 공고 원문을 먼저
    return out


def current() -> dict:
    from app import notice_pdf
    res = {}
    for no, f in originals().items():
        text = f.read_text(encoding="utf-8")
        r = notice_pdf.parse_notice(text)
        cx = notice_pdf.parse_complex(text)
        if cx:
            r["complex"] = cx
        res[no] = {"sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                   "parse": json.loads(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str))}
    return res


def diff(old: dict, new: dict) -> list[str]:
    """같은 원문 글(sha 같음)인데 읽은 값이 달라진 곳만. 원문 파일이 없어졌거나 글이 바뀐 곳은 건너뛴다."""
    lines = []
    for no in sorted(old):
        if no not in new or old[no].get("sha") != new[no]["sha"]:
            continue
        a, b = old[no]["parse"], new[no]["parse"]
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                sa, sb = json.dumps(a.get(k), ensure_ascii=False)[:160], json.dumps(b.get(k), ensure_ascii=False)[:160]
                lines.append(f"{no} {k}: {sa} → {sb}")
    return lines


def main() -> None:
    new = current()
    old = json.loads(SNAP.read_text(encoding="utf-8")) if SNAP.exists() else {}
    d = diff(old, new)
    added = sorted(set(new) - set(old))
    moved = sorted(n for n in old if n in new and old[n].get("sha") != new[n]["sha"])
    print(f"[공고문 읽기 고정] 원문 {len(new)}건 · 기준 {len(old)}건 · 바뀐 값 {len(d)} · 새 원문 {len(added)} · 글이 바뀐 원문(비교 안 함) {len(moved)}")
    for line in d[:200]:
        print("  " + line)
    if "--update" in sys.argv:
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(new, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print(f"기준을 새로 썼어요 ({len(new)}건)")


if __name__ == "__main__":
    main()
