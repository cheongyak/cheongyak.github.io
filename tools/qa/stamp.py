"""검사 결과가 '어느 데이터·화면 코드로 돌린 것인지' 도장 찍기 (2026-10-21 사용자 '이런 실수로 베타 참고용이 나오지 않도록').

배경: 검사 결과(evidence/qa/*.json)는 저장소에 남아 여러 워크플로가 함께 읽는다. 10-21 아침 수집이 전날 LH 수집 때의
'임대 못 읽음' 결과(그 뒤 SH 를 다시 수집해 이미 해결)를 그대로 세어 검증 실패 → 화면에 '베타 참고용'이 떴다.
같은 위험: 수집(collect)은 input_nav·LH 검사를 돌리지 않고, 공고문 재시도(notice-retry)는 검사를 하나도 돌리지 않은 채 요약을 만든다.

규칙
 - 이번 실행에서 새로 쓴 결과(저장소 HEAD 와 내용이 다르거나 새 파일)에는 지금 데이터의 지문(_data)을 찍는다.
 - 다시 쓰지 않은 결과는 찍혀 있던 지문을 지금 데이터와 비교해, 다르면 '지난 결과'로 보고 통과·실패를 세지 않는다
   (tools/verify_status.py 가 [검증·지난 결과] 줄과 verify-status.json qa_stale 로 남긴다).
 - 데이터를 바꾸는 워크플로(수집·공고문 재시도·LH·SH 임대 수집)는 저장 뒤 판정 검증(verify.yml)을 다시 돌려 지난 결과가 오래 남지 않게 한다.
실행: python -m tools.qa.stamp  (워크플로에서 검사 결과를 git add 하기 전에)"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "evidence" / "qa"

# 검사 결과 → 그 결과가 기대는 것 (listings·lh·sh = 수집 데이터, code = 화면 판정 코드 docs/index.html)
DEPS = {
    "supply-type.json": ("listings", "code"), "invariants.json": ("listings",), "filter-check.json": ("listings", "code"),
    "consistency.json": ("listings", "code"), "sp-text.json": ("listings", "code"), "market-check.json": ("listings",),
    "cross-rule.json": ("listings", "code"), "profile-keep.json": ("code",), "monotonic.json": ("listings", "code"),
    "snapshot.json": ("code",), "e2e.json": ("listings", "code"), "past-chat.json": ("listings", "code"),
    "pay-audit.json": ("listings",), "parse-moved.json": ("listings",), "zero-default.json": ("listings", "code"),
    "input-nav.json": ("listings", "code"), "coverage.json": ("listings",), "verify-scope.json": ("listings", "lh", "code"), "rent-org.json": ("lh", "sh", "gh", "pvt", "lw", "local", "code"),
    "lh-invariants.json": ("lh",), "lh-qa.json": ("lh", "sh", "gh", "pvt", "lw", "local", "code"), "lh-screen.json": ("lh", "sh", "gh", "pvt", "lw", "local", "code"),
    "lh-unread.json": ("lh", "sh", "gh", "pvt", "lw", "local", "code"), "lh-pdf-tools.json": ("lh",),
}
SRC = {"listings": "docs/listings.json", "lh": "docs/lh-rental.json", "sh": "docs/sh-rental.json", "gh": "docs/gh-rental.json", "pvt": "docs/pvt-rental.json", "local": "docs/local-rental.json", "lw": "docs/lh-welfare.json", "code": "docs/index.html"}


def current() -> dict:
    out = {}
    for k, f in SRC.items():
        p = ROOT / f
        out[k] = hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p.exists() else None
    return out


def want(name: str, cur: dict | None = None) -> dict:
    cur = cur or current()
    return {k: cur[k] for k in DEPS.get(name, ())}


def rewritten(p: Path) -> bool:
    """이번 실행에서 새로 쓴 파일인지 — 저장소 HEAD 와 내용이 다르거나 아직 저장소에 없음. git 이 없으면 새로 쓴 것으로 본다"""
    rel = str(p.relative_to(ROOT))
    try:
        if subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode != 0:
            return True
        return subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT, capture_output=True).returncode != 0
    except Exception:
        return True


def stamp_all() -> list[str]:
    """새로 쓴 검사 결과에 지금 데이터 지문을 찍는다 (이미 같은 지문이면 그대로)"""
    cur, done = current(), []
    for name in DEPS:
        p = QA / name
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        # 검사 도구는 지문을 쓰지 않으므로, 지문이 없으면 이번에 새로 쓴 결과다 — 저장소에 있던 결과에는 늘 지문이 있다.
        # (처음 한 번: 지문 도입 전에 저장된 결과도 지문이 없어 새 결과로 본다 — 도입 직후 판정 검증이 모두 다시 돌려 덮는다)
        if "_data" in d and not rewritten(p):
            continue
        w = want(name, cur)
        if d.get("_data") != w:
            d["_data"] = w
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        done.append(name)
    return done


def is_current(name: str, d: dict | None, cur: dict | None = None) -> bool:
    return bool(d) and isinstance(d, dict) and d.get("_data") == want(name, cur)


if __name__ == "__main__":
    n = stamp_all()
    print(f"[검사 결과 도장] 이번에 새로 쓴 결과 {len(n)}개: {' '.join(n) or '-'}")
    sys.exit(0)
