"""세션이 공고문을 직접 읽어 쓴 답을 답 파일로 싣는다 (기능 ai_read·ai_read_sale, 2026-11-12 운영자 'AI 호출은 네가 직접 열어 보는 걸로. API 키는 청약봇만').

수집은 Claude API 를 부르지 않는다. 규칙이 못 읽은 공고는 세션(운영자와 일하는 Claude·아침 자동 고치기)이 원문을 읽고 여기로 답을 넣는다.
답은 수집 때와 똑같은 검사기(app/ai_read: 근거 문장이 원문에 그대로·값이 그 문장 안·범위)를 거친다 — 통과한 값만 화면에 실린다.

  python -m tools.ai_answer todo                    못 읽은 칸이 있는데 답 파일이 없는 공고와 원문 위치
  python -m tools.ai_answer format lh|sale          답 JSON 형식(지시문)
  python -m tools.ai_answer excerpt <주택관리번호>   분양 공고문에서 거주 요건·거주의무 둘레만 뽑아 보기(긴 공고문)
  python -m tools.ai_answer lh <공고ID> <답.json>    LH 임대 — 검사 결과를 보여 주고 evidence/lh/ai/<공고ID>.json 에 씀
  python -m tools.ai_answer sale <주택관리번호> <답.json>   분양 — evidence/notices/ai/<번호>.json 에 씀
  (--dry: 검사만 하고 쓰지 않음)

쓴 뒤: LH 는 `python -m tools.qa.lh_reparse` 로 화면 데이터에 어떻게 실리는지 보고(확인 뒤 git checkout docs/lh-rental.json), 답 파일을 커밋한다. 다음 수집부터 실린다.
답 파일은 임시방편이다 — 읽기 규칙·정답 데이터를 더하는 일(AUTOFIX.md 2번)이 본 처리다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import ai_read  # noqa: E402


def _lh_notices() -> dict:
    return {n["id"]: n for n in json.loads((ROOT / "docs/lh-rental.json").read_text(encoding="utf-8"))["notices"]}


def _lh_texts(nid: str) -> dict:
    from tools.qa.lh_pdf_tools import texts_of
    return texts_of(nid)


def _sale_text(nid: str) -> str:
    from app import notice_chunks
    t = notice_chunks.text_of(nid)
    if t:
        return t
    for d in ("evidence/notices", "evidence/qa/notices"):
        f = ROOT / d / f"{nid}.txt"
        if f.exists():
            return f.read_text(encoding="utf-8", errors="replace")
    return ""


def _has(d: Path, nid: str, v: int) -> bool:
    try:
        return json.loads((d / f"{nid}.json").read_text(encoding="utf-8")).get("prompt_v") == v
    except Exception:
        return False


def todo() -> int:
    n = 0
    for nid, N in _lh_notices().items():
        if not N.get("judge_type"):
            continue
        T = N.get("terms_pre_ai", N.get("terms"))
        need = ai_read.gaps(T, N["type"])
        if need and not _has(ai_read.DIR, nid, ai_read.PROMPT_V):
            n += 1
            print(f"[LH] {nid} {N['type']} {N.get('name')} — 못 읽은 칸 {', '.join(need)} · 원문 evidence/lh/{nid}.txt")
    seen = set()
    for L in json.loads((ROOT / "docs/listings.json").read_text(encoding="utf-8")):
        nid = str(L["id"]).split("-")[0]
        need = ([] if L.get("residence") else ["residence"]) + (["residence_duty"] if L.get("residence_duty") is None and not L.get("duty_silent") else [])
        if not need or nid in seen or not L.get("notice_pdf") or (L.get("status") or "") in ("마감", "closed"):
            continue
        seen.add(nid)
        if not _has(ai_read.SALE_DIR, nid, ai_read.SALE_PROMPT_V):
            n += 1
            print(f"[분양] {nid} {L.get('name')} — 못 읽은 항목 {', '.join(need)} · 원문 `python -m tools.ai_answer excerpt {nid}`")
    print(f"답 파일이 없는 공고 {n}건")
    return 0


def main() -> int:
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    dry = "--dry" in sys.argv
    if not a or a[0] == "todo":
        return todo()
    if a[0] == "format":
        print(ai_read.SYSTEM if a[1] == "lh" else ai_read.SYSTEM_SALE)
        return 0
    if a[0] == "excerpt":
        print(ai_read.sale_excerpt(_sale_text(a[1])))
        return 0
    kind, nid, ans = a[0], a[1], json.loads(Path(a[2]).read_text(encoding="utf-8"))
    if kind == "lh":
        N, tx = _lh_notices().get(nid), _lh_texts(nid)
        if not N or not tx:
            print(f"공고 {nid} 가 docs/lh-rental.json 에 없거나 원문(evidence/lh)이 없음")
            return 1
        val, dropped = ai_read.to_terms(ans, list(tx.values()), N.get("region"), N["type"])
        print("검사 통과:", json.dumps({k: v for k, v in val.items() if k != "quotes"}, ensure_ascii=False))
        for d in dropped:
            print("  탈락:", d)
        need = ai_read.gaps(N.get("terms_pre_ai", N.get("terms")), N["type"])
        print("화면이 '공고문 확인'으로 보이는 칸:", ", ".join(need) or "없음(답을 써도 실리는 값이 없음)")
        if not dry:
            print("씀:", ai_read.save_answer("lh", nid, ans, next(iter(tx.values()))).relative_to(ROOT))
        return 0
    if kind == "sale":
        text = _sale_text(nid)
        if not text:
            print(f"공고 {nid} 원문(docs/chat-notice·evidence/notices)이 없음")
            return 1
        hints, dropped = ai_read.sale_hints(ans, [text])
        print("검사 통과:", json.dumps({k: v["text"] for k, v in hints.items()}, ensure_ascii=False))
        for d in dropped:
            print("  탈락:", d)
        if not dry:
            print("씀:", ai_read.save_answer("sale", nid, ans, text).relative_to(ROOT))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
