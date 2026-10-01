"""판정 엔진 잠금 (기능: chatbot, 2026-10-01). 청약봇은 판정 엔진 결과를 읽기만 하고 엔진 코드는 바꾸지 않는다.
docs/index.html 의 판정 함수 본문을 함수별 지문(sha256)으로 tools/engine_lock.json 과 비교한다. 다르면 tests/test_engine_lock.py 가 실패한다.
판정 규칙을 일부러 고친 커밋에서만(판정 사례·회귀 검사를 함께 돌린 뒤) `python -m tools.engine_lock --update` 로 지문을 새로 쓴다."""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "tools" / "engine_lock.json"
ENGINE = ["eligibility", "spJudge", "myScore", "mcScore", "pubPoints", "townItems", "pubGeneralItems", "residenceItem", "accountItems",
          "regulatedItems", "grade", "funding", "itemBasis", "cpExplain", "rewinTarget", "incomeNeedsHh", "relaxLimit", "acctScoreMonths",
          "parentHouseMissing", "optDefaults", "ownExcept", "eligBucket", "spTypesFor", "pendingChecks", "fromApi", "statusOf", "syncHome", "syncV2"]


def bodies(html: str) -> dict:
    out = {}
    for name in ENGINE:
        m = re.search(rf"^(?:async )?function {name}\(|^const {name} = ", html, re.M)
        if not m:
            out[name] = None
            continue
        start = m.start()
        if html[start:].startswith("const"):   # 한 줄 정의
            end = html.index("\n", start)
        else:                                   # 맨 앞 칸의 '}' 까지
            end = html.index("\n}", start) + 2
        out[name] = hashlib.sha256(html[start:end].encode()).hexdigest()[:16]
    return out


def check() -> list:
    now = bodies((ROOT / "docs" / "index.html").read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    return [k for k in ENGINE if now.get(k) != lock.get(k)]


if __name__ == "__main__":
    if "--update" in sys.argv:
        LOCK.write_text(json.dumps(bodies((ROOT / "docs" / "index.html").read_text(encoding="utf-8")), indent=1) + "\n", encoding="utf-8")
        print("[엔진 잠금] 지문을 새로 썼어요")
    else:
        bad = check()
        print("[엔진 잠금] " + ("판정 함수 그대로" if not bad else "바뀐 판정 함수: " + ", ".join(bad)))
        sys.exit(1 if bad else 0)
