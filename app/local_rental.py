"""지방 공사 임대 모집공고 수집 — 1단계: 목록·일정·단지·보증금·월 임대료, 자격 판정은 하지 않음 (기능 local_rental, 2026-10-22).
2026-10-22 사용자 '임대 공고 중 안 다루는 것도 다 수집해서 화면에' → 같은 날 운영자가 마이홈포털 API 이용 신청 완료.

국토교통부 마이홈포털 공공주택 모집공고 조회 API (apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList, DATA_GO_KR_KEY).
응답 칸은 2026-10-22 tools/qa/myhome_probe.py 로 확인(evidence/qa/myhome-probe.json): 한 줄 = 공고(pblancId) × 단지(houseSn).
  suplyInsttNm 공급기관 · suplyTyNm 공급유형(영구임대·국민임대·행복주택·매입임대 …) · houseTyNm 주택유형 · pblancNm 공고명 · sttusNm 일반공고/정정공고
  beforePblancId 정정 전 공고 · rcritPblancDe 모집공고일 · beginDe/endDe 접수 · przwnerPresnatnDe 당첨자 발표 · hsmpNm 단지 · brtcNm 시도 · signguNm 시군구
  fullAdres 주소 · sumSuplyCo 공급 호수 · rentGtn 임대보증금(원) · mtRntchrg 월 임대료(원) · refrnc 문의처 · url 공급기관 공고 글 · pcUrl/mobileUrl 마이홈포털 상세
LH·SH·GH 는 따로 수집하므로(공고문까지 읽음) 빼고, 나머지 공급기관(광주광역시도시공사·제주특별자치도개발공사·인천도시공사 등)만 docs/local-rental.json 으로.
보증금·월 임대료가 0이거나 없으면 비워 둔다(화면 '공고문 확인'). 실행: python -m app.local_rental (Actions '지방 공사 임대 수집' local-rental.yml)"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "local-rental.json"
LOG = ROOT / "evidence" / "qa" / "local-rental-log.txt"
URL = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"
KST = timezone(timedelta(hours=9))
SKIP = ("LH", "한국토지주택공사", "SH", "서울주택도시공사", "GH", "경기주택도시공사")   # 따로 수집 (app/lh_rental·sh_rental·gh_rental)
LOOKBACK_DAYS = 120
KEEP_AFTER_WINNER_DAYS = 14


def _d(s) -> Optional[str]:
    s = str(s or "").strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


def _won(v) -> Optional[int]:
    try:
        n = int(float(v))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def fetch(key: str, client: Optional[httpx.Client] = None, log: Optional[list] = None) -> list[dict]:
    http = client or httpx.Client(timeout=httpx.Timeout(30, connect=10))
    rows, page = [], 1
    while page <= 30:
        r = http.get(URL, params={"serviceKey": key, "pageNo": page, "numOfRows": 100, "_type": "json"})
        r.raise_for_status()
        body = (r.json().get("response") or {}).get("body") or {}
        items = body.get("item") or []
        if isinstance(items, dict):
            items = [items]
        rows += items
        total = int(body.get("totalCount") or 0)
        if log is not None and page == 1:
            log.append(f"[목록] 전체 {total}줄")
        if not items or len(rows) >= total:
            break
        page += 1
    return rows


def build(rows: list[dict], today: date) -> tuple[list[dict], dict]:
    """줄(공고 × 단지) → 공고. 정정공고가 가리키는 옛 공고(beforePblancId)는 뺀다. LH·SH·GH 는 뺀다"""
    superseded = {str(r.get("beforePblancId")) for r in rows if r.get("beforePblancId")}
    since = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    by: dict[str, dict] = {}
    count = {"줄": len(rows), "LH·SH·GH 뺌": 0, "정정 전 공고 뺌": 0, "지난 공고 뺌": 0}
    for r in rows:
        inst = str(r.get("suplyInsttNm") or "").strip()
        pid = str(r.get("pblancId") or "")
        if not pid:
            continue
        if inst in SKIP:
            count["LH·SH·GH 뺌"] += 1
            continue
        if pid in superseded:
            count["정정 전 공고 뺌"] += 1
            continue
        posted, end, win = _d(r.get("rcritPblancDe")), _d(r.get("endDe")), _d(r.get("przwnerPresnatnDe"))
        last = (date.fromisoformat(win) + timedelta(days=KEEP_AFTER_WINNER_DAYS)).isoformat() if win else end
        if (posted and posted < since) or (last and last < today.isoformat()):
            count["지난 공고 뺌"] += 1
            continue
        N = by.setdefault(pid, {
            "id": "LOC-" + pid, "org": "LOCAL", "inst": inst, "name": str(r.get("pblancNm") or "").strip(), "type": r.get("suplyTyNm") or "임대",
            "judge_type": False, "youth": False, "region": r.get("brtcNm"), "posted": posted, "close": end, "status": r.get("sttusNm"),
            "url": r.get("url") or r.get("pcUrl"), "url_mobile": r.get("mobileUrl") or r.get("url"), "myhome_url": r.get("pcUrl"),
            "schedule": [], "complexes": [], "units": [], "rents": [], "terms": None, "files": [], "notice_pdf": None,
            "office": {"place": None, "tel": (str(r.get("refrnc") or "").strip() or None)}})
        cx = str(r.get("hsmpNm") or "").strip() or None
        b, e = _d(r.get("beginDe")), end
        if b or e:
            s = {"complex": cx, "apply_start": b, "apply_end": e, "docs_target": None, "winner": win, "contract_start": None, "contract_end": None}
            if s not in N["schedule"]:
                N["schedule"].append(s)
        if cx and not any(c["name"] == cx for c in N["complexes"]):
            N["complexes"].append({"name": cx, "address": str(r.get("fullAdres") or "").strip() or None, "households": _won(r.get("totHshldCo")),
                                   "heating": r.get("heatMthdNm") or None, "house_type": r.get("houseTyNm") or None})
        n = _won(r.get("sumSuplyCo"))
        N["units"].append({"complex": cx, "type": r.get("houseTyNm") or "", "area": None, "households": n, "now_households": n, "deposit": None, "rent": None})
        dep, rent = _won(r.get("rentGtn")), _won(r.get("mtRntchrg"))
        if dep or rent:
            N["rents"].append({"complex": cx, "type": r.get("houseTyNm") or "", "group": None, "deposit": dep, "rent": rent})
        if e and (not N["close"] or e > N["close"]):
            N["close"] = e
    return sorted(by.values(), key=lambda n: n["posted"] or "", reverse=True), count


def main() -> int:
    now = datetime.now(KST)
    key = os.environ.get("DATA_GO_KR_KEY", "")
    log = [f"지방 공사 임대 수집 {now:%Y-%m-%d %H:%M}"]
    try:
        rows = fetch(key, log=log)
    except Exception as e:
        log.append(f"[경고] 마이홈포털 API 실패 {e.__class__.__name__} — 지난 결과를 그대로 둠")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return 0
    if rows:
        log.append(f"[응답 필드] {', '.join(sorted(rows[0].keys()))}")
    insts: dict[str, int] = {}
    for r in rows:
        k = str(r.get("suplyInsttNm") or "?")
        insts[k] = insts.get(k, 0) + 1
    log.append(f"[공급기관] {insts}")
    notices, count = build(rows, now.date())
    log.append(f"[거름] {count} → 공고 {len(notices)}건")
    for N in notices:
        s = N["schedule"][0] if N["schedule"] else {}
        log.append(f"[공고] {N['id']} {N['inst']} · {N['type']} · {N['name'][:40]} · 접수 {s.get('apply_start')}~{s.get('apply_end')} · 단지 {len(N['complexes'])} · 임대조건 {len(N['rents'])}줄")
    if not notices and OUT.exists() and not rows:
        log.append("[경고] 0줄 받음 — 지난 결과를 그대로 둠")
    else:
        OUT.write_text(json.dumps({"updated": now.strftime("%Y-%m-%d %H:%M"), "source": "국토교통부 마이홈포털 공공주택 모집공고 조회 서비스 (LH·SH·GH 제외)",
                                   "count": len(notices), "notices": notices}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(log) + "\n"
    if key:
        text = text.replace(key, "***")
    LOG.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
