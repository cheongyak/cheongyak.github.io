"""주간 블라인드 표본 (2026-10-02 사용자 '공고문을 제대로 파싱하는지 점검' 4단계).

매주 지금 공고에서 공급 종류별로 고르게 5개를 뽑아, 앱 값을 보지 않는 검토자가 원문(evidence/notices/<번호>.txt 또는 모집공고문 PDF)만 읽고 답을 적고,
그 답을 수집 값과 비교한다. 같은 공고는 다시 뽑지 않는다. 검토자가 적은 값은 확인 뒤 정답 데이터(tests/golden/notices.json)로 옮긴다.

  python -m tools.qa.blind_sample pick      → evidence/qa/blind/<YYYY-Www>.json (질문만, 앱 값 없음)
  python -m tools.qa.blind_sample compare   → 답이 채워진 주의 파일을 수집 값(docs/listings.json)과 비교 → evidence/qa/blind/report.json

질문(QUESTIONS)은 판정에 쓰는 공고문 값만. 답을 모르면 null, 공고문에 없으면 "없음"이라고 적는다.
LH 임대(기능 lh_rental, 2026-10-05 추가): 같은 파일 lh_samples 에 임대 공고 2개(유형이 다르게)를 뽑아 LH_QUESTIONS 를 묻고, docs/lh-rental.json 의 terms·rents 와 비교한다.
원문: evidence/lh/<공고번호>.txt 또는 모집공고문 PDF.
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
LH_QUESTIONS = {
    "local": "신청자격에 거주 지역 제한(예: '모집공고일 현재 군산시에 거주하는')이 있으면 그 시·군·시 이름, 없으면 \"없음\"",
    "homeless_relaxed": "주택건설지역·연접지역 밖 주택 등 무주택 요건 완화가 있나요? (true/false)",
    "groups": "계층별 기준 {계층: {\"income_3\": 3인 이상 소득 %(미적용이면 \"미적용\"), \"asset\": 총자산 한도 만원, \"car\": 자동차 한도 만원(소유 불가 0)}} — 계층 이름은 일반·청년·대학생·신혼부부·한부모·고령자·주거급여수급자·장기종사자",
    "rent_first": "임대조건 표 첫 줄 [보증금 원, 월 임대료 원]",
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


def lh_notices() -> list[dict]:
    f = ROOT / "docs" / "lh-rental.json"
    return json.loads(f.read_text(encoding="utf-8")).get("notices", []) if f.exists() else []


LH_KEY = {"일반": "일반", "청년": "청년", "대학생": "대학생", "신혼부부": "신혼부부·한부모", "한부모": "신혼부부·한부모", "신혼부부·한부모": "신혼부부·한부모", "고령자": "고령자",
          "주거급여수급자": "주거급여수급자", "장기종사자": "장기종사자"}


def lh_app_answer(N: dict) -> dict:
    T = N.get("terms") or {}
    loc = T.get("local")
    g = {}
    for x in T.get("groups") or []:
        ip = x.get("income_pct")
        g[x["key"]] = {"income_3": "미적용" if ip == "excluded" else (ip or {}).get("3+"), "asset": "미적용" if x.get("asset_manwon") == "excluded" else x.get("asset_manwon"),
                       "car": "미적용" if x.get("car_manwon") == "excluded" else x.get("car_manwon")}
    r = (N.get("rents") or [None])[0]
    return {"local": loc["name"] if loc else "없음", "homeless_relaxed": T.get("homeless_relaxed"), "groups": g, "rent_first": [r["deposit"], r["rent"]] if r else None}


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
    lh_done = set()
    for f in DIR.glob("20*.json"):
        lh_done |= {s["id"] for s in json.loads(f.read_text(encoding="utf-8")).get("lh_samples", [])}
    lh_out, seen = [], set()
    for N in sorted([N for N in lh_notices() if N.get("terms") and N["id"] not in lh_done], key=lambda N: rng.random()):   # 유형이 겹치지 않게 2개
        if N.get("type") not in seen and len(lh_out) < 2:
            seen.add(N.get("type")); lh_out.append(N)
    path = DIR / f"{week[0]}-W{week[1]:02d}.json"
    path.write_text(json.dumps({"week": f"{week[0]}-W{week[1]:02d}", "made": date.today().isoformat(),
        "how": "앱 화면·docs/listings.json 을 보지 않고 원문만 읽고 answers 를 채운다. 원문 위치: source. 근거 문장은 quotes 에.",
        "questions": QUESTIONS,
        "samples": [{"group": g, "id": x["id"], "name": x["name"], "unit": x.get("unit"),
                     "source": next((str(p.relative_to(ROOT)) for p in (ROOT / "evidence" / "notices" / f"{x['id'].split('-')[0]}.txt",) if p.exists()), None) or x.get("notice_pdf") or x.get("url"),
                     "answers": {k: None for k in QUESTIONS}, "quotes": {}} for g, x in out],
        "lh_questions": LH_QUESTIONS,
        "lh_samples": [{"group": "LH " + (N.get("type") or ""), "id": N["id"], "name": N["name"],
                        "source": next((str(p.relative_to(ROOT)) for p in (ROOT / "evidence" / "lh" / f"{N['id']}.txt",) if p.exists()), None) or N.get("notice_pdf"),
                        "answers": {k: None for k in LH_QUESTIONS}, "quotes": {}} for N in lh_out]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[블라인드 표본] {path.relative_to(ROOT)} · {len(out)}개: " + ", ".join(f"{g} {x['name'][:12]}" for g, x in out) + f" · LH {len(lh_out)}개: " + ", ".join(N["name"][:14] for N in lh_out))
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
                if k == "need_head" and v is True and a is False and x.get("regulated") and x.get("category") == "general":   # 신청 대상은 세대구성원, 규제지역 1순위 세대주는 따로 판정(regulated_rules) — 2026-W41 광명
                    same = True
                if k == "account_months" and a is None and v == 0 and x.get("need_account") is False:   # 청약통장 필요 없음(need_account false) = 0개월 — 2026-W41 무순위·재공급
                    same = True
                if k == "special_total" and a is None and v == 0 and x.get("category") == "remainder":   # 무순위·재공급은 특공 자료가 없으면 None — 특공 없음과 같은 뜻
                    same = True
                if not same:
                    mism += 1
                    rows.append({"week": w["week"], "id": s["id"], "name": s["name"], "field": k, "reviewer": v, "app": a, "quote": s.get("quotes", {}).get(k)})
        lhby = {N["id"]: N for N in lh_notices()}
        for s in w.get("lh_samples", []):
            ans = {k: v for k, v in s["answers"].items() if v is not None}
            if not ans:
                continue
            N = lhby.get(s["id"])
            if not N:
                rows.append({"week": w["week"], "id": s["id"], "note": "LH 목록에 없음(마감)"})
                continue
            app = lh_app_answer(N)
            pairs = []
            for k, v in ans.items():
                if k == "groups":   # 계층마다 칸마다 비교. 앱이 못 읽은 값(None)은 '공고문 확인'으로 보이므로 다름이 아니라 미확인으로 센다
                    for gk, gv in v.items():
                        ag = app["groups"].get(LH_KEY.get(gk, gk)) or {}
                        pairs += [(f"groups.{gk}.{f}", gv.get(f), ag.get(f)) for f in ("income_3", "asset", "car") if gv.get(f) is not None and ag.get(f) is not None]
                else:
                    pairs.append((k, v, app.get(k)))
            for k, v, a in pairs:
                nans += 1
                same = str(a).replace(" ", "") == str(v).replace(" ", "")
                if k == "local" and a and v:
                    same = same or str(a).replace(" ", "").rstrip("시군") == str(v).replace(" ", "").rstrip("시군")
                if not same:
                    mism += 1
                    rows.append({"week": w["week"], "id": s["id"], "name": s["name"], "field": "LH " + k, "reviewer": v, "app": a, "quote": s.get("quotes", {}).get(k.split(".")[0])})
    rep = {"date": date.today().isoformat(), "answers": nans, "mismatches": mism, "rows": rows}
    (DIR / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[블라인드 표본] 답 {nans}개 비교 · 다름 {mism}개")
    for r in rows[:10]:
        print("  ", r)
    return 1 if mism else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pick"
    sys.exit(compare() if cmd == "compare" else (pick() and 0))
