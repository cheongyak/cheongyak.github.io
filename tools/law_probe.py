"""법령 원문 받기 — 주택공급에 관한 규칙 (법제처 국가법령정보 공동활용 OPEN API).

판정·가이드에 쓰는 법령 기준표(별표 1 가점제 적용기준, 별표 2 청약 예치기준금액 등)를 법령 원문과 대조하려고
GitHub Actions 에서 법령 본문·별표를 받아 evidence/law/ 에 남긴다. 작업 환경(Claude)에서는 law.go.kr 에 접속할 수 없어 Actions 가 받는다.

인증키: GitHub Secrets LAW_OC (open.law.go.kr 에서 신청한 API인증키). 저장하는 파일·기록에는 인증키를 남기지 않는다.
실행: python -m tools.law_probe   (워크플로 law-probe.yml)
"""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "law"
LAW_NAME = "주택공급에 관한 규칙"
BASE = "https://www.law.go.kr/DRF"
WANT = (1, 2)          # 별표 1 가점제 적용기준, 별표 2 청약 예치기준금액
NOW = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")


def scrub(text: str, oc: str) -> str:
    return text.replace(oc, "***") if oc else text


def txt(el, *names) -> str:
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def main() -> int:
    oc = os.environ.get("LAW_OC", "").strip()
    OUT.mkdir(parents=True, exist_ok=True)
    log: list[str] = [f"받은 시각: {NOW}", f"법령: {LAW_NAME}"]
    summary: dict = {"at": NOW, "law": LAW_NAME, "ok": False}
    if not oc:
        log.append("LAW_OC 가 없어 받지 않음 (GitHub Secrets 에 LAW_OC 를 넣어야 함)")
        (OUT / "README.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 0
    http = httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "cheongyakpass-law-probe"})

    # 1) 법령 찾기 — 주소 형태(http/https, 법령명 띄어쓰기)에 따라 '필수 입력값 없음'이 나는 경우가 있어 차례로 시도하고 모두 기록한다
    tries = []
    r = None
    found = BASE
    for base in ("http://www.law.go.kr/DRF", "https://www.law.go.kr/DRF"):
        for q in (LAW_NAME, LAW_NAME.replace(" ", "")):
            rr = http.get(f"{base}/lawSearch.do", params={"OC": oc, "target": "law", "type": "XML", "query": q, "display": 20})
            hops = " → ".join(scrub(str(h.url), oc) for h in rr.history) + (" → " if rr.history else "") + scrub(str(rr.url), oc)
            tries.append(f"[검색 시도] {hops} · HTTP {rr.status_code} · " + re.sub(r"\s+", " ", scrub(rr.text, oc)[:160]))
            if rr.status_code == 200 and "<law" in rr.text:
                r = rr
                break
        if r is not None:
            found = base
            break
    log += tries
    if r is None:
        r = rr
    body = scrub(r.text, oc)
    (OUT / "search.xml").write_text(body, encoding="utf-8")
    log.append(f"[검색] HTTP {r.status_code} · {len(body)}자 · 사용 주소 {found}")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        log.append("[검색] XML 이 아님 — 응답 앞부분: " + re.sub(r"\s+", " ", body[:300]))
        (OUT / "README.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 1
    hit = None
    for law in root.iter("law"):
        if txt(law, "법령명한글").replace(" ", "") == LAW_NAME.replace(" ", ""):
            hit = law
            break
    if hit is None:
        log.append("[검색] 이름이 같은 법령을 찾지 못함 — search.xml 확인")
        (OUT / "README.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 1
    mst, lid = txt(hit, "법령일련번호"), txt(hit, "법령ID")
    summary.update({"mst": mst, "law_id": lid, "promulgated": txt(hit, "공포일자"), "effective": txt(hit, "시행일자"),
                    "promulgation_no": txt(hit, "공포번호"), "kind": txt(hit, "법령구분명"), "ministry": txt(hit, "소관부처명")})
    log.append(f"[검색] 법령일련번호 {mst} · 시행일자 {summary['effective']} · 공포일자 {summary['promulgated']} ({summary['kind']} 제{summary['promulgation_no']}호)")

    # 2) 본문 (별표 포함)
    r = http.get(f"{found}/lawService.do", params={"OC": oc, "target": "law", "type": "XML", "MST": mst})
    body = scrub(r.text, oc)
    (OUT / "rule.xml").write_text(body, encoding="utf-8")
    log.append(f"[본문] HTTP {r.status_code} · {len(body)}자")
    try:
        doc = ET.fromstring(r.content)
    except ET.ParseError:
        log.append("[본문] XML 이 아님 — 응답 앞부분: " + re.sub(r"\s+", " ", body[:300]))
        doc = None
    tables = []
    if doc is not None:
        for b in doc.iter("별표단위"):
            no, title = txt(b, "별표번호"), txt(b, "별표제목")
            content = txt(b, "별표내용")
            links = {k: txt(b, k) for k in ("별표서식파일링크", "별표서식PDF파일링크", "별표HWP파일명", "별표PDF파일명") if txt(b, k)}
            gaji = txt(b, "별표가지번호")
            tables.append({"no": no, "branch": gaji, "title": title, "chars": len(content), "links": links})
            try:
                n = int(no)
            except ValueError:
                n = None
            if n in WANT and not (gaji and gaji not in ("0", "00")):
                (OUT / f"byeolpyo_{n}.txt").write_text(f"{title}\n\n{content}\n", encoding="utf-8")
                for k, url in links.items():
                    if "PDF" in k and url.startswith("/"):
                        url = "https://www.law.go.kr" + url
                    if "PDF" in k and url.startswith("http"):
                        try:
                            f = http.get(url)
                            if f.status_code == 200 and f.content[:4] == b"%PDF":
                                (OUT / f"byeolpyo_{n}.pdf").write_bytes(f.content)
                                log.append(f"[별표 {n}] PDF {len(f.content)}바이트 저장")
                            else:
                                log.append(f"[별표 {n}] PDF 받기 실패 HTTP {f.status_code}")
                        except Exception as e:
                            log.append(f"[별표 {n}] PDF 받기 실패: {e}")
        for t in tables:
            log.append(f"[별표 목록] 별표 {t['no']}{('의' + t['branch']) if t['branch'] and t['branch'] not in ('0', '00') else ''} · {t['title']} · 본문 {t['chars']}자")
    summary["tables"] = tables
    summary["ok"] = any(t["no"].lstrip("0") in ("1", "2") and t["chars"] > 0 for t in tables)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "README.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
