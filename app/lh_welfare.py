"""LH 주거복지(매입임대·든든전세)·신혼희망타운 행복주택 공고 수집 — 목록만, 자격 판정 없음 (2026-10-22 운영자 '넣어줘', 기능 lh_welfare).

왜 따로: app/lh_rental.py 는 LH 대분류 '임대주택'(UPP_AIS_TP_CD=06)만 수집해서, 같은 LH 청약플러스에 올라오는
  - 주거복지(13) / 매입임대(26): 청년·신혼·신생아 매입임대, 든든전세주택, 기존주택 매입임대 (현장·선착순 접수 포함)
  - 공공분양(신혼희망)(39) / 행복주택(신혼희망)(42): 신혼희망타운 안 행복주택
  가 처음부터 빠져 있었다(evidence/qa/lh-probe.txt '[06 밖]', 2026-10-22 확인). 기존 docs/lh-rental.json·판정·검사에 영향을 주지 않도록
  결과는 docs/lh-welfare.json 한 파일로만 쓰고, 화면은 스위치 lh_welfare 가 켜졌을 때만 이 파일을 불러 '판정 미지원 · 공고문 확인'으로 목록에 섞는다.
공고문 PDF 는 받지 않는다(지역본부마다 형식이 달라 자격 판정은 원문을 모은 뒤 다음 단계). 일정·단지·주택형·첨부는 LH 상세·공급 API 그대로.
실행: python -m app.lh_welfare (Actions 'LH 임대 수집' 뒤 단계, 실패해도 LH 임대 수집은 그대로)"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta

import httpx

from app.lh_rental import DTL, KST, LIST, ROOT, SPL, TEXT_DIR, UA, _d, alt_paths, feature_on, fetch_pdf, notice_record, org_target, pdf_to_text, save_alt_texts

OUT = ROOT / "docs" / "lh-welfare.json"
LOG = ROOT / "evidence" / "qa" / "lh-welfare-log.txt"
LOOKBACK_DAYS = 60
# (대분류 코드, 받을 유형 이름) — 이름이 API 응답(AIS_TP_CD_NM)과 같을 때만 받는다. 상가·토지·공공분양 본 공고는 받지 않는다.
WANT = {"13": ("매입임대", "전세임대"), "39": ("행복주택(신혼희망)",)}


def kind_of(row: dict) -> str:
    """화면 유형 이름: 든든전세는 API 유형이 '매입임대'라도 따로 (공고 제목으로). 그 밖은 API 유형 그대로"""
    name, t = row.get("PAN_NM") or "", row.get("AIS_TP_CD_NM") or ""
    if "든든전세" in name:
        return "든든전세"
    return t


def keep(row: dict, today: str) -> bool:
    """받을 공고: 원하는 대분류·유형이고, 마감이 오늘 이후(또는 마감일 없음)이며, 접수마감이 아니고, 기관·기업 대상이 아님"""
    up, t = row.get("UPP_AIS_TP_CD"), row.get("AIS_TP_CD_NM") or ""
    if up not in WANT or t not in WANT[up]:
        return False
    if row.get("PAN_SS") == "접수마감":
        return False
    close = _d(row.get("CLSG_DT"))
    if close and close < today:
        return False
    return not org_target(row.get("PAN_NM") or "")


CORR = re.compile(r"^\s*\[\s*정정\s*(?:공고)?\s*\]\s*")


def _title_key(name: str) -> str:
    """정정 표시를 뗀 제목(공백 무시) — 정정 공고와 원 공고를 잇는 데만 쓴다"""
    return re.sub(r"\s", "", CORR.sub("", name or ""))


def drop_superseded(rows: list[dict], log: list[str]) -> list[dict]:
    """정정 공고가 있으면 원 공고는 뺀다 (2026-10-22 운영자 '정정공고로 보여줘야지').
    LH 주거복지 정정 공고는 원 공고와 공고번호가 달라(경남 0901 → 0934, 경기남부 0802 → 0927·0731 → 0769) 둘 다 목록에 온다.
    '[정정공고]'를 뗀 제목이 글자 그대로(공백 무시) 같을 때만 원 공고로 본다 — 비슷한 제목을 짐작해 합치지 않는다."""
    fixed = {_title_key(r.get("PAN_NM")): r["PAN_ID"] for r in rows if CORR.match(r.get("PAN_NM") or "")}
    out = []
    for r in rows:
        k = _title_key(r.get("PAN_NM"))
        if not CORR.match(r.get("PAN_NM") or "") and k in fixed:
            log.append(f"[목록·정정] 원 공고 {r['PAN_ID']} 는 정정 공고 {fixed[k]} 로 대신함 · {(r.get('PAN_NM') or '')[:50]}")
            continue
        out.append(r)
    return out


def record(row: dict, dtl, spl) -> dict:
    rec = notice_record(row, dtl, spl)
    rec.update({"type": kind_of(row), "type_api": row.get("AIS_TP_CD_NM"), "upper": row.get("UPP_AIS_TP_NM"),
                "judge_type": False, "welfare": True, "rents": [], "terms": None})
    return rec


LIST_DIR = ROOT / "evidence" / "lh" / "lists"   # 첨부 '주택목록' 엑셀을 글(csv)로 — 매입임대·든든전세 보증금·월세는 주택마다 달라 공고문이 아니라 이 목록에 있다


def _get(http: httpx.Client, url: str, referer) -> tuple:
    try:
        r = http.get(url, headers={**UA, **({"Referer": referer} if referer else {})})
        return (r.content, f"HTTP {r.status_code}") if r.status_code == 200 else (None, f"HTTP {r.status_code}")
    except Exception as e:
        return None, f"받기 실패 {e.__class__.__name__}"


def xlsx_to_csv(data: bytes, cap: int = 3000) -> tuple:
    """주택목록 엑셀 → csv 글(첫 시트 전부, 최대 cap 줄). 값은 그대로 — 해석(금액 단위·열 이름)은 하지 않는다"""
    try:
        import csv, io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        buf, n = io.StringIO(), 0
        w = csv.writer(buf)
        for row in ws.iter_rows(values_only=True):
            if n >= cap:
                break
            if any(v not in (None, "") for v in row):
                w.writerow(["" if v is None else v for v in row])
                n += 1
        return buf.getvalue(), f"주택목록 {n}줄"
    except Exception as e:
        return None, f"주택목록 읽기 실패 {e.__class__.__name__}"


def read_notice(http: httpx.Client, rec: dict) -> str:
    """공고문을 읽어 rec 에 글 길이·보증금·월세(공고문 임대조건 표)·주택목록 파일을 채운다 → 기록용 문장.
    글은 evidence/lh/<공고ID>.txt 에 한 번만 저장(LH 임대와 같은 곳·같은 규칙), 다른 도구 글도 같이(기능 lh_pdf_multi).
    PDF 를 못 읽으면 같은 공고문의 .hwpx 로(app/hwpx_text). 보증금·월세는 LH 임대와 같은 읽기(app/lh_pdf_merge.read_all, 자격 판정은 하지 않음)."""
    nid, msg = rec["id"], []
    tp = TEXT_DIR / f"{nid}.txt"
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    if tp.exists() and tp.stat().st_size:
        msg.append("공고문 저장본")
        need_alt = feature_on("lh_pdf_multi") and rec["notice_pdf"] and not all(p.exists() for k, p in alt_paths(nid).items() if k != "tables")
        if need_alt:
            data, m = fetch_pdf(http, rec["notice_pdf"], rec["url"])
            msg.append("다른 읽기 도구 " + (save_alt_texts(nid, data) if data else m))
    else:
        text = None
        if rec["notice_pdf"]:
            data, m = fetch_pdf(http, rec["notice_pdf"], rec["url"])
            text, m = pdf_to_text(data) if data else (None, m)
            msg.append(f"공고문 PDF {m}")
            if text and feature_on("lh_pdf_multi"):
                msg.append("다른 읽기 도구 " + save_alt_texts(nid, data))
        if not text:
            h = next((f for f in rec["files"] if (f.get("name") or "").lower().endswith(".hwpx") and "공고문" in (f.get("kind") or "")), None)
            if h:
                from app.hwpx_text import hwpx_to_text
                data, m = _get(http, h["url"], rec["url"])
                text, m = hwpx_to_text(data) if data else (None, m)
                msg.append(f"공고문 HWPX {m}")
        if text:
            tp.write_text(text, encoding="utf-8")
    if tp.exists() and tp.stat().st_size:
        rec["notice_text"] = tp.stat().st_size
        try:
            from app.lh_pdf_merge import read_all
            P = alt_paths(nid)
            texts = {"pypdf": tp.read_text(encoding="utf-8")}
            for k in ("pdfium", "plumber"):
                if P[k].exists():
                    texts[k] = P[k].read_text(encoding="utf-8")
            tables = json.loads(P["tables"].read_text(encoding="utf-8")) if P["tables"].exists() else []
            got = read_all(texts, rec["type"], rec["name"] or "", rec["region"], [u["type"] for u in rec["units"]], False, tables)
            rec["rents"] = got["rents"]
            msg.append(f"임대조건 {len(rec['rents'])}줄")
        except Exception as e:
            msg.append(f"임대조건 읽기 실패 {e.__class__.__name__}")
    hl = next((f for f in rec["files"] if (f.get("name") or "").lower().endswith((".xlsx", ".xls")) and "목록" in (f.get("name") or "")), None)
    if hl:
        rec["house_list"] = {"name": hl["name"], "url": hl["url"]}
        cp = LIST_DIR / f"{nid}.csv"
        if not cp.exists() and hl["name"].lower().endswith(".xlsx"):
            data, m = _get(http, hl["url"], rec["url"])
            csv_text, m = xlsx_to_csv(data) if data else (None, m)
            if csv_text:
                LIST_DIR.mkdir(parents=True, exist_ok=True)
                cp.write_text(csv_text, encoding="utf-8")
            msg.append(m)
        elif cp.exists():
            msg.append("주택목록 저장본")
    return " · ".join(msg)


def main() -> int:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    log = [f"LH 주거복지·신혼희망 행복주택 수집 {now:%Y-%m-%d %H:%M}"]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not key:
        LOG.write_text("\n".join(log + ["DATA_GO_KR_KEY 없음 — 건너뜀"]) + "\n", encoding="utf-8")
        return 0
    scrub = lambda s: s.replace(key, "***")
    http = httpx.Client(timeout=httpx.Timeout(40, connect=10), follow_redirects=True, headers=UA)

    def api(url, **params):
        last = ""
        for attempt in range(3):
            try:
                r = http.get(url, params={"serviceKey": key, **params})
                return r.status_code, json.loads(r.text)
            except Exception as e:
                last = scrub(e.__class__.__name__)
                time.sleep(2 + attempt * 3)
        return 0, {"error": last}

    rows: list[dict] = []
    for up in WANT:
        for page in range(1, 6):
            st, j = api(LIST, PG_SZ=100, PAGE=page, UPP_AIS_TP_CD=up,
                        PAN_ST_DT=(now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d"), PAN_ED_DT=now.strftime("%Y%m%d"))
            got = [x for part in (j if isinstance(j, list) else [j]) if isinstance(part, dict)
                   for k, v in part.items() if isinstance(v, list) and k != "dsSch" and not k.endswith("Nm") for x in v if isinstance(x, dict) and x.get("PAN_ID")]
            log.append(f"[목록] 대분류 {up} {page}쪽 HTTP {st} · {len(got)}건")
            rows += got
            if len(got) < 100:
                break
    if not rows:
        log.append("[경고] 목록이 비어 있음 — 이전 파일을 그대로 둠")
        LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
        return 1
    seen, picks = set(), []
    for r in rows:
        if r["PAN_ID"] in seen:
            continue
        seen.add(r["PAN_ID"])
        if org_target(r.get("PAN_NM") or "") and r.get("UPP_AIS_TP_CD") in WANT:
            log.append(f"[목록·제외] 기관·기업 대상 공고(개인 신청 아님) {r['PAN_ID']} {(r.get('PAN_NM') or '')[:60]}")
        if keep(r, today):
            picks.append(r)
    picks = drop_superseded(picks, log)
    log.append("[목록] 전체 유형별 " + ", ".join(f"{k} {v}" for k, v in Counter(r.get("AIS_TP_CD_NM") for r in rows).most_common())
               + f" · 지금 공고 {len(picks)}건")
    notices = []
    for r in picks:
        p = {k: r.get(k) for k in ("PAN_ID", "CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")}
        st1, dtl = api(DTL, **p)
        st2, spl = api(SPL, **p)
        rec = record(r, dtl, spl)
        try:
            rd = read_notice(http, rec)   # 2026-10-22 운영자 '판정 미지원 공고문도 다 읽어오도록' — 화면 표시는 스위치 lh_welfare_read
        except Exception as e:   # 공고문 읽기가 실패해도 목록은 그대로
            rd = f"공고문 읽기 실패 {e.__class__.__name__}"
        sc = rec["schedule"]
        log.append(f"[공고] {rec['type']} {rec['id']} {(rec['name'] or '')[:50]} · 상세 {st1}/공급 {st2} · 일정 {len(sc)}"
                   + (f" 접수 {sc[0]['apply_start']}~{sc[0]['apply_end']}" if sc and sc[0]['apply_start'] else " 접수일 없음")
                   + f" · 단지 {len(rec['complexes'])} · 주택형 {len(rec['units'])} · 첨부 {len(rec['files'])} · {rd}")
        notices.append(rec)
        time.sleep(0.3)
    notices.sort(key=lambda n: (n["close"] or "9999", n["id"]))
    data = {"updated": now.strftime("%Y-%m-%d %H:%M"),
            "source": "LH 청약플러스 주거복지(매입임대·든든전세)·신혼희망타운 행복주택 공고 (공공데이터포털 한국토지주택공사 분양임대공고 조회)",
            "count": len(notices), "notices": notices}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log.append("[요약] 유형별 " + ", ".join(f"{k} {v}" for k, v in Counter(n["type"] for n in notices).most_common()))
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
