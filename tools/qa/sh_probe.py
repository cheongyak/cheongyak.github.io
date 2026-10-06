"""SH(서울주택도시개발공사) 임대 공고 원천 점검 (2026-10-06 사용자 'SH 공고 추가할 수 있는지' — 조사 단계, 화면·판정에는 쓰지 않음).
공공데이터 API 가 없어(공급계획 파일만 있음) SH 인터넷청약시스템 '공고 및 공지 > 주택임대' 게시판을 GitHub Actions 서버에서 받을 수 있는지 본다:
 - 목록  https://www.i-sh.co.kr/app/lay2/program/S48T1581C563/www/brd/m_247/list.do?multi_itm_seq=2 (모바일 주소) · /main/ 주소
 - 상세  같은 경로 view.do?multi_itm_seq=2&seq=<글번호> — 첨부파일 이름·주소
 - 첨부  공고문 PDF 를 한 개 받아 pypdf 로 글자를 뽑을 수 있는지
결과(받은 HTML 일부·뽑은 목록·첨부·PDF 글 앞부분)를 evidence/qa/sh/ 와 evidence/qa/sh-probe.txt 에 남긴다.
실행: python -m tools.qa.sh_probe (Actions 'SH 임대 원천 점검')"""
import html
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "sh-probe.txt"
RAW = ROOT / "evidence" / "qa" / "sh"
NOW = datetime.now(timezone(timedelta(hours=9)))
BASE = "https://www.i-sh.co.kr"
LISTS = [
    BASE + "/app/lay2/program/S48T1581C563/www/brd/m_247/list.do?multi_itm_seq=2",
    BASE + "/main/lay2/program/S1T294C297/www/brd/m_247/list.do?multi_itm_seq=2",
]
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36 cheongyakpass-probe",
      "Accept-Language": "ko-KR,ko;q=0.9"}
strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def rows_from(page: str, url: str) -> list[dict]:
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]*view\.do[^"]*seq=(\d+)[^"]*)"[^>]*>(.*?)</a>', page, re.S):
        href, seq, txt = m.group(1), m.group(2), strip(m.group(3))
        if seq in seen or not txt:
            continue
        seen.add(seq)
        tail = page[m.end(): m.end() + 600]
        d = re.search(r"(20\d\d[-.]\d\d[-.]\d\d)", tail)
        out.append({"seq": seq, "title": txt[:120], "date": d.group(1) if d else None, "url": urljoin(url, html.unescape(href))})
    if not out:   # 자바스크립트로 여는 목록(onclick="fn_view('290219')")
        # SH 게시판: <a href="#" onclick="javascript:getDetailView('310653');..."> 제목 </a> … <td class="num"> 2026-09-30 </td> (view.do 에 seq 를 POST, GET 주소도 열림)
        for m in re.finditer(r"[A-Za-z_]*[Vv]iew\(\s*'?(\d{5,})'?[^)]*\)[^>]*>(.*?)</a>", page, re.S):
            seq, txt = m.group(1), strip(m.group(2))
            if seq in seen or not txt:
                continue
            seen.add(seq)
            d = re.search(r"(20\d\d-\d\d-\d\d)", page[m.end(): m.end() + 1500])
            out.append({"seq": seq, "title": txt[:120], "date": d.group(1) if d else None, "url": url.split("list.do")[0] + "view.do?multi_itm_seq=2&seq=" + seq})
    return out


def attachments(page: str, url: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]*(?:download|fileDown|FileDown|atchFile|file)[^"]*)"[^>]*>(.*?)</a>', page, re.S | re.I):
        name = strip(m.group(2))
        if name:
            out.append({"name": name[:120], "url": urljoin(url, html.unescape(m.group(1)))})
    return out


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    log = [f"SH 임대 원천 점검 {NOW:%Y-%m-%d %H:%M}"]
    rows, used = [], None
    with httpx.Client(timeout=30, follow_redirects=True, headers=UA) as c:
        for u in LISTS:
            try:
                r = c.get(u)
                log.append(f"[목록] {u} → {r.status_code} {len(r.content)}B {r.headers.get('content-type')}")
                (RAW / f"list-{'app' if '/app/' in u else 'main'}.html").write_text(r.text[:200000], encoding="utf-8")
                rr = rows_from(r.text, u)
                log.append(f"  뽑은 줄 {len(rr)}" + "".join(f"\n   - {x['seq']} {x['date']} {x['title']}" for x in rr[:12]))
                if rr and not rows:
                    rows, used = rr, u
            except Exception as e:
                log.append(f"[목록] {u} 실패 {e.__class__.__name__}: {str(e)[:160]}")
        pdf_done = False
        pick = [x for x in rows if re.search(r"모집", x["title"]) and not re.search(r"발표|결과|안내", x["title"])] or rows   # 입주자 모집공고 먼저
        for x in pick[:4]:
            try:
                r = c.get(x["url"], headers={**UA, "Referer": used})
                (RAW / f"view-{x['seq']}.html").write_text(r.text[:200000], encoding="utf-8")
                at = attachments(r.text, x["url"])
                body = strip(re.sub(r"(?s)<(script|style).*?</\1>", " ", r.text))
                log.append(f"[상세] {x['seq']} {x['title'][:50]} → {r.status_code} · 첨부 {len(at)}" + "".join(f"\n   · {a['name']} | {a['url'][:160]}" for a in at[:8]))
                x["attachments"] = at
                x["body_head"] = body[:400]
                if not pdf_done:
                    for a in at:
                        if re.search(r"\.pdf|공고", a["name"], re.I):
                            try:
                                p = c.get(a["url"], headers={**UA, "Referer": x["url"]})
                                ok = p.content[:5] == b"%PDF-"
                                log.append(f"[첨부] {a['name']} → {p.status_code} {len(p.content)}B PDF={ok} {p.headers.get('content-type')}")
                                if ok:
                                    from pypdf import PdfReader
                                    rd = PdfReader(io.BytesIO(p.content))
                                    txt = "\n".join((pg.extract_text() or "") for pg in rd.pages[:6])
                                    (RAW / f"pdf-{x['seq']}.txt").write_text(txt[:30000], encoding="utf-8")
                                    log.append(f"  쪽수 {len(rd.pages)} · 앞 6쪽 글자 {len(txt)} · 소득 {'있음' if '소득' in txt else '없음'} · 자산 {'있음' if '자산' in txt else '없음'}")
                                    pdf_done = True
                                    break
                            except Exception as e:
                                log.append(f"[첨부] {a['name']} 실패 {e.__class__.__name__}: {str(e)[:160]}")
            except Exception as e:
                log.append(f"[상세] {x['seq']} 실패 {e.__class__.__name__}: {str(e)[:160]}")
        # 첨부 내려받기: 화면 a 태그는 existFile('n') 자바스크립트라 주소가 없다 → 스크립트 파일에서 함수를 찾고, initParam.downList(brdId·seq·fileSeq·oriFileNm)로 후보 주소를 시험
        try:
            for js in ("/app/js/sh/cms-common.js", "/app/lib/js/common.js", "/app/lib/js/front.js?v=02", "/app/lib/js/sub.js"):
                r = c.get(BASE + js)
                for m in re.finditer(r"function\s+(existFile|fn_?[Ff]ile[Dd]own\w*|[Ff]ile[Dd]own\w*|download\w*)\s*\([^)]*\)\s*\{", r.text):
                    log.append(f"[스크립트] {js} {m.group(1)}: " + re.sub(r"\s+", " ", r.text[m.start(): m.start() + 900]))
                for m in re.finditer(r"[\"'](/[^\"']*(?:[Dd]own|[Ff]ile)[^\"']*\.do)[\"']", r.text):
                    log.append(f"[스크립트] {js} 주소 {m.group(1)}")
        except Exception as e:
            log.append(f"[스크립트] 실패 {e}")
        x = next((x for x in pick if x.get("attachments")), None)
        if x:
            pg = (RAW / f"view-{x['seq']}.html").read_text(encoding="utf-8")
            m = re.search(r"downList\s*=\s*(\[.*?\]);", pg, re.S)
            dl = json.loads(m.group(1)) if m else []
            log.append(f"[첨부 목록] {x['seq']} " + "; ".join(f"{d.get('fileSeq')}:{d.get('oriFileNm')}" for d in dl))
            f0 = next((d for d in dl if str(d.get("oriFileNm", "")).lower().endswith(".pdf")), None)
            if f0:
                cands = [f"{BASE}/app/com/util/fileDown.do", f"{BASE}/app/com/util/fileDownload.do", f"{BASE}/app/com/util/download.do", f"{BASE}/main/com/util/fileDown.do"]
                prm = {"brd_id": f0["brdId"], "seq": f0["seq"], "data_tp": f0.get("fileTp", "A"), "file_seq": f0["fileSeq"]}
                for u in cands:
                    for meth in ("GET", "POST"):
                        try:
                            r = c.request(meth, u, params=prm if meth == "GET" else None, data=prm if meth == "POST" else None, headers={**UA, "Referer": x["url"]})
                            log.append(f"[내려받기 시험] {meth} {u} → {r.status_code} {len(r.content)}B PDF={r.content[:5] == b'%PDF-'} {r.headers.get('content-type')}")
                            if r.content[:5] == b"%PDF-":
                                from pypdf import PdfReader
                                rd = PdfReader(io.BytesIO(r.content)); txt = "\n".join((pg_.extract_text() or "") for pg_ in rd.pages[:8])
                                (RAW / f"pdf-{x['seq']}.txt").write_text(txt[:40000], encoding="utf-8")
                                log.append(f"  쪽수 {len(rd.pages)} · 앞 8쪽 글자 {len(txt)} · 소득 {'있음' if '소득' in txt else '없음'} · 자산 {'있음' if '자산' in txt else '없음'}")
                                raise StopIteration
                        except StopIteration:
                            break
                        except Exception as e:
                            log.append(f"[내려받기 시험] {meth} {u} 실패 {e.__class__.__name__}")
                    else:
                        continue
                    break
            # 미리보기(htmlConverter): 공고문을 HTML 로 바꿔 보여 주는 주소 — 글을 여기서 뽑을 수 있는지
            try:
                pv = f"{BASE}/app/com/util/htmlConverter.do?brd_id=GS0401&seq={x['seq']}&data_tp=A&file_seq={(f0 or {}).get('fileSeq', 1)}"
                r = c.get(pv, headers={**UA, "Referer": x["url"]})
                body = strip(re.sub(r"(?s)<(script|style).*?</\1>", " ", r.text))
                (RAW / f"preview-{x['seq']}.txt").write_text(body[:40000], encoding="utf-8")
                log.append(f"[미리보기] {pv} → {r.status_code} {len(r.content)}B 글자 {len(body)} · 소득 {'있음' if '소득' in body else '없음'} · 앞: {body[:160]}")
            except Exception as e:
                log.append(f"[미리보기] 실패 {e}")
    (RAW / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
