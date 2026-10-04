"""수도권 지하철·전철 노선별 역 좌표 (청약봇 V2 '신분당선 라인' 같은 노선 조건용, 2026-10-04 사용자 샘플 4).
출처: OpenStreetMap(ODbL) Overpass API — 수집의 주변 역(app/geo.py)과 같은 출처. 역 좌표를 기억으로 적지 않는다.
결과: chat/v2/data/lines.json {"src","at","lines":{"신분당선":[{"name":"강남","lat":..,"lng":..}, ...]}}, 근거 요약 evidence/chat-v2/lines-probe.txt
실행(Actions 근거 자료 모으기): python -m tools.subway_lines"""
import json
import re
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "chat" / "v2" / "data" / "lines.json"
EVI = ROOT / "evidence" / "chat-v2" / "lines-probe.txt"
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
BBOX = "36.80,126.30,38.10,127.80"   # 수도권 (평택·안성 ~ 동두천·포천, 인천 ~ 양평)
LINE_RE = re.compile(r"(GTX-?[A-C]|신분당선|수인분당선|수인선|분당선|경의중앙선|경의선|중앙선|경춘선|공항철도|서해선|경강선|신림선|우이신설선|김포골드라인|"
                     r"인천\s?[12]호선|의정부경전철|용인경전철|에버라인|신안산선|동북선|[1-9]호선)")
QUERY = f"""[out:json][timeout:180];
relation["route"~"^(subway|light_rail|train|monorail)$"]({BBOX})->.r;
.r out tags;
node(r.r)["name"]["railway"~"^(station|stop|halt)$"]->.s1;
node(r.r)["name"]["public_transport"~"^(stop_position|station)$"]->.s2;
(.s1; .s2;);
out body qt;
.r out body qt;"""


def norm_line(tags: dict) -> str | None:
    for k in ("name", "ref", "name:ko", "description"):
        m = LINE_RE.search(tags.get(k) or "")
        if m:
            x = re.sub(r"\s", "", m.group(1))
            return {"수인선": "수인분당선", "분당선": "수인분당선", "경의선": "경의중앙선", "중앙선": "경의중앙선", "용인경전철": "에버라인", "GTXA": "GTX-A"}.get(x, x.replace("GTXA", "GTX-A"))
    return None


def station_name(n: str) -> str:
    n = re.sub(r"\(.*?\)", "", n).strip()
    n = re.sub(r"\s*(\d+번\s*)?(승강장|출구).*$", "", n)
    return re.sub(r"역$", "", n).strip()


def main() -> None:
    data = None
    for u in URLS:
        try:
            r = httpx.post(u, data={"data": QUERY}, timeout=240, headers={"User-Agent": "cheongyakpass-bot (+https://cheongyakpass.kr)"})
            if r.status_code == 200:
                data = r.json()
                break
            print("Overpass", u, r.status_code)
        except Exception as e:
            print("Overpass", u, e.__class__.__name__)
        time.sleep(5)
    if not data:
        print("[노선] Overpass 응답 없음 — 건너뜀")
        return
    nodes = {e["id"]: e for e in data["elements"] if e["type"] == "node"}
    lines: dict[str, dict[str, list]] = {}
    for rel in (e for e in data["elements"] if e["type"] == "relation" and e.get("members")):
        ln = norm_line(rel.get("tags", {}))
        if not ln:
            continue
        for m in rel["members"]:
            n = nodes.get(m["ref"]) if m["type"] == "node" else None
            if not n or not n.get("tags", {}).get("name"):
                continue
            nm = station_name(n["tags"].get("name:ko") or n["tags"]["name"])
            if not nm or re.search(r"[A-Za-z]{4,}", nm):
                continue
            lines.setdefault(ln, {}).setdefault(nm, []).append((n["lat"], n["lon"]))
    out = {}
    for ln, st in sorted(lines.items()):
        rows = []
        for nm, pts in st.items():
            lat = sum(p[0] for p in pts) / len(pts)
            lng = sum(p[1] for p in pts) / len(pts)
            rows.append({"name": nm, "lat": round(lat, 6), "lng": round(lng, 6)})
        out[ln] = sorted(rows, key=lambda x: (x["lat"], x["lng"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"src": "OpenStreetMap 기여자(ODbL) · Overpass API", "at": time.strftime("%Y-%m-%d"), "lines": out}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    EVI.parent.mkdir(parents=True, exist_ok=True)
    EVI.write_text("\n".join(f"{ln} {len(v)}역: " + ", ".join(x["name"] for x in v) for ln, v in out.items()) + "\n", encoding="utf-8")
    print(f"[노선] {len(out)}개 노선 · " + " · ".join(f"{ln} {len(v)}" for ln, v in out.items()))


if __name__ == "__main__":
    main()
