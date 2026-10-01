"""청약봇 근거용 모집공고문 조각 (기능: chatbot, 2026-10-02 — '필요 서류'를 공고문에서 찾아 답하도록).
공고문 글을 문단 단위 약 800자 조각으로 나눠 docs/chat-notice/<공고번호>.json 에 쓴다. 판정에는 쓰지 않는다."""
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "docs" / "chat-notice"
HEAD = re.compile(r"^\s*(?:[■□◆◇●○▶▣※]|\d{1,2}\s*[.)]|[가-하]\s*[.)]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.)]?)")


def chunk_text(text: str, size: int = 800) -> list[dict]:
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n")]
    lines = [l for l in lines if l and not re.fullmatch(r"-\s*\d+\s*-", l)]   # 쪽 번호 줄 빼기
    out, cur, head = [], [], ""
    for l in lines:
        if HEAD.match(l) and len(l) < 60:
            head = l
        if sum(len(x) for x in cur) + len(l) > size and cur:
            out.append({"h": cur_head, "t": "\n".join(cur)})
            cur = []
        if not cur:
            cur_head = head
        cur.append(l)
    if cur:
        out.append({"h": cur_head, "t": "\n".join(cur)})
    return out


def write(nid: str, name: str, pdf, text: str) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    ch = chunk_text(text)
    (DIR / f"{nid}.json").write_text(json.dumps({"nid": nid, "name": name, "pdf": pdf, "chunks": ch}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(ch)


def has(nid: str) -> bool:
    return (DIR / f"{nid}.json").exists()
