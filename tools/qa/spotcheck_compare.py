"""사람(블라인드 검토자) 원문 대조 30건 ↔ 앱 데이터 비교 (MASTER QA 37항). evidence/qa/spotcheck-blind.json(원문에서 읽은 값)과
지난 공고 보관함(docs/archive/past.json, 청약홈 값)·판정 자료(docs/archive/past-judge.json, 공고문에서 읽은 값)를 항목별로 대조해
PASS / FAIL / NOT_TESTABLE 로 센다. 결과: evidence/qa/spotcheck-result.json. 실행: python -m tools.qa.spotcheck_compare"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def norm_ty(s: str) -> str:
    """'84.9531E' · '084.9531E' → '084.9531E' (청약홈 주택형 표기)"""
    s = s.strip()
    num = "".join(c for c in s if c.isdigit() or c == ".")
    suf = s[len(num):].strip()
    a, _, b = num.partition(".")
    return f"{int(a):03d}.{(b + '0000')[:4]}{suf}"


def main() -> None:
    blind = json.loads((ROOT / "evidence/qa/spotcheck-blind.json").read_text(encoding="utf-8"))["items"]
    arc = json.loads((ROOT / "docs/archive/past.json").read_text(encoding="utf-8"))["items"]
    pj = json.loads((ROOT / "docs/archive/past-judge.json").read_text(encoding="utf-8"))["items"]
    A, J = {}, {}
    for x in arc:
        A.setdefault(x["notice_no"], {})[norm_ty(x["id"].split("-", 1)[1])] = x
    for x in pj:
        J.setdefault(x["id"].split("-")[0], {})[norm_ty(x["id"].split("-", 1)[1])] = x
    res, tally = [], {}
    def rec(no, field, st, detail=""):
        res.append({"id": no, "field": field, "status": st, "detail": detail})
        tally.setdefault(field, {}).setdefault(st, 0)
        tally[field][st] += 1
    for b in blind:
        no, rows = b["id"], A.get(b["id"], {})
        if not rows:
            rec(no, "공고 존재", "FAIL", "보관함에 없음"); continue
        r0 = next(iter(rows.values()))
        want_cat = "remainder" if b["kind"] == "무순위" else "general"
        rec(no, "공급 구분", "PASS" if r0["category"] == want_cat else "FAIL", f"앱 {r0['category']}/{r0.get('kind')} · 원문 {b['kind']}")
        for ty, gen, sp, price in b["types"]:
            k = norm_ty(ty)
            x = rows.get(k)
            if not x:
                rec(no, "주택형", "FAIL", f"{k} 앱에 없음 (앱: {', '.join(sorted(rows))})"); continue
            rec(no, "주택형", "PASS")
            rec(no, "일반 세대수", "PASS" if x.get("households") == gen else "FAIL", f"{k} 앱 {x.get('households')} · 원문 {gen}")
            if sp is None:
                rec(no, "특공 세대수", "NOT_TESTABLE", f"{k} 원문 특공 없음/미기재")
            else:
                have = (x.get("special_units") or {}).get("total")
                rec(no, "특공 세대수", "PASS" if (have or 0) == sp else "FAIL", f"{k} 앱 {have} · 원문 {sp}")
            p = x.get("price")
            ok = p is not None and abs(p * 1e8 - price) < 1e4 * 1.5   # 억 단위 소수 4자리 → 만 원 단위 반올림 허용
            rec(no, "분양가(최고가)", "PASS" if ok else "FAIL", f"{k} 앱 {p}억 · 원문 {price:,}원")
        s = b["sched"]
        # 청약홈 RCEPT_BGNDE(앱 apply)는 일반분양이면 특별공급 접수 시작일, 무순위면 접수일 (청약홈 정의)
        s = [s[0], s[0] if want_cat == "general" and s[0] else s[1], s[2], s[3]]
        app = [None, r0.get("apply"), r0.get("apply_end") or r0.get("apply"), r0.get("winner")]
        for nm, i in (("접수 시작", 1), ("접수 끝", 2), ("당첨 발표", 3)):
            if s[i] is None:
                rec(no, nm, "NOT_TESTABLE")
            else:
                rec(no, nm, "PASS" if app[i] == s[i] else "FAIL", f"앱 {app[i]} · 원문 {s[i]}")
        jr = J.get(no)
        if not jr:
            for nm in ("1순위 세대주 요건", "재당첨 제한", "1순위 가입기간"):
                rec(no, nm, "NOT_TESTABLE", "판정 자료 없음 (6/15 이전 공고 또는 막 마감)")
            continue
        j0 = next(iter(jr.values()))
        if want_cat == "general":
            # 앱의 1순위 세대주 요건 = need_head(공급 전체 대상이 세대주) 또는 규제지역 1순위 규칙(regulated) — 화면 regulatedItems
            head = bool(j0.get("need_head")) or bool(j0.get("regulated"))
            rec(no, "1순위 세대주 요건", "PASS" if head == b["head"] else "FAIL", f"앱 need_head {j0.get('need_head')} · 규제 {j0.get('regulated')} · 원문 {b['head']}")
            rec(no, "1순위 가입기간", "PASS" if j0.get("account_months") == b["acct"] else ("NOT_TESTABLE" if j0.get("account_months") is None else "FAIL"),
                f"앱 {j0.get('account_months')} · 원문 {b['acct']}")
        rw = next((v for k, v in j0.get("limits") or [] if k == "재당첨 제한"), None)
        have = 0 if rw == "없음" else int(rw[:-1]) if rw and rw.endswith("년") else None
        rec(no, "재당첨 제한", "PASS" if have == b["rewin"] else ("NOT_TESTABLE" if have is None else "FAIL"), f"앱 {rw} · 원문 {b['rewin']}년")
    out = {"tally": tally, "fails": [r for r in res if r["status"] == "FAIL"], "not_testable": [r for r in res if r["status"] == "NOT_TESTABLE"][:40]}
    (ROOT / "evidence/qa/spotcheck-result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in tally.items():
        print(k, v)
    for r in out["fails"]:
        print("FAIL", r["id"], r["field"], r["detail"])


if __name__ == "__main__":
    main()
