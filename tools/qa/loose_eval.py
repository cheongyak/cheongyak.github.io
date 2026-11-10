"""느슨한 읽기(기능 loose_read) 평가 — 로컬 확인용, 네트워크 없음.

1) 지금 규칙: 저장된 LH 원문(evidence/lh) 전부를 엄격 ↔ 느슨하게 채운 결과로 비교해, 느슨한 읽기가 채운 칸을 모두 보여 준다(정답 데이터와 다르면 '틀림').
2) 과거 재현(--history): app/lh_terms.py 를 고친 커밋마다 '고치기 전 규칙'으로 읽어, 그 커밋이 고친 공고를 느슨한 읽기가 미리 읽었을지 센다.
실행: python -m tools.qa.loose_eval [--history] [--json evidence/qa/loose-eval.json]
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import loose_read  # noqa: E402


def meta() -> dict:
    out = {}
    for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8")):
        out.setdefault(n["id"], {}).update(region=n.get("region"), type=n.get("type"), name=n.get("name") or "")
    for n in json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]:
        out.setdefault(n["id"], {}).update(type=n["type"], name=n.get("verified_from", ""))
    try:
        for n in json.loads((ROOT / "docs/lh-rental.json").read_text(encoding="utf-8"))["notices"]:
            out.setdefault(n["id"], {}).update(type=n["type"], name=n.get("name") or "", region=n.get("region"))
    except Exception:
        pass
    return {k: v for k, v in out.items() if v.get("type")}


def texts() -> dict:
    return {f.stem: f.read_text(encoding="utf-8", errors="replace") for f in sorted((ROOT / "evidence/lh").glob("*.txt"))}


def core(r: dict) -> dict:
    """비교용 — 인용문·기록은 빼고 값만"""
    r = copy.deepcopy(r)
    r.pop("quotes", None); r.pop("loose", None)
    if isinstance(r.get("local"), dict):
        r["local"].pop("quote", None)
    return json.loads(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str))


def load_old(sha: str):
    src = subprocess.run(["git", "show", f"{sha}:app/lh_terms.py"], cwd=ROOT, capture_output=True, text=True).stdout
    if not src:
        return None
    f = Path(tempfile.mkdtemp()) / f"lh_terms_{sha}.py"
    f.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"lh_terms_{sha}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, tx, m, fill: bool):
    try:
        if fill:
            return loose_read.parse_lh_terms(tx, m["type"], m.get("name", ""), m.get("region"), mod=mod)
        return mod.parse_lh_terms(tx, m["type"], m.get("name", ""), m.get("region"))
    except TypeError:   # 옛 규칙: region 인자가 없던 때
        return mod.parse_lh_terms(tx, m["type"], m.get("name", ""))
    except Exception as e:
        return {"error": str(e)[:80]}


def now() -> list[dict]:
    from app import lh_terms
    M, T = meta(), texts()
    out = []
    for nid, tx in T.items():
        if nid not in M:
            continue
        s, l = run(lh_terms, tx, M[nid], False), run(lh_terms, tx, M[nid], True)
        if l.get("loose"):
            out.append({"id": nid, "type": M[nid]["type"], "filled": l["loose"], "strict": core(s), "loose": core(l), "quotes": l.get("quotes")})
    return out


def history() -> list[dict]:
    M, T = meta(), texts()
    shas = subprocess.run(["git", "log", "--format=%h %ad %s", "--date=short", "--", "app/lh_terms.py"], cwd=ROOT, capture_output=True, text=True).stdout.strip().splitlines()
    rows = []
    for line in shas:
        sha, date, subj = line.split(" ", 2)
        new, old = load_old(sha), load_old(sha + "^")
        if not new or not old or not hasattr(old, "parse_lh_terms"):
            continue
        for nid, tx in T.items():
            if nid not in M:
                continue
            a, b = core(run(old, tx, M[nid], False)), core(run(new, tx, M[nid], False))
            if a == b or "error" in a or "error" in b:
                continue
            c = core(run(old, tx, M[nid], True))
            # 고친 칸: 옛 규칙이 못 읽고(None·없음) 새 규칙이 읽은 것 / 값이 바뀐 것(느슨한 읽기는 바꾸지 않으므로 대상 아님)
            res = "읽음(새 규칙과 같음)" if c == b else "효과 없음" if c == a else "일부·다름"
            rows.append({"commit": sha, "date": date, "subject": subj[:60], "id": nid, "type": M[nid]["type"], "result": res,
                         "diff": None if res != "일부·다름" else {"old": a, "new": b, "loose": c}})
    return rows


def main() -> int:
    res = {"now": now()}
    print(f"[느슨한 읽기 평가] 지금 규칙 · 저장 원문에서 채운 공고 {len(res['now'])}건")
    for r in res["now"]:
        print("  ", r["id"], r["type"], r["filled"])
    if "--history" in sys.argv:
        res["history"] = history()
        from collections import Counter
        c = Counter(r["result"] for r in res["history"])
        print(f"[느슨한 읽기 평가] 과거 재현 · 규칙 커밋이 고친 (커밋·공고) {len(res['history'])}건: {dict(c)}")
        for r in res["history"]:
            print("  ", r["date"], r["commit"], r["id"], r["type"], r["result"], "·", r["subject"])
    if "--json" in sys.argv:
        p = ROOT / sys.argv[sys.argv.index("--json") + 1]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
