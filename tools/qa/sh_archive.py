"""SH 지난 모집공고 원문 모으기 (조사 도구, 2026-10-08 사용자 'Abc 순차로' A — SH 청년안심주택·행복주택 판정 준비).
매일 수집(app/sh_rental.py)은 최근 60일만 보므로, 판정 규칙을 만들 원문(정답 데이터)이 없는 종류는 게시판을 더 깊이 넘겨 지난 공고문을 모은다.
 - 대상 종류: 행복주택 · 청년안심주택(역세권 청년주택) · 국민임대 · 영구임대 (제목 낱말, app/sh_rental.KINDS)
 - 종류마다 최근 공고 KEEP 건까지 공고문 PDF 글을 evidence/qa/sh-archive/<글번호>.txt 로 저장(한 번 저장하면 다시 받지 않음), 목록은 index.json
화면·판정에는 쓰지 않는다. 실행: python -m tools.qa.sh_archive (Actions 'SH 임대 원천 점검')"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import httpx  # noqa: E402

from app.sh_rental import BASE, BRD, SKIP, UA, WANT, downlist, file_url, kind_of, pick_pdf, rows_from  # noqa: E402

OUT = ROOT / "evidence" / "qa" / "sh-archive"
TARGET = {"행복주택", "청년안심주택", "국민임대", "영구임대"}
KEEP = 6
MAX_PAGES = 80


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    idx_f = OUT / "index.json"
    idx = json.loads(idx_f.read_text(encoding="utf-8")) if idx_f.exists() else {}
    rows, log = [], []
    with httpx.Client(timeout=40, follow_redirects=True, headers=UA) as c:
        for page in range(1, MAX_PAGES + 1):
            try:
                r = c.post(BRD + "list.do", data={"multi_itm_seq": "2", "page": str(page)}) if page > 1 else c.get(BRD + "list.do?multi_itm_seq=2")
                rr = rows_from(r.text)
            except Exception as e:
                log.append(f"[목록] {page}쪽 실패 {e.__class__.__name__}")
                break
            new = [x for x in rr if x["seq"] not in {y["seq"] for y in rows}]
            if not new:
                break
            rows += new
            time.sleep(0.4)
        log.append(f"[목록] {page}쪽까지 {len(rows)}줄 · 마지막 {rows[-1]['date'] if rows else '-'}")
        cnt: dict[str, int] = {}
        for x in rows:
            k = kind_of(x["title"])
            if k not in TARGET or not WANT.search(x["title"]) or SKIP.search(x["title"]):
                continue
            cnt[k] = cnt.get(k, 0) + 1
            if cnt[k] > KEEP:
                continue
            tp = OUT / f"{x['seq']}.txt"
            if tp.exists():
                log.append(f"[있음] {x['seq']} {k} {x['date']} {x['title'][:50]}")
                continue
            try:
                v = c.get(BRD + f"view.do?multi_itm_seq=2&seq={x['seq']}")
                files = downlist(v.text)
                f = pick_pdf(files)
                msg = "공고문 PDF 없음"
                if f:
                    c.post(BASE + "/com/file/existFile.do", data={"brdId": f["brdId"], "seq": f["seq"], "fileSeq": f["fileSeq"], "fileTp": f.get("fileTp") or "A"}, headers={"X-Requested-With": "XMLHttpRequest"})
                    p = c.get(file_url(f))
                    if p.status_code == 200 and p.content[:4] == b"%PDF":
                        from app.lh_rental import pdf_to_text
                        text, msg = pdf_to_text(p.content)
                        if text:
                            tp.write_text(text, encoding="utf-8")
                    else:
                        msg = f"PDF 아님(HTTP {p.status_code})"
                idx[x["seq"]] = {"kind": k, "title": x["title"], "date": x["date"], "pdf": f and f.get("oriFileNm"), "url": f and file_url(f),
                                 "files": [g.get("oriFileNm") for g in files]}
                log.append(f"[받음] {x['seq']} {k} {x['date']} {x['title'][:50]} · {msg}")
                time.sleep(0.5)
            except Exception as e:
                log.append(f"[실패] {x['seq']} {k} {e.__class__.__name__}")
        log.append("[종류별 모집공고 수] " + json.dumps(cnt, ensure_ascii=False))
    idx_f.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
