"""시군구 코드(실거래가 LAWD_CD) 못 찾은 공고 점검 (2026-10-03 향남역 그로브 스위첸 '화성특례시 만세구').
지금 공고 중 시군구 코드를 못 찾은 주소마다:
  ① 네이버 지오코딩을 주소 여러 형태(원문·'특례시'→'시'·구 뺀 것)로 해 보고 ② 찾은 좌표를 역지오코딩해 법정동 코드·지역 이름을 받고
  ③ 국토부 실거래가(매매·분양권)를 후보 코드로 최근 달마다 조회해 그 읍·면·동 거래가 실제로 나오는지 센다.
결과: evidence/qa/lawd-probe.txt. 코드를 추측해 넣지 않기 위한 근거 자료. 실행: python -m tools.qa.lawd_probe [주소 ...]"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx

from app import geo, lawd, region as RG
from app.sources.rtms import RtmsClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "lawd-probe.txt"


def targets() -> list[str]:
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    cache = lawd.load()
    seen, out = set(), []
    for x in rows:
        a = x.get("address") or ""
        if x.get("sample") or a in seen:
            continue
        seen.add(a)
        if not lawd.lawd_for(a, cache):
            out.append(a)
    return out


def variants(a: str) -> list[str]:
    m = RG.main_address(a)
    v = [m, m.replace("특례시", "시")]
    parts = v[1].split()
    if len(parts) > 3 and parts[1].endswith("시") and parts[2].endswith("구"):
        v.append(" ".join(parts[:2] + parts[3:]))   # 구 빼기 (구가 생기기 전 이름)
    return list(dict.fromkeys(v))


def months(n: int = 9) -> list[str]:
    t = date.today()
    y, m = t.year, t.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def main() -> None:
    key = (os.environ.get("NCP_MAPS_CLIENT_ID") or "", os.environ.get("NCP_MAPS_CLIENT_SECRET") or "")
    http = httpx.Client(timeout=httpx.Timeout(20, connect=10))
    rt = RtmsClient()
    addrs = sys.argv[1:] or targets()
    out = [f"# 시군구 코드 점검 {date.today()} · 대상 {len(addrs)}곳"]
    for a in addrs:
        out.append(f"\n## {a}")
        codes = set()
        umd = None
        for q in variants(a):
            g, msg = geo.geocode(q, RG.sido_of(a), http, key)
            out.append(f"  지오코딩 '{q}': {'좌표 ' + str((g['lat'], g['lng'])) + ' · ' + g.get('matched', '') if g else '없음'} ({msg})")
            if g:
                info, m2 = lawd.reverse(g["lat"], g["lng"], http, key)
                out.append(f"    역지오코딩: {info if info else m2}")
                if info:
                    codes.add(info["code"])
                    umd = umd or info["names"].split()[-1]
        for name in ("화성시",):
            if name in a.replace("특례시", "시"):
                codes.add("41590")   # 표(app/rules.py)에 있는 구 화성시 코드도 함께 확인
        umd = umd or next((p for p in RG.main_address(a).split() if p.endswith(("읍", "면", "동"))), None)
        out.append(f"  확인할 코드 {sorted(codes)} · 읍면동 '{umd}'")
        for code in sorted(codes):
            for kind in ("trade", "presale"):
                line = []
                for ym in months():
                    try:
                        rows = rt.fetch(kind, code, ym)
                    except Exception as e:
                        line.append(f"{ym} 실패 {e.__class__.__name__}")
                        continue
                    hit = [r for r in rows if umd and umd in json.dumps(r, ensure_ascii=False)]
                    sample = (hit[0] if hit else (rows[0] if rows else {}))
                    line.append(f"{ym} 전체 {len(rows)} · {umd} {len(hit)}")
                    if hit and len(line) == 1 or (hit and not any('예:' in s for s in line)):
                        line.append("예: " + json.dumps({k: sample.get(k) for k in list(sample)[:12]}, ensure_ascii=False)[:300])
                out.append(f"  {code} {kind}: " + " | ".join(line))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
