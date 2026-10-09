"""블라인드 판독(공고문 원문만 본 검토자 JSON) ↔ 화면 데이터(docs/listings.json) 대조 (2026-10-09 공고문 해석 정확도 점검).
사용: python -m tools.qa.blind.compare_live <블라인드 JSON 폴더> [--json 결과파일]
항목마다 같음/다름/앱 모름/원문 없음 으로 나누고, 다름은 사람이 원문으로 가린다(이 도구는 판정하지 않음)."""
from __future__ import annotations
import json, sys, re, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _v(f, k):
    x = (f.get(k) or {})
    return x.get("value"), x.get("status"), x.get("note") or "", x.get("quote") or ""


def _num(x):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, (int, float)):
        return x
    m = re.search(r"\d+", str(x))
    return int(m.group()) if m else x


def app_rewin(L):
    v = next((l[1] for l in L.get("limits", []) if l[0] == "재당첨 제한"), None)
    return 0 if v == "없음" else int(v[:-1]) if v and v.endswith("년") else v


def rows(blind_dir: Path):
    data = json.loads((ROOT / "docs/listings.json").read_text(encoding="utf-8"))
    data = data.get("listings", data) if isinstance(data, dict) else data
    by = collections.OrderedDict()
    for x in data:
        by.setdefault(x["id"].split("-")[0], []).append(x)
    out = []
    for p in sorted(blind_dir.glob("*.json")):
        b = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(b, dict) or "fields" not in b:   # 결과 파일(compare-*.json) 건너뜀
            continue
        nid, f = b["id"], b["fields"]
        Ls = by.get(nid)
        if not Ls:
            continue
        L = Ls[0]
        fn = set(L.get("from_notice") or [])
        def add(key, app, src, blind, st, note, quote):
            if st in ("not_stated", None) and blind in (None, "", []):
                res = "원문 없음" if app is None else "원문 없음·앱 값 있음"
            elif app is None:
                res = "앱 모름"
            else:
                res = "같음" if app == blind else "다름"
            out.append(dict(id=nid, name=L["name"], key=key, app=app, app_src=src, blind=blind, status=st, note=note, quote=quote[:150], result=res))
        v, st, n, q = _v(f, "need_head")
        add("need_head", L.get("need_head"), "공고문" if "세대주 요건" in fn else "추정(규제지역)", v if isinstance(v, bool) else v, st, n, q)
        v, st, n, q = _v(f, "price_cap")
        add("price_cap", L.get("price_cap"), "공고문" if "분양가상한제" in fn else "청약홈", v, st, n, q)
        v, st, n, q = _v(f, "residence_duty")
        add("residence_duty", L.get("residence_duty"), "공고문" if "실거주 의무" in fn else "추정", _num(v), st, n, q)
        v, st, n, q = _v(f, "rewin_years")
        add("rewin_years", app_rewin(L), "공고문" if "재당첨 제한" in fn else "추정", _num(v), st, n, q)
        v, st, n, q = _v(f, "account_months")
        add("account_months", L.get("account_months"), "공고문" if "1순위 가입기간" in fn else "추정", _num(v), st, n, q)
        v, st, n, q = _v(f, "deposit_count")
        add("deposit_count", L.get("deposit_count"), "공고문" if "납입 인정 횟수" in fn else "-", _num(v), st, n, q)
        v, st, n, q = _v(f, "resale")
        bm = v.get("months") if isinstance(v, dict) else v
        ar = L.get("resale") or {}
        am = None if not ar else ("이미 지남" if ar.get("passed") else "없음" if ar.get("none") else ar.get("months"))
        add("resale_months", am, "공고문" if ar else "-", bm, st, n, q)
        v, st, n, q = _v(f, "residence")
        r = L.get("residence") or {}
        if isinstance(v, dict):
            add("residence.months", r.get("months"), "공고문" if r else "-", _num(v.get("months")), st, n, q)
            add("residence.since", r.get("since"), "공고문" if r else "-", v.get("since"), st, n, q)
        v, st, n, q = _v(f, "pay_ratio")
        pr = L.get("pay_ratio")
        if isinstance(v, dict) and v.get("contract_pct") is not None:
            bv = (_num(v.get("contract_pct")), _num(v.get("mid_pct")) or 0, _num(v.get("balance_pct")))
            av = None if not pr else (round(pr["contract"] * 100), round(pr["mid"] * 100), round(pr["balance"] * 100))
            add("pay_ratio", av, "공고문" if pr else "-", bv, st, n, q)
        v, st, n, q = _v(f, "score_ratio")
        sr = L.get("score_ratio")
        if isinstance(v, list) and v:
            bv = sorted((_num(x.get("upto_m2")) or 999, _num(x.get("score_pct")) or 0) for x in v if isinstance(x, dict))
            av = None if not sr or sr.get("unknown") else sorted((x.get("upto") or 999, x.get("score")) for x in sr.get("rows", []))
            add("score_ratio", av, "공고문" if sr else "-", bv, st, n, q)
    return out


if __name__ == "__main__":
    rs = rows(Path(sys.argv[1]))
    c = collections.Counter((r["key"], r["result"]) for r in rs)
    keys = sorted({r["key"] for r in rs})
    print(f"{'항목':18}" + "".join(f"{k:>10}" for k in ["같음", "다름", "앱 모름", "원문 없음", "원문 없음·앱 값 있음"]))
    for k in keys:
        print(f"{k:18}" + "".join(f"{c[(k, t)]:>10}" for t in ["같음", "다름", "앱 모름", "원문 없음", "원문 없음·앱 값 있음"]))
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(rs, ensure_ascii=False, indent=1), encoding="utf-8")
