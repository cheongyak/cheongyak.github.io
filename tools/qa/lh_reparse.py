"""저장된 공고문 글(evidence/lh)로 docs/lh-rental.json 의 terms·rents 를 지금 읽기 규칙으로 다시 만든다 (네트워크 없음, 로컬 확인용).
읽기 규칙(app/lh_terms·lh_pdf_merge)을 고친 뒤 화면 검사(lh_qa·lh_rental.cjs)를 새 데이터로 돌릴 때 쓴다.
docs/lh-rental.json 은 Actions 결과물이므로 확인이 끝나면 `git checkout docs/lh-rental.json` 으로 되돌리고 커밋하지 않는다.
실행: python -m tools.qa.lh_reparse"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.lh_pdf_merge import read_all  # noqa: E402
from tools.qa.lh_pdf_tools import texts_of  # noqa: E402


def main() -> int:
    p = ROOT / "docs/lh-rental.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    for N in d.get("notices", []):
        tx = texts_of(N["id"])
        if not tx:
            continue
        tf = ROOT / "evidence/lh/plumber" / f"{N['id']}.tables.json"
        m = read_all(tx, N["type"], N.get("name") or "", N.get("region"), [u["type"] for u in N.get("units") or []], bool(N.get("judge_type")),
                     json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else [])
        if N.get("judge_type") and m["terms"]:
            N["terms"] = m["terms"]
        N["rents"] = m["rents"]
        n += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[LH 다시 읽기] {n}건 — 확인 뒤 git checkout docs/lh-rental.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
