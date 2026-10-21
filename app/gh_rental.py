"""GH(경기주택도시공사) 임대 모집공고 수집 — 1단계: 목록·접수 기간·공고문 연결만, 자격 판정은 하지 않음 (기능 gh_rental).
2026-10-21 사용자 'GH 임대 → 공공지원 민간임대 순서로 추가'.

LH·SH·청약 수집과 완전히 따로 돈다 — 결과는 docs/gh-rental.json, 공고문 글은 evidence/gh/<글번호>.txt(한 번 저장하면 다시 쓰지 않음).
공공데이터 API 가 없고 GH 청약센터(apply.gh.or.kr)는 Actions 서버에서 접속이 안 돼(2026-10-21 tools/qa/gh_probe.py, 시간 초과),
GH 누리집 '청약정보 > 분양/임대 공고' 게시판의 '주택' 분류(srCategoryId=12)를 읽는다:
 - 목록  https://www.gh.or.kr/gh/announcement-of-salerental001.do?mode=list&srCategoryId=12&articleLimit=10&article.offset=<0,10,…>
         <td class="title"><a href="?mode=view&articleNo=65277…">제목</a> · <td class="date">26.10.16</td> · 첨부 ?mode=download&articleNo&attachNo (alt 에 파일 이름)
 - 상세  ?mode=view&articleNo=<글번호> — 첨부가 목록에 없으면 여기서 찾는다
읽는 것: 글번호·제목·등록일·공고 종류(제목 낱말)·접수 기간(공고문 글, SH 와 같은 규칙 app.sh_rental.apply_period). 분양 공고(청약홈에 있음)는 뺀다.
모르면 비워 두고 화면은 '공고문 확인'. 자격 판정은 2단계(종류별 정답 데이터 뒤)에서.
실행: python -m app.gh_rental (Actions 'GH 임대 수집' gh-rental.yml)"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.sh_rental import apply_period

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "gh-rental.json"
TEXT_DIR = ROOT / "evidence" / "gh"
LOG = ROOT / "evidence" / "qa" / "gh-rental-log.txt"
KST = timezone(timedelta(hours=9))
BOARD = "https://www.gh.or.kr/gh/announcement-of-salerental001.do"
LOOKBACK_DAYS = 60
MAX_PAGES = 8
UA = {"User-Agent": "Mozilla/5.0 (cheongyak-bot; +https://github.com/cheongyak/cheongyak.github.io)", "Accept-Language": "ko-KR,ko;q=0.9"}

WANT = re.compile(r"모집")
SKIP = re.compile(r"발표|결과|당첨|계약\s?안내|심사|재계약|설명회|서류\s?제출|안내문|연기|취소|경쟁률|게시|변동|명단|선정")
SALE = re.compile(r"분양주택|분양\s?전환\s?(?!공공임대)|임의공급|공공분양|민영주택")   # 분양 공고는 청약홈(일반분양·임의공급)에서 다룬다
KINDS = [
    (r"행복\s?주택", "행복주택"),
    (r"장기\s?전세", "장기전세"),
    (r"신혼|신생아", "신혼·신생아 매입임대"),
    (r"청년.{0,10}매입|매입.{0,20}청년|청년형", "청년 매입임대"),
    (r"매입\s?임대", "매입임대"),
    (r"전세\s?임대", "전세임대"),
    (r"국민\s?임대", "국민임대"),
    (r"영구\s?임대", "영구임대"),
    (r"통합\s?공공\s?임대", "통합공공임대"),
    (r"공공\s?임대", "공공임대"),
    (r"기숙사", "기숙사"),
]
strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def kind_of(title: str) -> str:
    return next((k for p, k in KINDS if re.search(p, title)), "기타 임대")


def _date(s: str) -> Optional[str]:
    m = re.search(r"(\d{2,4})\.(\d{1,2})\.(\d{1,2})", s or "")
    if not m:
        return None
    y = int(m.group(1)) + (2000 if len(m.group(1)) == 2 else 0)
    return f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def files_in(chunk: str) -> list[dict]:
    """?mode=download&articleNo=…&attachNo=… 링크와 파일 이름 (img alt 'GH <이름> - 다운로드' 또는 링크 글자)"""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(\?mode=download&(?:amp;)?articleNo=(\d+)&(?:amp;)?attachNo=(\d+))"[^>]*>(.*?)</a>', chunk, re.S):
        if m.group(3) in seen:
            continue
        seen.add(m.group(3))
        alt = re.search(r'alt="(?:GH\s)?(.*?)\s?-\s?다운로드"', m.group(4))
        name = html.unescape(alt.group(1)) if alt else strip(m.group(4))
        out.append({"name": name, "url": f"{BOARD}?mode=download&articleNo={m.group(2)}&attachNo={m.group(3)}"})
    return out


def rows_from(page: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        r = m.group(1)
        a = re.search(r'<td class="title">.*?<a href="\?mode=view&(?:amp;)?articleNo=(\d+)[^"]*"[^>]*>(.*?)</a>', r, re.S)
        if not a:
            continue
        d = re.search(r'<td class="date">(.*?)</td>', r, re.S)
        cat = re.search(r'<td class="category">(.*?)</td>', r, re.S)
        out.append({"no": a.group(1), "title": strip(a.group(2)), "date": _date(strip(d.group(1))) if d else None,
                    "category": strip(cat.group(1)) if cat else None, "files": files_in(r)})
    return out


def pick_pdf(files: list[dict]) -> Optional[dict]:
    pdfs = [f for f in files if str(f.get("name", "")).lower().endswith(".pdf")]
    pdfs.sort(key=lambda f: (0 if re.search(r"공고", f["name"]) else 1, 1 if re.search(r"명단|서식|신청서|목록|안내문", f["name"]) else 0))
    return pdfs[0] if pdfs else None


def notice_record(row: dict, files: list[dict], text: Optional[str]) -> dict:
    title, f = row["title"], pick_pdf(files)
    per = apply_period(text or "", row.get("date"))
    return {
        "id": "GH-" + row["no"], "org": "GH", "name": title, "type": kind_of(title),
        "youth": bool(re.search(r"청년|대학생", title)), "judge_type": False,   # 1단계: 자격 판정 안 함
        "region": "경기도", "posted": row.get("date"), "close": per["apply_end"] if per else None, "status": None,
        "url": f"{BOARD}?mode=view&articleNo={row['no']}", "url_mobile": f"{BOARD}?mode=view&articleNo={row['no']}",
        "schedule": [{"complex": None, "apply_start": per["apply_start"], "apply_end": per["apply_end"], "docs_target": None, "winner": None,
                      "rank1": per.get("rank1", False), "quote": per["quote"]}] if per else [],
        "complexes": [], "units": [], "rents": [], "terms": None,
        "files": [{"kind": "PDF 공고문" if x is f else "첨부", "name": x["name"], "url": x["url"]} for x in files],
        "notice_pdf": f["url"] if f else None, "notice_text": len(text) if text else None,
        "office": {"place": None, "tel": None},
    }


def main() -> int:
    now = datetime.now(KST)
    since = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    log = [f"GH 임대 수집 {now:%Y-%m-%d %H:%M}"]
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    prev = {}
    try:
        prev = {n["id"]: n for n in json.loads(OUT.read_text(encoding="utf-8")).get("notices", [])}
    except Exception:
        pass
    rows: list[dict] = []
    notices: list[dict] = []
    with httpx.Client(timeout=40, follow_redirects=True, headers=UA) as c:
        for page in range(MAX_PAGES):
            try:
                r = c.get(BOARD, params={"mode": "list", "srCategoryId": "12", "articleLimit": "10", "article.offset": str(page * 10)})
                rr = rows_from(r.text)
                log.append(f"[목록] {page + 1}쪽 HTTP {r.status_code} · {len(rr)}줄" + (f" · {rr[-1]['date']}" if rr else ""))
            except Exception as e:
                log.append(f"[목록] {page + 1}쪽 실패 {e.__class__.__name__}")
                break
            new = [x for x in rr if x["no"] not in {y["no"] for y in rows}]
            if not new:
                break
            rows += new
            if all((x["date"] or "9999") < since for x in new):
                break
            time.sleep(0.5)
        want = [x for x in rows if (x["date"] or "") >= since and WANT.search(x["title"]) and not SKIP.search(x["title"]) and not SALE.search(x["title"])]
        log.append(f"[목록] 전체 {len(rows)}줄 · {since} 이후 임대 입주자 모집공고 {len(want)}건 (분양·발표·결과 글 뺌)")
        for x in want:
            nid = "GH-" + x["no"]
            tp = TEXT_DIR / f"{x['no']}.txt"
            try:
                files = x["files"]
                if not files:   # 목록에 첨부가 없으면 상세에서
                    v = c.get(BOARD, params={"mode": "view", "articleNo": x["no"]})
                    files = files_in(v.text)
                    if not files:
                        (ROOT / "evidence/qa/gh").mkdir(parents=True, exist_ok=True)
                        (ROOT / "evidence/qa/gh" / f"view-{x['no']}.html").write_text(v.text[:300_000], encoding="utf-8")   # 원인 확인용
                text, msg = None, "공고문 PDF 없음"
                if tp.exists():
                    text, msg = tp.read_text(encoding="utf-8"), "이전 글"
                elif (f := pick_pdf(files)):
                    p = c.get(f["url"])
                    if p.status_code == 200 and p.content[:4] == b"%PDF":
                        from app.lh_rental import pdf_to_text
                        text, msg = pdf_to_text(p.content)
                        if text:
                            tp.write_text(text, encoding="utf-8")
                    else:
                        msg = f"PDF 아님(HTTP {p.status_code}, {len(p.content)}바이트)"
                rec = notice_record(x, files, text)
                notices.append(rec)
                log.append(f"[공고] {nid} {x['title'][:40]} · {rec['type']} · 첨부 {len(files)} · {msg} · 접수 "
                           + (f"{rec['schedule'][0]['apply_start']}~{rec['schedule'][0]['apply_end']}" if rec["schedule"] else "못 읽음"))
                time.sleep(0.5)
            except Exception as e:
                log.append(f"[공고] {nid} 실패 {e.__class__.__name__}: {str(e)[:120]}")
    if not notices and prev:
        log.append("[경고] GH 공고를 0건 읽음 — 지난 결과를 그대로 둠")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 0
    out = {"updated": now.strftime("%Y-%m-%d %H:%M"), "source": "GH 누리집 청약정보 > 분양/임대 공고 > 주택 (경기주택도시공사)", "count": len(notices), "notices": notices}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
