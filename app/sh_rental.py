"""SH(서울주택도시개발공사) 임대 모집공고 수집 — 1단계: 목록·접수 기간·공고문 연결만, 자격 판정은 하지 않음 (기능 sh_rental).
2026-10-06 사용자 '임대 범위 넓히기(SH 공고 추가) — 너가 추천하는 방향으로 진행'.

LH 수집(app/lh_rental.py)·청약 수집과 완전히 따로 돈다 — 결과는 docs/sh-rental.json, 공고문 글은 evidence/sh/<글번호>.txt(한 번 저장하면 다시 쓰지 않음).
공공데이터 API 가 없어 SH 인터넷청약시스템 '공고 및 공지 > 주택임대' 게시판을 읽는다(구조는 tools/qa/sh_probe.py 로 2026-10-06 확인, evidence/qa/sh-probe.txt):
 - 목록  /app/lay2/program/S48T1581C563/www/brd/m_247/list.do?multi_itm_seq=2  — <a onclick="getDetailView('310653')">제목</a> … 등록일
 - 상세  같은 경로 view.do?multi_itm_seq=2&seq=<글번호>  — 첨부 목록 initParam.downList = [{brdId, seq, fileSeq, oriFileNm, fileTp}]
 - 첨부  /com/file/existFile.do (POST) → /com/file/innoFD.do?brdId&seq&fileSeq&fileTp (GET, PDF)
읽는 것: 글번호·제목·등록일, 공고 종류(제목 낱말), 청년 대상 여부(제목), 접수 기간(공고문 글에서 '접수' 근처 날짜 범위 — 등록일 뒤 120일 안일 때만).
모르면 비워 두고 화면은 '공고문 확인'. 자격 판정은 2단계(종류별 정답 데이터 뒤)에서.
실행: python -m app.sh_rental (Actions 'SH 임대 수집' sh-rental.yml)"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "sh-rental.json"
TEXT_DIR = ROOT / "evidence" / "sh"
LOG = ROOT / "evidence" / "qa" / "sh-rental-log.txt"
KST = timezone(timedelta(hours=9))
BASE = "https://www.i-sh.co.kr"
BRD = BASE + "/app/lay2/program/S48T1581C563/www/brd/m_247/"
VIEW_PUBLIC = BASE + "/main/lay2/program/S1T294C297/www/brd/m_247/view.do?multi_itm_seq=2&seq={seq}"   # 사용자에게 여는 주소(PC·모바일 공용)
LOOKBACK_DAYS = 60
MAX_PAGES = 6
UA = {"User-Agent": "Mozilla/5.0 (cheongyak-bot; +https://github.com/cheongyak/cheongyak.github.io)", "Accept-Language": "ko-KR,ko;q=0.9"}

# 입주자 모집공고만 (당첨자·예비자 발표, 계약 안내, 심사 결과, 재계약 등은 뺀다)
WANT = re.compile(r"모집")
SKIP = re.compile(r"발표|결과|당첨|계약\s?안내|심사|재계약|설명회|서류\s?제출|안내문|연기|취소|경쟁률|게시")
# 공고 종류 (제목 낱말, 앞에서부터 처음 맞는 것)
KINDS = [
    (r"청년\s?안심\s?주택|역세권\s?청년", "청년안심주택"),
    (r"장기\s?전세|미리\s?내\s?집", "장기전세"),
    (r"사회\s?주택|토지지원", "사회주택"),
    (r"신혼|신생아", "신혼·신생아 매입임대"),
    (r"청년.{0,10}매입|매입.{0,20}청년|청년형", "청년 매입임대"),
    (r"매입\s?임대", "매입임대"),
    (r"행복\s?주택", "행복주택"),
    (r"국민\s?임대", "국민임대"),
    (r"영구\s?임대", "영구임대"),
    (r"장기\s?안심", "장기안심주택"),
    (r"공공\s?임대|공공\s?지원", "공공임대"),
]
strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def kind_of(title: str) -> str:
    return next((k for p, k in KINDS if re.search(p, title)), "기타 임대")


def rows_from(page: str) -> list[dict]:
    """목록 HTML → [{seq, title, date}] (sh_probe 와 같은 규칙)"""
    out, seen = [], set()
    for m in re.finditer(r"[A-Za-z_]*[Vv]iew\(\s*'?(\d{5,})'?[^)]*\)[^>]*>(.*?)</a>", page, re.S):
        seq, title = m.group(1), strip(m.group(2))
        if seq in seen or not title:
            continue
        seen.add(seq)
        d = re.search(r"(20\d\d-\d\d-\d\d)", page[m.end(): m.end() + 1500])
        out.append({"seq": seq, "title": title, "date": d.group(1) if d else None})
    return out


def downlist(page: str) -> list[dict]:
    m = re.search(r"downList\s*=\s*(\[.*?\]);", page, re.S)
    try:
        return json.loads(m.group(1)) if m else []
    except Exception:
        return []


def pick_pdf(files: list[dict]) -> Optional[dict]:
    """공고문 PDF 하나: 이름에 '공고' 가 있는 PDF 먼저, 없으면 첫 PDF (주택목록·서식 등은 뒤로)"""
    pdfs = [f for f in files if str(f.get("oriFileNm", "")).lower().endswith(".pdf")]
    pdfs.sort(key=lambda f: (0 if re.search(r"공고", f.get("oriFileNm", "")) else 1, 1 if re.search(r"목록|서식|신청서|안내", f.get("oriFileNm", "")) else 0))
    return pdfs[0] if pdfs else None


def file_url(f: dict) -> str:
    return BASE + "/com/file/innoFD.do?" + urlencode({"brdId": f.get("brdId"), "seq": f.get("seq"), "fileSeq": f.get("fileSeq"), "fileTp": f.get("fileTp") or "A"})


# 연도는 4자리 또는 '26. 처럼 2자리(SH 공고문 일정표: '26.10.1. (목) 10:00 ~ 10.2. (금))
_D = r"[‘'’]?(20\d\d|\d\d)\s?[.\-년]\s?(\d{1,2})\s?[.\-월]\s?(\d{1,2})\s?\.?\s?일?"
_D2 = r"(?:[‘'’]?(20\d\d|\d\d)\s?[.\-년]\s?)?(\d{1,2})\s?[.\-월]\s?(\d{1,2})\s?\.?\s?일?"
_Y = lambda y: int(y) + 2000 if len(y) == 2 else int(y)


def apply_period(text: str, posted: Optional[str]) -> Optional[dict]:
    """공고문 글에서 접수 기간: '접수' 낱말 뒤 120자 안의 '2026. 10. 13.(월) ~ 10. 15.(수)' 같은 범위.
    두 날짜가 등록일 이후 120일 안이고 시작 ≤ 끝일 때만 (아니면 None — 화면 '공고문 확인')."""
    if not text:
        return None
    t = re.sub(r"\s+", " ", text)
    p0 = date.fromisoformat(posted) if posted else None
    # 접수를 뜻하는 분명한 낱말만 (맨 '접수'·'신청기간'은 일정표·동시접수·서류 접수 안내와 섞여 틀린 날짜를 잡았음 — 2026-10-06 310258·310672·310673 원문 대조)
    for m in re.finditer(r"(?:청약\s?신청\s?접수|청약\s?접수|신청\s?접수|서류\s?접수|신청서\s?접수|인터넷\s?접수|접수\s?기간)", t):
        if re.search(r"우편\s?접수|방문\s?접수", t[max(0, m.start() - 300): m.start()]) or re.search(r"(?:동시|우편|방문|이메일|추가)\s?$", t[max(0, m.start() - 6): m.start()]):
            continue   # 우편·방문 접수 안내(인터넷 청약과 기간이 다름)는 쓰지 않는다
        seg = t[m.end(): m.end() + 160]
        # 접수 낱말 바로 뒤(40자 안)에 나오는 범위만. 범위 기호(~) 바로 앞의 날짜가 시작일 — 일정표는 '공고일 접수시작 ~ 접수끝'처럼 날짜가 줄지어 있어 그 앞 날짜(공고일)를 시작으로 잡지 않게 (2026-10-06 310258·310673)
        for tl in re.finditer(r"[~∼～]", seg):
            before = list(re.finditer(_D, seg[max(0, tl.start() - 40): tl.start()]))
            r2 = re.match(r"\s?" + _D2, seg[tl.end():])
            if not before or not r2:
                continue
            r1 = before[-1]
            s1 = max(0, tl.start() - 40) + r1.start()   # 시작 날짜의 seg 안 위치
            # 표 머리(단계 이름 ▶ ⇨ ➤ 로 이어진 줄) 뒤에 날짜가 줄지어 있으면 어느 날짜가 접수인지 모른다 (310673: 공고 ▶ 사전 주택공개 ▶ 청약접수 → 9.29~9.30 은 주택공개) → 읽지 않음
            if s1 > 40 or re.search(r"[▶⇨➤→►]", seg[:s1]):
                break
            gap = seg[max(0, tl.start() - 40) + r1.end(): tl.start()]
            if re.search(r"\d{1,2}\s?[.\-월]\s?\d{1,2}", gap) or len(gap) > 25:   # 사이에 다른 날짜가 끼었거나 너무 멀면 아님
                continue
            y1, m1, d1 = _Y(r1.group(1)), int(r1.group(2)), int(r1.group(3))
            y2 = _Y(r2.group(1)) if r2.group(1) else y1
            m2, d2 = int(r2.group(2)), int(r2.group(3))
            try:
                a, b = date(y1, m1, d1), date(y2, m2, d2)
            except ValueError:
                continue
            if b < a and not r2.group(1):
                try:
                    b = date(y1 + 1, m2, d2)
                except ValueError:
                    continue
            if a > b or (b - a).days > 60:
                continue
            if p0 and not (p0 - timedelta(days=3) <= a <= p0 + timedelta(days=120)):
                continue
            q = (t[m.start(): m.end()] + seg[: tl.end() + r2.end()]).strip()
            return {"apply_start": a.isoformat(), "apply_end": b.isoformat(), "rank1": bool(re.search(r"1\s?순위", q)), "quote": q[-160:]}
    return None


def notice_record(row: dict, files: list[dict], text: Optional[str]) -> dict:
    title = row["title"]
    f = pick_pdf(files)
    per = apply_period(text or "", row.get("date"))
    return {
        "id": "SH-" + row["seq"],
        "org": "SH",
        "name": title,
        "type": kind_of(title),
        "youth": bool(re.search(r"청년|대학생", title)),
        "judge_type": False,          # 1단계: 자격 판정 안 함 (화면 '판정 미지원 유형 · 공고문 확인')
        "region": "서울특별시",
        "posted": row.get("date"),
        "close": per["apply_end"] if per else None,
        "status": None,
        "url": VIEW_PUBLIC.format(seq=row["seq"]),
        "url_mobile": BRD + f"view.do?multi_itm_seq=2&seq={row['seq']}",
        "schedule": [{"complex": None, "apply_start": per["apply_start"], "apply_end": per["apply_end"], "docs_target": None, "winner": None, "rank1": per.get("rank1", False), "quote": per["quote"]}] if per else [],
        "complexes": [], "units": [], "rents": [], "terms": None,
        "files": [{"kind": "PDF 공고문" if f2 is f else "첨부", "name": f2.get("oriFileNm"), "url": file_url(f2)} for f2 in files],
        "notice_pdf": file_url(f) if f else None,
        "notice_text": len(text) if text else None,
        "office": {"place": None, "tel": None},
    }


def main() -> int:
    now = datetime.now(KST)
    since = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    log = [f"SH 임대 수집 {now:%Y-%m-%d %H:%M}"]
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    prev = {}
    try:
        prev = {n["id"]: n for n in json.loads(OUT.read_text(encoding="utf-8")).get("notices", [])}
    except Exception:
        pass
    rows: list[dict] = []
    with httpx.Client(timeout=40, follow_redirects=True, headers=UA) as c:
        for page in range(1, MAX_PAGES + 1):
            try:
                r = c.post(BRD + "list.do", data={"multi_itm_seq": "2", "page": str(page)}) if page > 1 else c.get(BRD + "list.do?multi_itm_seq=2")
                rr = rows_from(r.text)
                log.append(f"[목록] {page}쪽 HTTP {r.status_code} · {len(rr)}줄" + (f" · {rr[-1]['date']}" if rr else ""))
            except Exception as e:
                log.append(f"[목록] {page}쪽 실패 {e.__class__.__name__}")
                break
            new = [x for x in rr if x["seq"] not in {y["seq"] for y in rows}]
            if not new:
                break
            rows += new
            if all((x["date"] or "9999") < since for x in new):
                break
            time.sleep(0.5)
        want = [x for x in rows if (x["date"] or "") >= since and WANT.search(x["title"]) and not SKIP.search(x["title"])]
        log.append(f"[목록] 전체 {len(rows)}줄 · {since} 이후 입주자 모집공고 {len(want)}건")
        notices = []
        for x in want:
            nid = "SH-" + x["seq"]
            tp = TEXT_DIR / f"{x['seq']}.txt"
            try:
                if nid in prev and tp.exists():   # 예전에 읽은 공고: 글은 다시 받지 않음(첨부 목록만 그대로)
                    files = [{"oriFileNm": f["name"], **dict(re.findall(r"(brdId|seq|fileSeq|fileTp)=([^&]+)", f["url"]))} for f in prev[nid].get("files", [])]
                    rec = notice_record(x, files, tp.read_text(encoding="utf-8"))
                    rec["files"], rec["notice_pdf"] = prev[nid].get("files", []), prev[nid].get("notice_pdf")
                    notices.append(rec)
                    log.append(f"[공고] {nid} {x['title'][:40]} · 이전 글 · 접수 {rec['schedule'][0]['apply_start'] + '~' + rec['schedule'][0]['apply_end'] if rec['schedule'] else '못 읽음'}")
                    continue
                v = c.get(BRD + f"view.do?multi_itm_seq=2&seq={x['seq']}")
                files = downlist(v.text)
                f = pick_pdf(files)
                text, msg = None, "공고문 PDF 없음"
                if f:
                    try:
                        c.post(BASE + "/com/file/existFile.do", data={"brdId": f["brdId"], "seq": f["seq"], "fileSeq": f["fileSeq"], "fileTp": f.get("fileTp") or "A"}, headers={"X-Requested-With": "XMLHttpRequest"})
                        p = c.get(file_url(f))
                        if p.status_code == 200 and p.content[:4] == b"%PDF":
                            from app.lh_rental import pdf_to_text
                            text, msg = pdf_to_text(p.content)
                        else:
                            msg = f"PDF 아님(HTTP {p.status_code}, {len(p.content)}바이트)"
                    except Exception as e:
                        msg = f"받기 실패 {e.__class__.__name__}"
                if text and not tp.exists():
                    tp.write_text(text, encoding="utf-8")
                rec = notice_record(x, files, text)
                notices.append(rec)
                log.append(f"[공고] {nid} {x['title'][:40]} · {rec['type']} · 첨부 {len(files)} · {msg} · 접수 {rec['schedule'][0]['apply_start'] + '~' + rec['schedule'][0]['apply_end'] if rec['schedule'] else '못 읽음'}")
                time.sleep(0.5)
            except Exception as e:   # 한 공고가 실패해도 계속
                log.append(f"[공고] {nid} 실패 {e.__class__.__name__}: {str(e)[:120]}")
    if not notices and prev:
        log.append("[경고] SH 공고를 0건 읽음 — 지난 결과를 그대로 둠")
        LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 0
    out = {"updated": now.strftime("%Y-%m-%d %H:%M"), "source": "SH 인터넷청약시스템 공고 및 공지 > 주택임대 (서울주택도시개발공사)", "count": len(notices), "notices": notices}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
