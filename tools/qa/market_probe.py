"""시세를 못 구한 공고 점검 (2026-10-07 사용자 제보 'LTV 70%인데 대출 0원' 뒤, 시세 없는 공고 줄이기 A).
접수 마감 전 분양 공고 중 기준 시세(mkt_base)가 빈 주택형마다 실제 국토부 실거래가를 다시 받아,
지금 규칙(같은 단지·같은 평형 / 같은 구 준공 10년 이내 같은 평형 ±3㎡, 최근 6개월)에서 왜 0건인지와
다른 후보(역지오코딩 코드, 12개월, 평형 범위 넓히기, 준공 연도 정보 없는 거래)에서 몇 건이 나오는지 센다.
코드를 추측해 넣지 않기 위한 근거 자료. 결과: evidence/qa/market-probe.txt. 실행: python -m tools.qa.market_probe"""
import json
import os
import statistics
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

from app import geo, lawd, region as RG, rules as R
from app.market import same_complex
from app.sources.rtms import RtmsClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "market-probe.txt"


def months(n: int) -> list[str]:
    t = date.today()
    y, m = t.year, t.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def med(xs):
    return round(statistics.median(xs) / 10000, 2) if xs else None


def main() -> None:
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    today = date.today().isoformat()
    miss = [x for x in rows if not x.get("sample") and not x.get("rental") and (x.get("apply_end") or "") >= today and x.get("mkt_base") is None]
    key = (os.environ.get("NCP_MAPS_CLIENT_ID") or "", os.environ.get("NCP_MAPS_CLIENT_SECRET") or "")
    http = httpx.Client(timeout=httpx.Timeout(20, connect=10))
    rt = RtmsClient()
    cache = lawd.load()
    out = [f"# 시세 없는 공고 점검 {today} · 주택형 {len(miss)}개 (지금 규칙: 최근 {R.MARKET_MONTHS}개월 · ±{R.AREA_BAND}㎡ · 준공 {R.NEW_BUILD_YEARS}년 이내)"]
    by_addr: dict = {}
    for x in miss:
        by_addr.setdefault(x["address"], []).append(x)
    got: dict = {}
    for addr, xs in by_addr.items():
        out.append(f"\n## {xs[0]['name']} · {addr}")
        codes = {}
        c0 = lawd.lawd_for(addr, cache)
        if c0:
            codes[c0] = "표/기록"
        g, msg = geo.geocode(RG.main_address(addr), RG.sido_of(addr), http, key)
        if g:
            info, m2 = lawd.reverse(g["lat"], g["lng"], http, key)
            out.append(f"  역지오코딩: {info if info else m2}")
            if info and info["code"] not in codes:
                codes[info["code"]] = "역지오코딩"
        else:
            out.append(f"  지오코딩 실패 ({msg})")
        umd = next((p for p in RG.main_address(addr).split() if p.endswith(("읍", "면", "동", "리"))), None)
        out.append(f"  확인할 코드 {codes} · 읍면동 '{umd}'")
        for code, why in codes.items():
            data = {}
            for kind in ("trade", "presale", "rent"):
                rs = []
                for ym in months(12):
                    k = (kind, code, ym)
                    if k not in got:
                        try:
                            got[k] = rt.fetch(kind, code, ym)
                        except Exception as e:
                            got[k] = []
                            out.append(f"  {code} {kind} {ym} 실패 {e.__class__.__name__}")
                    rs += [dict(r, _ym=ym) for r in got[k]]
                data[kind] = rs
            recent = set(months(R.MARKET_MONTHS))
            yr = date.today().year
            out.append(f"  [{code} {why}] 12개월 매매 {len(data['trade'])} · 분양권 {len(data['presale'])} · 전월세 {len(data['rent'])}"
                       f" · 매매 중 '{umd}' {sum(1 for r in data['trade'] if umd and r.get('umd') == umd)}")
            nb = [r for r in data["trade"] if r.get("build_year") and r["build_year"] >= yr - R.NEW_BUILD_YEARS and r.get("deal_type") != "직거래"]
            areas = Counter(int(round(r["area"] or 0)) for r in nb)
            out.append(f"    준공 {R.NEW_BUILD_YEARS}년 이내 매매(직거래 뺌) {len(nb)}건 · 많은 면적 {areas.most_common(8)}")
            for x in xs:
                a = x["area"]
                def cnt(pool, band, mon):
                    return [r for r in pool if r.get("amount") and r.get("area") and abs(r["area"] - a) <= band and r["_ym"] in mon]
                own = [r for r in data["trade"] + data["presale"] if same_complex(r.get("apt", ""), x["name"]) and r.get("deal_type") != "직거래"]
                m6, m12 = recent, set(months(12))
                line = [f"    {x['unit']}({a}㎡ 분양가 {x['price']}억):",
                        f"같은 단지 {len(own)}(평형 맞음 {len(cnt(own, R.AREA_BAND, m12))})",
                        f"신축 ±3·6개월 {len(cnt(nb, 3, m6))}", f"±3·12개월 {len(cnt(nb, 3, m12))}",
                        f"±5·12개월 {len(cnt(nb, 5, m12))}", f"±10·12개월 {len(cnt(nb, 10, m12))}"]
                c = cnt(nb, 10, m12)
                if c:
                    ppa = [r["amount"] / r["area"] for r in c]
                    line.append(f"㎡당 중앙값 {round(statistics.median(ppa))}만 → ×{a}㎡ = {round(statistics.median(ppa) * a / 10000, 2)}억")
                    line.append("예 " + "; ".join(f"{r.get('apt')} {r.get('area')}㎡ {round(r['amount']/10000,2)}억 {r.get('build_year')}준공 {r.get('date')}" for r in sorted(c, key=lambda r: r.get('date', ''), reverse=True)[:4]))
                rents = [r for r in data["rent"] if r.get("deposit") and not r.get("monthly") and r.get("area") and abs(r["area"] - a) <= 10 and r.get("build_year") and r["build_year"] >= yr - R.NEW_BUILD_YEARS]
                line.append(f"전세(±10·신축·12개월) {len(rents)}건 중앙값 {med([r['deposit'] for r in rents])}억")
                out.append(" · ".join(line))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
