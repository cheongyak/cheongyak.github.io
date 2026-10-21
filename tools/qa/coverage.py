"""청약홈 공고 누락 점검 (2026-10-21 사용자 '일반분양도 혹시 놓치는 공고 잇니?') → evidence/qa/coverage.json

수집(app/sources/applyhome.iter_open_listings)과 따로, 청약홈 분양정보 API 를 날짜 필터 없이 최신순으로 넓게(공고일 200일 전까지) 훑고
날짜 필터로도 한 번 더 받아 합친 뒤, '아직 접수 중이거나 당첨자 발표 후 14일이 안 지난' 공고가 화면 데이터(docs/listings.json)에 있는지 본다.
 - missing: 열려 있는데 화면에 없는 일반분양·무순위 공고 (공급 세대가 모두 0 이라 일부러 뺀 공고는 excluded 로 따로) → 검증 실패
 - uncollected: 아직 수집하지 않는 유형(임의공급·오피스텔·도시형·민간임대·공공지원 민간임대)에서 열려 있는 공고 수 (참고)
실행: python -m tools.qa.coverage  (DATA_GO_KR_KEY 필요 — Actions 수집에서 돈다)"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.sources.applyhome import KEEP_AFTER_WINNER_DAYS, ApplyhomeClient, pick, to_date, to_int  # noqa: E402

ENDS = {   # 이름 → (개요, 주택형) — 일반분양·무순위는 수집하는 것, 나머지는 아직 수집하지 않는 것
    "general": ("/getAPTLttotPblancDetail", "/getAPTLttotPblancMdl"),
    "remainder": ("/getRemndrLttotPblancDetail", "/getRemndrLttotPblancMdl"),
    "임의공급": ("/getOPTLttotPblancDetail", None),
    "오피스텔·도시형·민간임대": ("/getUrbtyOfctlLttotPblancDetail", None),
    "공공지원 민간임대": ("/getPblPvtRentLttotPblancDetail", None),
}
LOOKBACK = 200


def _is_open(d: dict, today: str) -> bool:
    end = to_date(pick(d, "apply_end")) or to_date(pick(d, "apply"))
    winner = to_date(pick(d, "winner"))
    keep = (date.fromisoformat(winner) + timedelta(days=KEEP_AFTER_WINNER_DAYS)).isoformat() if winner else end
    return bool(keep) and keep >= today


def sweep(c: ApplyhomeClient, path: str, since: str) -> dict:
    """같은 목록을 두 방법으로: ① 날짜 필터 없이 최신순 페이지를 since 보다 오래된 공고만 나올 때까지 ② 서버 날짜 필터. 합쳐서 관리번호별로."""
    out: dict = {}
    for page in range(1, 80):
        data = c._get(path, page=page).get("data", [])
        for d in data:
            out.setdefault(str(pick(d, "manage_no") or pick(d, "notice_no")), d)
        if len(data) < 100 or all((to_date(pick(d, "notice")) or "") < since for d in data):
            break
    try:
        for page in range(1, 40):
            data = c._get(path, page=page, **{"cond[RCRIT_PBLANC_DE::GTE]": since}).get("data", [])
            for d in data:
                out.setdefault(str(pick(d, "manage_no") or pick(d, "notice_no")), d)
            if len(data) < 100:
                break
    except Exception:
        pass
    return out


def main() -> int:
    today = date.today().isoformat()
    since = (date.today() - timedelta(days=LOOKBACK)).isoformat()
    c = ApplyhomeClient()
    listed = {str(x["id"]).split("-")[0] for x in json.loads((ROOT / "docs/listings.json").read_text(encoding="utf-8")) if not x.get("sample")}
    missing, excluded, uncollected, seen = [], [], {}, {}
    for name, (dpath, mpath) in ENDS.items():
        rows = sweep(c, dpath, since)
        opened = {no: d for no, d in rows.items() if no and _is_open(d, today)}
        seen[name] = {"swept": len(rows), "open": len(opened)}
        if mpath is None:
            uncollected[name] = [f"{no} {pick(d, 'name')} (공고 {to_date(pick(d, 'notice'))} · 접수 {to_date(pick(d, 'apply'))}~{to_date(pick(d, 'apply_end'))})" for no, d in sorted(opened.items())]
            continue
        for no, d in sorted(opened.items()):
            if no in listed:
                continue
            ms = c._get(mpath, **{"cond[PBLANC_NO::EQ]": no}).get("data", [])
            sup = sum((to_int(m.get("SUPLY_HSHLDCO")) or 0) + (to_int(m.get("SPSPLY_HSHLDCO")) or 0) for m in ms)
            line = f"{name} {no} {pick(d, 'name')} (공고 {to_date(pick(d, 'notice'))} · 접수 {to_date(pick(d, 'apply'))}~{to_date(pick(d, 'apply_end'))} · 주택형 {len(ms)}개)"
            (excluded if ms and sup == 0 else missing).append(line + (" — 공급 세대 0" if ms and sup == 0 else ""))
    res = {"date": today, "since": since, "seen": seen, "missing": missing, "excluded": excluded, "uncollected": uncollected}
    (ROOT / "evidence/qa").mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence/qa/coverage.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m in missing:
        print(f"[검증·공고 누락] {m}")
    for m in excluded:
        print(f"[공고 누락 점검·제외] {m}")
    for k, v in uncollected.items():
        print(f"[공고 누락 점검·미수집 유형] {k} 열린 공고 {len(v)}건" + (": " + " / ".join(v[:5]) if v else ""))
    print(f"[공고 누락 점검] 일반분양 {seen['general']['open']}건·무순위 {seen['remainder']['open']}건 열림 → 화면에 없음 {len(missing)}건 (공급 0 제외 {len(excluded)}건)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
