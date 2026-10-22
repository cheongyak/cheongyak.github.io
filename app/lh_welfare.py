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
import time
from collections import Counter
from datetime import datetime, timedelta

import httpx

from app.lh_rental import DTL, KST, LIST, ROOT, SPL, UA, _d, notice_record, org_target

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


def record(row: dict, dtl, spl) -> dict:
    rec = notice_record(row, dtl, spl)
    rec.update({"type": kind_of(row), "type_api": row.get("AIS_TP_CD_NM"), "upper": row.get("UPP_AIS_TP_NM"),
                "judge_type": False, "welfare": True, "rents": [], "terms": None})
    return rec


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
    log.append("[목록] 전체 유형별 " + ", ".join(f"{k} {v}" for k, v in Counter(r.get("AIS_TP_CD_NM") for r in rows).most_common())
               + f" · 지금 공고 {len(picks)}건")
    notices = []
    for r in picks:
        p = {k: r.get(k) for k in ("PAN_ID", "CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")}
        st1, dtl = api(DTL, **p)
        st2, spl = api(SPL, **p)
        rec = record(r, dtl, spl)
        sc = rec["schedule"]
        log.append(f"[공고] {rec['type']} {rec['id']} {(rec['name'] or '')[:50]} · 상세 {st1}/공급 {st2} · 일정 {len(sc)}"
                   + (f" 접수 {sc[0]['apply_start']}~{sc[0]['apply_end']}" if sc and sc[0]['apply_start'] else " 접수일 없음")
                   + f" · 단지 {len(rec['complexes'])} · 주택형 {len(rec['units'])} · 첨부 {len(rec['files'])}")
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
