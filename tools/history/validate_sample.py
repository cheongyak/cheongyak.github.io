"""2026 과거 공고 랜덤 검증 (기능: historical 실험 4단계). 서비스 데이터는 바꾸지 않고 evidence/history/ 에만 쓴다.

모집단 = docs/archive/2026.json 의 공고(주택형 묶음). 층화 랜덤(유형 일반분양/무순위 × 수도권/지방)으로 공고를 뽑는다.
같은 seed·같은 보관함 버전이면 같은 샘플이 나온다. 결과는 PASS / FAIL / UNCERTAIN / N/A(해당 없음) 로만 세고 비율을 지어내지 않는다.

검사 (사람이 고른 사례 없음):
  D1 일정 순서      공고일 ≤ 접수 시작 ≤ 접수 끝 ≤ 발표일                       (청약홈 값끼리)
  D2 세대수 합       주택형 일반+특공 세대 합 = 공고 총공급 세대(TOT_SUPLY_HSHLDCO)   (청약홈 값끼리, 일반분양만)
  D3 지역            시·도 / 시·군·구를 주소에서 읽었는가
  N1 공고문 받기     모집공고문 PDF 를 받아 글을 읽었는가                          (SOURCE_ERROR)
  N2 분양가 대조     청약홈 주택형 분양가가 공고문 원문 숫자로 나오는가(notice_facts.price_seen)
  N3 단지 규모       공고문 '공급규모'에서 총세대·동 수를 읽었는가(parse_complex)
  N4 정답 데이터     tests/golden/notices.json 에 있으면 추출값과 비교
실행: python -m tools.history.validate_sample [--seed N] [--size N] [--fresh]
"""
import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "archive" / "2026.json"
GOLD = ROOT / "tests" / "golden" / "notices.json"
OUT_DIR = ROOT / "evidence" / "history"
CAPITAL = {"서울", "경기", "인천"}


def groups(items: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for x in items:
        g.setdefault(x["notice_no"], []).append(x)
    return g


def stratified(g: dict, size: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    strata: dict[str, list[str]] = {}
    for no, rows in sorted(g.items()):
        r = rows[0]
        strata.setdefault(f"{r['category']}|{'수도권' if r.get('sido') in CAPITAL else '지방'}", []).append(no)
    total = sum(len(v) for v in strata.values())
    picked: list[str] = []
    for k in sorted(strata):
        ids = strata[k]
        n = max(1, round(size * len(ids) / total))
        picked += rng.sample(ids, min(n, len(ids)))
    rng.shuffle(picked)
    return sorted(picked[:size]) if len(picked) >= size else sorted(picked)


def check_data(rows: list[dict]) -> dict:
    r = rows[0]
    out = {}
    ds = [r.get("notice"), r.get("apply"), r.get("apply_end") or r.get("apply"), r.get("winner")]
    if any(d is None for d in ds):
        out["D1"] = ("UNCERTAIN", "MISSING_DATA", f"일정 빈 값 {ds}")
    else:
        out["D1"] = ("PASS", None, "") if ds == sorted(ds) else ("FAIL", "DATA_ERROR", f"일정 순서 {ds}")
    if r["category"] != "general":
        out["D2"] = ("N/A", None, "무순위·재공급은 총공급 세대 기준이 다름")
    elif r.get("total_households") in (None, 0):
        out["D2"] = ("UNCERTAIN", "MISSING_DATA", "총공급 세대 없음")
    else:
        s = sum((x.get("households") or 0) + ((x.get("special_units") or {}).get("total") or 0) for x in rows)
        if s == r["total_households"]:
            out["D2"] = ("PASS", None, "")
        elif "본청약" in (r.get("name") or "") and s < r["total_households"]:   # 2026000414 공고문: 총 663 = 사전청약 412 + 이번 공급 251 (+이주자 2)
            out["D2"] = ("UNCERTAIN", "EXPECTED_DIFFERENCE", f"본청약: 총공급 {r['total_households']} 에 사전청약 당첨자 몫 포함, 이번 공급 {s}")
        else:
            out["D2"] = ("FAIL", "DATA_ERROR", f"주택형 합 {s} ≠ 총공급 {r['total_households']}")
    out["D3"] = ("PASS", None, "") if r.get("sido") and r.get("district") else ("FAIL", "PARSING_ERROR", f"시도 {r.get('sido')} 시군구 {r.get('district')}")
    return out


def check_notice(no: str, rows: list[dict], gold: dict) -> dict:
    r = rows[0]
    out = {}
    if not r.get("url"):
        return {"N1": ("UNCERTAIN", "MISSING_DATA", "공고 페이지 주소 없음")}
    text, msg, pdf = notice_pdf.fetch_notice_text(r["url"])
    if not text:
        out["N1"] = ("FAIL", "SOURCE_ERROR", msg[:120])
        for k in ("N2", "N3"):
            out[k] = ("UNCERTAIN", "SOURCE_ERROR", "공고문을 못 받음")
        return out
    out["N1"] = ("PASS", None, "")
    prices = {x["id"].split("-", 1)[1].strip(): round((x.get("price") or 0) * 10000) for x in rows if x.get("price")}
    seen = notice_pdf.notice_facts(text, prices).get("price_seen", {})
    if not seen:
        out["N2"] = ("UNCERTAIN", "MISSING_DATA", "청약홈 분양가 없음")
    else:
        ok = sum(1 for v in seen.values() if v)
        out["N2"] = ("PASS", None, "") if ok == len(seen) else ("FAIL" if ok == 0 else "UNCERTAIN", "PARSING_ERROR", f"공고문에서 찾은 분양가 {ok}/{len(seen)}")
    c = notice_pdf.parse_complex(text)
    out["N3"] = ("PASS", None, f"{c['households']}세대·{c['buildings']}개동") if c else ("UNCERTAIN", "PARSING_ERROR", "공급규모 문장 못 읽음")
    if no in gold:
        want = gold[no].get("fields", {})
        got = notice_pdf.parse_notice(text)
        diffs = [k for k in ("need_head", "price_cap", "rewin_years", "residence") if k in want and k in got and want[k] != got[k]]
        if "complex" in want:
            gc = c and {"households": c["households"], "buildings": c["buildings"]}
            if want["complex"]["households"] is None:
                diffs += [] if c is None else ["complex"]
            elif gc != want["complex"]:
                diffs.append("complex")
        out["N4"] = ("PASS", None, "") if not diffs else ("FAIL", "PARSING_ERROR", f"정답과 다름: {diffs}")
    else:
        out["N4"] = ("N/A", None, "정답 데이터 없는 공고")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--size", type=int, default=120)
    ap.add_argument("--fresh", action="store_true", help="새 랜덤 seed (재현용으로 seed 를 기록)")
    a = ap.parse_args()
    today = date.today().isoformat()
    seed = random.SystemRandom().randrange(10**9) if a.fresh else (a.seed if a.seed is not None else int(today.replace("-", "")))
    arc = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    g = groups(arc["items"])
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    ids = stratified(g, a.size, seed)
    t0 = time.monotonic()
    res: dict[str, dict] = {no: check_data(g[no]) for no in ids}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for no, r in zip(ids, ex.map(lambda n: check_notice(n, g[n], gold), ids)):
            res[no].update(r)
    tally: dict[str, dict] = {}
    errs: dict[str, int] = {}
    for no, checks in res.items():
        for k, (st, cls, _) in checks.items():
            tally.setdefault(k, {}).setdefault(st, 0)
            tally[k][st] += 1
            if cls and st != "PASS":
                errs[cls] = errs.get(cls, 0) + 1
    meta = {"date": today, "seed": seed, "fresh": a.fresh, "dataset": f"archive/2026.json built {arc['meta']['built']} ({arc['meta']['notices']}공고·{arc['meta']['count']}주택형)",
            "population_notices": len(g), "sample_size": len(ids), "seconds": round(time.monotonic() - t0, 1)}
    rep = {"meta": meta, "tally": tally, "errors": dict(sorted(errs.items(), key=lambda x: -x[1])), "sample": ids,
           "results": {no: {k: list(v) for k, v in c.items()} | {"name": g[no][0]["name"].strip(), "category": g[no][0]["category"], "sido": g[no][0].get("sido")} for no, c in res.items()}}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"validation-{today}{'-fresh' if a.fresh else ''}.json"
    (OUT_DIR / name).write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    for k in sorted(tally):
        print(k, tally[k])
    print("errors", rep["errors"])


if __name__ == "__main__":
    main()
