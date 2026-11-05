"""사이트 외부 점검 — 구글(애드센스·검색)이 실제로 받는 응답 (2026-11-05 애드센스 'ads.txt 찾을 수 없음').

주소마다 Googlebot·Mediapartners-Google(애드센스 크롤러) 이름으로 요청해 리다이렉트 경로·상태 코드·내용 형식·본문을 남기고,
ads.txt 는 저장소 docs/ads.txt 와 같은지 본다. 도메인(apex·www) DNS·인증서 이름도 남긴다.
작업 환경에서는 이 사이트에 접속이 막혀 있어 Actions(근거 자료 모으기)에서 돈다.

사용: python -m tools.qa.site_check --json evidence/qa/site-check.json
"""
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOSTS = ["cheongyakpass.kr", "www.cheongyakpass.kr"]
URLS = ["https://cheongyakpass.kr/ads.txt", "https://www.cheongyakpass.kr/ads.txt", "http://cheongyakpass.kr/ads.txt", "http://www.cheongyakpass.kr/ads.txt",
        "https://cheongyakpass.kr/robots.txt", "https://cheongyakpass.kr/sitemap.xml", "https://cheongyakpass.kr/"]
UAS = {"Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "Mediapartners-Google": "Mediapartners-Google"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPEN = urllib.request.build_opener(NoRedirect)


def fetch(url: str, ua: str) -> dict:
    chain, cur = [], url
    for _ in range(6):
        req = urllib.request.Request(cur, headers={"User-Agent": ua})
        try:
            r = OPEN.open(req, timeout=20)
            code, hdr, body = r.status, r.headers, r.read(4000)
        except urllib.error.HTTPError as ex:
            code, hdr, body = ex.code, ex.headers, ex.read(4000) if ex.fp else b""
        except Exception as ex:
            chain.append({"url": cur, "error": f"{type(ex).__name__}: {ex}"[:200]})
            return {"chain": chain, "ok": False}
        loc = hdr.get("Location")
        chain.append({"url": cur, "status": code, "type": hdr.get("Content-Type"), "location": loc})
        if code in (301, 302, 303, 307, 308) and loc:
            cur = urllib.parse.urljoin(cur, loc)
            continue
        return {"chain": chain, "ok": code == 200, "final": cur, "status": code, "type": hdr.get("Content-Type"),
                "body": body.decode("utf-8", "replace")[:300] if cur.endswith((".txt", ".xml")) else None}
    return {"chain": chain, "ok": False, "error": "리다이렉트 6번 넘음"}


def dns(host: str) -> dict:
    out = {}
    try:
        out["addrs"] = sorted({a[4][0] for a in socket.getaddrinfo(host, 443)})
    except Exception as ex:
        out["error"] = str(ex)[:200]
    for t in ("CNAME", "A", "AAAA"):
        try:
            out[t] = subprocess.run(["dig", "+short", t, host], capture_output=True, text=True, timeout=15).stdout.split()
        except Exception:
            pass
    return out


def cert(host: str) -> dict:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=15) as s, ctx.wrap_socket(s, server_hostname=host) as t:
            c = t.getpeercert()
        return {"ok": True, "names": [v for k, v in c.get("subjectAltName", []) if k == "DNS"], "until": c.get("notAfter")}
    except Exception as ex:
        return {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:200]}


def run() -> dict:
    want = (ROOT / "docs" / "ads.txt").read_text(encoding="utf-8").strip()
    res = {"at": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "repo_ads_txt": want,
           "dns": {h: dns(h) for h in HOSTS}, "cert": {h: cert(h) for h in HOSTS}, "fetch": {}}
    for u in URLS:
        res["fetch"][u] = {name: fetch(u, ua) for name, ua in UAS.items()}
    a = res["fetch"]["https://cheongyakpass.kr/ads.txt"]
    res["ads_txt_ok"] = all(x.get("ok") and (x.get("body") or "").strip() == want and "text/plain" in (x.get("type") or "") for x in a.values())
    res["www_ads_txt_ok"] = all(x.get("ok") and (x.get("body") or "").strip() == want for x in res["fetch"]["https://www.cheongyakpass.kr/ads.txt"].values())
    return res


def main() -> None:
    r = run()
    if "--json" in sys.argv:
        p = ROOT / sys.argv[sys.argv.index("--json") + 1]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    a = r["fetch"]["https://cheongyakpass.kr/ads.txt"]["Mediapartners-Google"]
    print(f"[사이트 점검] ads.txt {'정상' if r['ads_txt_ok'] else '문제'} (애드센스 크롤러: " + " → ".join(f"{c.get('status', c.get('error'))}" for c in a["chain"])
          + f", 형식 {a.get('type')}) · www ads.txt {'정상' if r['www_ads_txt_ok'] else '문제'} · 인증서 " + ", ".join(f"{h} {'정상' if c['ok'] else '문제'}" for h, c in r["cert"].items()))


if __name__ == "__main__":
    main()
