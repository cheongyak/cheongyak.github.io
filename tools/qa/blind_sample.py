"""주간 블라인드 표본 (2026-10-02 사용자 '공고문을 제대로 파싱하는지 점검' 4단계).

매주 지금 공고에서 공급 종류별로 고르게 5개를 뽑아, 앱 값을 보지 않는 검토자가 원문(evidence/notices/<번호>.txt 또는 모집공고문 PDF)만 읽고 답을 적고,
그 답을 수집 값과 비교한다. 같은 공고는 다시 뽑지 않는다. 검토자가 적은 값은 확인 뒤 정답 데이터(tests/golden/notices.json)로 옮긴다.

  python -m tools.qa.blind_sample pick      → evidence/qa/blind/<YYYY-Www>.json (질문만, 앱 값 없음)
  python -m tools.qa.blind_sample compare   → 답이 채워진 주의 파일을 수집 값(docs/listings.json)과 비교 → evidence/qa/blind/report.json

질문(QUESTIONS)은 판정에 쓰는 공고문 값만. 답을 모르면 null, 공고문에 없으면 "없음"이라고 적는다.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "evidence" / "qa" / "blind"
QUESTIONS = {
    "need_head": "청약 신청자가 세대주여야 하나요? (true/false)",
    "price_cap": "분양가상한제 적용 주택인가요? (true/false)",
    "residence_duty": "거주의무 기간(년). 없으면 0, 공고문에 아예 없으면 \"없음\"",
    "rewin_years": "당첨 시 재당첨 제한 기간(년). 없으면 0",
    "account_months": "일반공급 1순위 청약통장 가입기간(개월)",
    "residence_area": "해당지역(우선공급) 이름 (예: 서울특별시, 과천시)",
    "residence_months": "해당지역 최소 거주기간(개월). 기간 조건이 없으면 0",
    "balance": "잔금일 또는 입주지정기간 종료일 (YYYY-MM-DD)",
    "special_total": "이 주택형 특별공급 세대수 합계",
}
GROUPS = [("민영 일반", lambda x: x.get("category") == "general" and x.get("house_dtl") == "민영"),
          ("공공 일반", lambda x: x.get("category") == "general" and x.get("house_dtl") == "국민" and "신혼희망타운" not in x.get("name", "")),
          ("신혼희망타운", lambda x: "신혼희망타운" in x.get("name", "")),
          ("무순위", lambda x: x.get("category") == "remainder" and "재공급" not in (x.get("kind") or "")),
          ("재공급", lambda x: x.get("category") == "remainder" and "재공급" in (x.get("kind") or ""))]


def listings() -> list[dict]:
    d = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    return [x for x in (d["items"] if isinstance(d, dict) else d) if not x.get("sample")]


def app_answer(x: dict) -> dict:
    r = x.get("residence") or {}
    su = x.get("special_units") or {}
    return {"need_head": x.get("need_head"), "price_cap": x.get("price_cap"),
            "residence_duty": "없음" if x.get("duty_silent") else x.get("residence_duty"), "rewin_years": next((int(v[:-1]) if v.endswith("년") else 0 for k, v in (x.get("limits") or []) if k == "재당첨 제한"), None),
            "account_months": x.get("account_months"), "residence_area": (r.get("area") or {}).get("name"), "residence_months": r.get("months"),
            "balance": x.get("balance"), "special_total": su.get("total")}


def pick(n: int = 5) -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    for f in DIR.glob("20*.json"):
        done |= {s["id"] for s in json.loads(f.read_text(encoding="utf-8"))["samples"]}
    week = date.today().isocalendar()
    rng = random.Random(f"{week[0]}-{week[1]}")
    rows = [x for x in listings() if x["id"] not in done and x["id"].split("-")[0] not in {d.split("-")[0] for d in done}]
    out = []
    for name, f in GROUPS:
        pool = [x for x in rows if f(x)]
        if pool and len(out) < n:
            out.append((name, rng.choice(pool)))
    rest = [x for x in rows if x["id"] not in {o[1]["id"] for o in out}]
    while len(out) < n and rest:
        out.append(("기타", rest.pop(rng.randrange(len(rest)))))
    path = DIR / f"{week[0]}-W{week[1]:02d}.json"
    path.write_text(json.dumps({"week": f"{week[0]}-W{week[1]:02d}", "made": date.today().isoformat(),
        "how": "앱 화면·docs/listings.json 을 보지 않고 원문만 읽고 answers 를 채운다. 원문 위치: source. 근거 문장은 quotes 에.",
        "questions": QUESTIONS,
        "samples": [{"group": g, "id": x["id"], "name": x["name"], "unit": x.get("unit"),
                     "source": next((str(p.relative_to(ROOT)) for p in (ROOT / "evidence" / "notices" / f"{x['id'].split('-')[0]}.txt",) if p.exists()), None) or x.get("notice_pdf") or x.get("url"),
                     "answers": {k: None for k in QUESTIONS}, "quotes": {}} for g, x in out]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[블라인드 표본] {path.relative_to(ROOT)} · {len(out)}개: " + ", ".join(f"{g} {x['name'][:12]}" for g, x in out))
    return path


def compare() -> int:
    by = {x["id"]: x for x in listings()}
    rows, mism, nans = [], 0, 0
    for f in sorted(DIR.glob("20*.json")):
        w = json.loads(f.read_text(encoding="utf-8"))
        for s in w["samples"]:
            ans = {k: v for k, v in s["answers"].items() if v is not None}
            if not ans:
                continue
            x = by.get(s["id"])
            if not x:
                rows.append({"week": w["week"], "id": s["id"], "note": "지금 목록에 없음(마감·보관)"})
                continue
            app = app_answer(x)
            for k, v in ans.items():
                nans += 1
                a = app.get(k)
                same = str(a).replace(" ", "") == str(v).replace(" ", "") or (a in (None,) and v == "없음")
                if k == "residence_area" and a and v:   # '경기도 평택시' ↔ '평택시' 같은 지역 (표기만 다름)
                    same = same or str(a).replace(" ", "").endswith(str(v).replace(" ", "")) or str(v).replace(" ", "").endswith(str(a).replace(" ", ""))
                if k == "special_total" and a is None and v == 0 and x.get("category") == "remainder":   # 무순위·재공급은 특공 자료가 없으면 None — 특공 없음과 같은 뜻
                    same = True
                if not same:
                    mism += 1
                    rows.append({"week": w["week"], "id": s["id"], "name": s["name"], "field": k, "reviewer": v, "app": a, "quote": s.get("quotes", {}).get(k)})
    rep = {"date": date.today().isoformat(), "answers": nans, "mismatches": mism, "rows": rows}
    (DIR / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[블라인드 표본] 답 {nans}개 비교 · 다름 {mism}개")
    for r in rows[:10]:
        print("  ", r)
    return 1 if mism else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pick"
    sys.exit(compare() if cmd == "compare" else (pick() and 0))
