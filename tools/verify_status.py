"""검증 결과 모으기 (기능: verify_status) → docs/verify-status.json

수집 실행 기록(docs/run-log.txt)의 공고문 대조·정답 데이터 결과와 판정 검증 사례 결과(docs/judge-status.json)를 한 파일로 모은다.
화면(이용 안내·베타 상자)이 이 파일로 마지막 검증 결과를 보여주고, 하나라도 다르면 종료 코드 1 → Actions 가 실패로 표시되고 이슈 알림.
실행: python -m tools.verify_status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def build() -> dict:
    log = (DOCS / "run-log.txt").read_text(encoding="utf-8").splitlines() if (DOCS / "run-log.txt").exists() else []
    judge = json.loads((DOCS / "judge-status.json").read_text(encoding="utf-8")) if (DOCS / "judge-status.json").exists() else None
    cc_sum = next((l for l in log if l.startswith("[검증·공고문] ")), None)
    cc_bad = [l for l in log if l.startswith("[검증·공고문 불일치]")]
    gold_bad = [l for l in log if l.startswith("[검증·정답 불일치]")]
    run_at = next((l.split("실행: ")[1] for l in log if l.startswith("실행: ")), None)
    try:
        cc_on = json.loads((DOCS / "config.json").read_text(encoding="utf-8")).get("features", {}).get("notice_crosscheck", True)
    except Exception:
        cc_on = True
    # MASTER QA 검사 (기능 qa_gate, 2026-10-02): 공급유형 표시 전수(tools/qa/supply_type.cjs)·데이터 불변식(tools/qa/invariants.py). 끄면 결과만 남고 통과 여부에 넣지 않는다
    try:
        gate = json.loads((DOCS / "config.json").read_text(encoding="utf-8")).get("features", {}).get("qa_gate", True)
    except Exception:
        gate = True
    def qa(name):
        f = ROOT / "evidence" / "qa" / name
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    st, inv, flt, con, spt, mkc, crx, pkp, mono, snap, e2e = qa("supply-type.json"), qa("invariants.json"), qa("filter-check.json"), qa("consistency.json"), qa("sp-text.json"), qa("market-check.json"), qa("cross-rule.json"), qa("profile-keep.json"), qa("monotonic.json"), qa("snapshot.json"), qa("e2e.json")
    pch = qa("past-chat.json")
    lhi, lhq, lhs = qa("lh-invariants.json"), qa("lh-qa.json"), qa("lh-screen.json")   # LH 임대 (기능 lh_rental, 2026-10-05): 데이터 불변식·정답 대조 / 판정 퍼징·단조성·답하기 / 화면
    lhi_bad = lhi["count"] if lhi else None
    lhq_bad = (len(lhq["fuzzBad"]) + len(lhq["monoBad"]) + len(lhq["loopBad"]) + len(lhq["cardBad"]) + len(lhq.get("pageErrors") or [])) if lhq else None
    lhs_bad = len(lhs["fails"]) if lhs else None
    lhp = qa("lh-pdf-tools.json")   # LH 공고문 여러 도구 읽기 (기능 lh_pdf_multi): 합친 값이 정답과 다른 칸 수
    lhp_bad = lhp["merged_wrong"] if lhp else None
    st_bad = len(st["fails"]) if st else None
    inv_bad = sum(v["count"] for s in ("live", "archive") for v in inv[s]["violations"].values()) if inv else None
    flt_bad = (flt["filter_fails"] + len(flt["search_fails"])) if flt else None
    con_bad = (con["fails"] + len(con.get("pageErrors") or [])) if con else None   # 카드·상세·필터 판정 일치 (2026-10-02 과천 84D)
    spt_bad = (spt["fails"] + len(spt.get("pageErrors") or [])) if spt else None   # 특별공급 칸 뽑는 방식·단계 세대수 문구 (2026-10-02)
    mkc_bad = mkc["fails"] if mkc else None   # 시세·근거 거래 ↔ 국토부 실거래가 원자료 (tools/qa/market_check.py, 2026-10-02)
    crx_bad = (crx["severity"]["CRITICAL"] + crx["severity"]["HIGH"] + len(crx.get("pageErrors") or [])) if crx else None   # 교차 규칙 CRITICAL·HIGH (evidence/qa/CROSS_RULES.md, 2026-10-02)
    pkp_bad = (pkp["fails"] + len(pkp.get("pageErrors") or [])) if pkp else None   # 저장한 내 조건 유지 (2026-10-02 납입 인정 회차 제보)
    mono_bad = (mono["violations"] + len(mono.get("pageErrors") or [])) if mono else None   # 정보·값 단조성 (확인 필요 → 가능, 경계값, 2026-10-02)
    snap_bad = snap["diffs"] if snap else None   # 화면 글자 스냅샷 (일부러 바꾸면 tools/qa/snapshot.cjs --update)
    e2e_bad = e2e["fail"] if e2e else None       # 사용자 흐름·퍼징
    pch_bad = (pch["violations"] + len(pch.get("pageErrors") or [])) if pch else None   # 지난 공고 판정 줄·청약봇 판정 요약 ↔ 화면 (tools/qa/past_chat.cjs, 2026-10-02)
    qa_ok = not gate or (st_bad == 0 and inv_bad == 0 and flt_bad in (0, None) and con_bad in (0, None) and spt_bad in (0, None) and mkc_bad in (0, None) and crx_bad in (0, None) and pkp_bad in (0, None) and mono_bad in (0, None) and snap_bad in (0, None) and e2e_bad in (0, None) and pch_bad in (0, None) and lhi_bad in (0, None) and lhq_bad in (0, None) and lhs_bad in (0, None) and lhp_bad in (0, None))   # 필터 검사는 결과 파일이 있을 때만 (2026-10-02 추가)
    ok = bool(judge) and not judge["failed"] and not judge.get("pageErrors") and not cc_bad and not gold_bad and (cc_sum is not None or not cc_on) and qa_ok
    kst = timezone(timedelta(hours=9))
    return {"at": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "ok": ok, "collect_run": run_at,
            "judge": {"total": judge["total"], "passed": judge["passed"], "failed": [f["id"] for f in judge["failed"]]} if judge else None,
            "crosscheck": {"summary": cc_sum, "mismatches": cc_bad[:30]}, "golden": {"mismatches": gold_bad[:30]},
            "qa": {"gate": gate, "supply_type_fails": st_bad, "invariant_violations": inv_bad, "filter_fails": flt_bad, "consistency_fails": con_bad, "sp_text_fails": spt_bad, "market_fails": mkc_bad, "cross_rule_fails": crx_bad, "profile_keep_fails": pkp_bad, "monotonic_violations": mono_bad, "snapshot_diffs": snap_bad, "e2e_fails": e2e_bad, "past_chat_fails": pch_bad, "lh_invariant_violations": lhi_bad, "lh_judge_qa_fails": lhq_bad, "lh_screen_fails": lhs_bad, "lh_pdf_merged_wrong": lhp_bad, "lh_data_at": lhi and lhi.get("data_updated"), "cross_rule_checks": crx and crx.get("checks"), "market_at": mkc and mkc.get("date"), "supply_type_at": st and st.get("date"), "invariants_at": inv and inv.get("date")}}


if __name__ == "__main__":
    s = build()
    (DOCS / "verify-status.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[검증 요약] {'통과' if s['ok'] else '문제 있음'} · 판정 사례 {s['judge'] and s['judge']['passed']}/{s['judge'] and s['judge']['total']} · {s['crosscheck']['summary']} · 정답 불일치 {len(s['golden']['mismatches'])}건 · QA 공급유형 {s['qa']['supply_type_fails']} · 불변식 {s['qa']['invariant_violations']}")
    sys.exit(0 if s["ok"] else 1)
