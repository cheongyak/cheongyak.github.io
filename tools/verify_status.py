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
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"




VERIFY_RUN = ("supply-type.json", "invariants.json", "filter-check.json", "consistency.json", "sp-text.json", "cross-rule.json", "profile-keep.json", "monotonic.json",
              "zero-default.json", "input-nav.json", "snapshot.json", "e2e.json", "past-chat.json", "verify-scope.json", "pay-audit.json")   # verify.yml 이 매번 만드는 결과


NAMES = {"invariants.json": "데이터 불변식", "lh-invariants.json": "임대 데이터 불변식", "lh-unread.json": "임대 공고문 못 읽음", "market-check.json": "시세 원자료 대조",
         "pay-audit.json": "계약금 비율 대조", "parse-moved.json": "다시 받은 공고문 값 변화", "coverage.json": "공고 누락 점검", "supply-type.json": "공급유형 표시",
         "filter-check.json": "필터", "consistency.json": "카드·상세 일치", "sp-text.json": "특별공급 문구", "cross-rule.json": "교차 규칙", "profile-keep.json": "내 조건 유지",
         "monotonic.json": "단조성", "snapshot.json": "화면 스냅샷", "e2e.json": "사용자 흐름", "past-chat.json": "지난 공고·청약봇", "zero-default.json": "빈칸 기본값",
         "input-nav.json": "입력 버튼", "verify-scope.json": "경고 범위 화면", "lh-qa.json": "임대 판정", "lh-screen.json": "임대 화면", "lh-pdf-tools.json": "임대 공고문 여러 도구 읽기"}


# 관문에 걸린 검사 (2026-10-22 고정). 새 검사는 여기 바로 넣지 말고 config.json qa_observe {결과 파일: 시작일} 로 먼저 관찰하고,
# 7일 넘게 실패 0(거짓 경보 없음)을 확인한 뒤 qa_observe 에서 빼고 여기에 더한다 — tests/test_qa_observe.py 가 지킨다
GATED = ("supply-type.json", "invariants.json", "filter-check.json", "consistency.json", "sp-text.json", "market-check.json", "cross-rule.json",
         "profile-keep.json", "monotonic.json", "snapshot.json", "e2e.json", "past-chat.json", "pay-audit.json", "parse-moved.json", "coverage.json",
         "zero-default.json", "input-nav.json", "lh-invariants.json", "lh-qa.json", "lh-screen.json", "lh-unread.json", "lh-pdf-tools.json")


def generic_bad(d: dict) -> Optional[int]:
    """관찰 중 검사의 실패 수 (검사마다 결과 모양이 달라 흔한 칸을 차례로 본다)"""
    for k in ("fails", "bad", "count", "violations", "diffs", "fail", "problems", "missing", "merged_wrong", "changed"):
        v = d.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            return v
        if isinstance(v, (list, dict)):
            return len(v)
    return None


def _viol_rows(d, parts) -> list:
    """불변식 결과 {part: {violations: {이름: {count, ids}}}} → [(id, 이름)]. ids 가 없는 옛 결과는 (None, 이름) — 어느 공고인지 모름"""
    out = []
    for s in parts:
        for k, v in (((d or {}).get(s) or {}).get("violations") or {}).items():
            out += [(i, k) for i in v["ids"]] if v.get("ids") else [(None, k)] * max(1, v.get("count") or 0)
    return out


def scope(*, gate, judge, cc_bad, gold_bad, cc_missing, full_stale, stale, system, notice, listing, coverage) -> dict:
    """경고 범위 나누기 (기능 verify_scope, 2026-10-22 경고 이력 분석 — evidence/qa/warn-history.json).
    ok(Actions 실패·이슈)는 그대로 두고, 화면이 쓸 상태만 나눈다:
      banner   — 모든 판정에 영향이 있어 사이트 전체에 알릴 것: 공고문 대조·정답 데이터 불일치('notice'), 판정·화면 검사 실패('judge'), 검증을 끝내지 못함('unverified')
      flagged  — 특정 공고에만 해당: {공고·주택형 id: [이유]} → 그 공고 화면 '데이터 확인 필요'. 어느 공고인지 모르는 실패가 하나라도 섞이면 숨기지 않고 banner 로 올린다
      pending  — 지금 데이터·코드로 아직 다시 돌리지 않은 검사(지난 결과): 통과로 치지 않고 '재검증 대기'로 보여 준다
      coverage_missing — 청약홈에 열려 있는데 화면에 없는 공고 수(값이 틀린 것이 아니라 빠진 것, 검증 현황에 표시)"""
    kinds, why = [], []
    if not judge:
        kinds.append("unverified"); why.append("판정 검증 결과 없음")
    if cc_missing:
        kinds.append("unverified"); why.append("공고문 대조를 돌리지 못함")
    if full_stale:
        kinds.append("unverified"); why.append("다시 돌리지 못한 검사 " + " ".join(full_stale))
    if cc_bad or gold_bad:
        kinds.append("notice"); why.append(f"공고문 대조 {len(cc_bad)}건 · 정답 데이터 {len(gold_bad)}건 다름")
    if judge and (judge["failed"] or judge.get("pageErrors")):
        kinds.append("judge"); why.append(f"판정 사례 {len(judge['failed'])}건 다름")
    flagged = {}
    if gate:
        for k, v in notice.items():
            if v:
                kinds.append("notice"); why.append(f"{k} {v}건")
        for k, v in system.items():
            if v:
                kinds.append("judge"); why.append(f"{k} {v}건")
        for f, (n, rows) in listing.items():
            if not n:
                continue
            ids = [(str(i).strip(), r) for i, r in rows if i]
            if not ids or len(ids) < len(rows):
                kinds.append("notice"); why.append(f"{NAMES.get(f, f)} {n}건 (어느 공고인지 모름)")
            for i, r in ids:
                t = f"자동 검증({NAMES.get(f, f)}): {r}"
                if t not in flagged.setdefault(i, []):
                    flagged[i].append(t)
    kind = next((k for k in ("notice", "judge", "unverified") if k in kinds), None)
    text = {"notice": "최근 자동 검증에서 공고문과 다른 값이 발견돼 확인 중이에요.",
            "judge": "최근 자동 검증에서 판정 계산이 기대와 달라 확인 중이에요.",
            "unverified": "최근 자동 검증을 끝까지 마치지 못해 확인 중이에요."}
    return {"banner": {"kind": kind, "text": text[kind], "why": why[:12]} if kind else None,
            "flagged": flagged, "pending": [NAMES.get(x, x) for x in stale], "coverage_missing": coverage or 0}


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
    # 검사 결과 도장 (tools/qa/stamp.py, 2026-10-21): 이번에 새로 쓴 결과에 지금 데이터 지문을 찍고,
    # 지문이 지금 데이터와 다른 결과(다른 워크플로가 예전 데이터로 돌린 것)는 '지난 결과'로 보고 통과·실패를 세지 않는다
    from tools.qa.stamp import current, is_current, stamp_all
    stamp_all()
    cur, stale = current(), []

    try:   # 관찰 중 검사 (기능 qa_observe, 2026-10-22): 결과는 남기되 ok·경고에 넣지 않는다 — 새 검사의 거짓 경보가 경고 원인 1위(6/19번)였다
        _c = json.loads((DOCS / "config.json").read_text(encoding="utf-8"))
        observe = (_c.get("qa_observe") or {}) if _c.get("features", {}).get("qa_observe", True) else {}   # 스위치를 끄면 관찰 중 검사도 바로 관문
    except Exception:
        observe = {}
    observed = []

    def qa(name):
        f = ROOT / "evidence" / "qa" / name
        if not f.exists():
            if name in observe:
                observed.append({"name": name, "label": NAMES.get(name, name), "since": observe[name], "fails": None, "state": "결과 없음"})
            return None
        d = json.loads(f.read_text(encoding="utf-8"))
        if not is_current(name, d, cur):
            stale.append(name)
            if name in observe:
                observed.append({"name": name, "label": NAMES.get(name, name), "since": observe[name], "fails": None, "state": "재검증 대기"})
            return None
        if name in observe:
            observed.append({"name": name, "label": NAMES.get(name, name), "since": observe[name], "fails": generic_bad(d), "state": "관찰 중"})
            return None
        return d
    st, inv, flt, con, spt, mkc, crx, pkp, mono, snap, e2e = qa("supply-type.json"), qa("invariants.json"), qa("filter-check.json"), qa("consistency.json"), qa("sp-text.json"), qa("market-check.json"), qa("cross-rule.json"), qa("profile-keep.json"), qa("monotonic.json"), qa("snapshot.json"), qa("e2e.json")
    pch = qa("past-chat.json")
    vsc = qa("verify-scope.json")   # 경고 범위 화면 (tools/qa/verify_scope.cjs, 기능 verify_scope 2026-10-22): 상태별 빨간 경고·공고 표시·검증 현황
    vsc_bad = len(vsc["fails"]) if vsc else None
    pay = qa("pay-audit.json")   # 계약금 비율 ↔ 공고문 금액 줄 독립 점검 (tools/qa/pay_audit.py, 2026-10-08 계약금 10% 고정 오류 뒤)
    pay_bad = pay["bad"] if pay else None
    pmv = qa("parse-moved.json")   # 다시 받아 글이 바뀐 공고문에서 읽은 값이 달라짐 (tools/qa/parse_snapshot --moved-json, 2026-10-10)
    pmv_bad = pmv["changed"] if pmv else None
    cov = qa("coverage.json")   # 청약홈 공고 누락 점검 (tools/qa/coverage.py, 2026-10-21): 열려 있는데 화면에 없는 공고 수
    cov_bad = len(cov["missing"]) if cov else None
    zd = qa("zero-default.json")   # 빈칸(기본값 0·아니요)을 값으로 본 판정 (tools/qa/zero_default.cjs, 2026-10-06 예치금 제보 뒤 전부 점검)
    zd_bad = (len(zd["violations"]) + len(zd.get("pageErrors") or [])) if zd else None
    inav = qa("input-nav.json")   # 입력 버튼이 판정을 바꾸는 칸으로 가는지 (tools/qa/input_nav.cjs, 2026-10-06)
    inav_bad = (len(inav["problems"]) + len(inav.get("pageErrors") or [])) if inav else None
    lhi, lhq, lhs = qa("lh-invariants.json"), qa("lh-qa.json"), qa("lh-screen.json")   # LH 임대 (기능 lh_rental, 2026-10-05): 데이터 불변식·정답 대조 / 판정 퍼징·단조성·답하기 / 화면
    lhi_bad = lhi["count"] if lhi else None
    lhq_bad = (len(lhq["fuzzBad"]) + len(lhq["monoBad"]) + len(lhq["loopBad"]) + len(lhq["cardBad"]) + len(lhq.get("pageErrors") or [])) if lhq else None
    lhs_bad = len(lhs["fails"]) if lhs else None
    lhu = qa("lh-unread.json")   # 임대 '공고문에서 못 읽음' 전수검사 (2026-10-20): 허용 목록 밖 항목 수
    lhu_bad = (lhu["bad"] + len(lhu.get("errs") or [])) if lhu else None
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
    qa_ok = not gate or ((st_bad == 0 or "supply-type.json" in stale) and (inv_bad == 0 or "invariants.json" in stale) and flt_bad in (0, None) and con_bad in (0, None) and spt_bad in (0, None) and mkc_bad in (0, None) and crx_bad in (0, None) and pkp_bad in (0, None) and mono_bad in (0, None) and zd_bad in (0, None) and inav_bad in (0, None) and snap_bad in (0, None) and e2e_bad in (0, None) and pch_bad in (0, None) and lhi_bad in (0, None) and lhq_bad in (0, None) and lhs_bad in (0, None) and lhu_bad in (0, None) and lhp_bad in (0, None) and pay_bad in (0, None) and pmv_bad in (0, None) and cov_bad in (0, None) and vsc_bad in (0, None))   # 필터 검사는 결과 파일이 있을 때만 (2026-10-02 추가)
    # --full (판정 검증 verify.yml): 그 실행이 모든 검사를 다시 돌리므로 지난 결과가 남으면(검사가 결과를 못 썼음) 실패. 수집에서만 도는 시세 대조·공고문 글 바뀜은 뺀다
    full_stale = [x for x in stale if x not in ("market-check.json", "parse-moved.json", "coverage.json")] if "--full" in sys.argv else []
    # --full: 판정 검증이 만들어야 하는 결과 파일이 아예 없으면 그 검사가 돌지 못한 것 — 없다고 통과로 치지 않는다 (2026-10-22 verify_scope.cjs 가 Actions 에서 멈춰 결과 없음)
    if "--full" in sys.argv:
        full_stale += [x for x in VERIFY_RUN if not (ROOT / "evidence" / "qa" / x).exists() and x not in full_stale]
    full_stale = [x for x in full_stale if x not in observe]   # 관찰 중 검사는 관문이 아님
    if full_stale:
        print(f"[검증·지난 결과] 판정 검증이 다시 돌렸는데도 지난 결과로 남은 검사: {' '.join(full_stale)} — 검사 실행 실패로 봄")
    if stale:
        print(f"[검증·지난 결과] 지금 데이터·화면 코드와 다른 때 돌린 검사 {len(stale)}개는 세지 않음(다음 판정 검증에서 다시 돌림): {' '.join(stale)}")
    ok = bool(judge) and not judge["failed"] and not judge.get("pageErrors") and not cc_bad and not gold_bad and (cc_sum is not None or not cc_on) and qa_ok and not full_stale
    sc = scope(gate=gate, judge=judge, cc_bad=cc_bad, gold_bad=gold_bad, cc_missing=cc_on and cc_sum is None, full_stale=full_stale, stale=stale,
               system={"공급유형 표시": st_bad, "필터": flt_bad, "카드·상세 일치": con_bad, "특별공급 문구": spt_bad, "교차 규칙": crx_bad,
                       "내 조건 유지": pkp_bad, "단조성": mono_bad, "빈칸 기본값": zd_bad, "입력 버튼": inav_bad, "화면 스냅샷": snap_bad, "사용자 흐름": e2e_bad,
                       "지난 공고·청약봇": pch_bad, "LH 판정": lhq_bad, "LH 화면": lhs_bad, "경고 범위 화면": vsc_bad},
               notice={"LH 공고문 여러 도구 읽기": lhp_bad},
               listing={"invariants.json": (inv_bad, _viol_rows(inv, ("live", "archive"))),
                        "lh-invariants.json": (lhi_bad, _viol_rows({"x": lhi} if lhi else None, ("x",))),
                        "lh-unread.json": (lhu_bad, [(r["id"], f"{r.get('group') or ''} {r['text']}".strip()) for r in ((lhu or {}).get("rows") or []) if not r.get("allowed")] + [(None, e) for e in ((lhu or {}).get("errs") or [])]),
                        "market-check.json": (mkc_bad, [(x["id"], "시세 근거가 국토부 실거래가 원자료와 다름") for x in ((mkc or {}).get("items") or []) if x.get("bad")]),
                        "pay-audit.json": (pay_bad, [(i, "계약금 비율이 공고문 금액 줄과 다름") for k in ("misread", "dominant") for i in (((pay or {}).get("flags") or {}).get(k) or [])]),
                        "parse-moved.json": (pmv_bad, [(str(x).split(" ")[0], "다시 받은 공고문에서 읽은 값이 달라짐") for x in ((pmv or {}).get("items") or [])])},
               coverage=cov_bad)
    kst = timezone(timedelta(hours=9))
    # 수집 멈춤 감시 (tools/qa/freshness.py, 2026-10-22 LH 임대 저장 실패로 이틀 멈춤): 분양·LH·SH 데이터 '마지막 갱신'이 26시간을 넘으면 경고.
    # 데이터가 틀린 게 아니라 오래된 것이라 ok 는 바꾸지 않고 warnings 로만 남긴다(지금 파일 시각으로 매번 계산 — 지난 결과가 될 일 없음)
    try:
        from tools.qa.freshness import check as fresh_check
        fresh = fresh_check(ROOT)
    except Exception as e:
        fresh = {"items": [], "warnings": [f"수집 멈춤 감시 실패 {e.__class__.__name__}"]}
    for w in fresh["warnings"]:
        print(f"[경고·수집 멈춤] {w}")
    for o in observed:
        print(f"[검증·관찰 중] {o['label']}({o['name']}) {o['state']} · 실패 {o['fails']} · {o['since']}부터 — ok·경고에 넣지 않음")
    return {"at": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "ok": ok, "collect_run": run_at, **sc, "observe": observed,
            "warnings": fresh["warnings"], "freshness": [{k: i[k] for k in ("name", "updated", "hours", "stale")} for i in fresh["items"]],
            "judge": {"total": judge["total"], "passed": judge["passed"], "failed": [f["id"] for f in judge["failed"]]} if judge else None,
            "crosscheck": {"summary": cc_sum, "mismatches": cc_bad[:30]}, "golden": {"mismatches": gold_bad[:30]},
            "qa_stale": stale, "qa": {"gate": gate, "supply_type_fails": st_bad, "invariant_violations": inv_bad, "filter_fails": flt_bad, "consistency_fails": con_bad, "sp_text_fails": spt_bad, "market_fails": mkc_bad, "cross_rule_fails": crx_bad, "profile_keep_fails": pkp_bad, "monotonic_violations": mono_bad, "zero_default_violations": zd_bad, "input_nav_problems": inav_bad, "snapshot_diffs": snap_bad, "e2e_fails": e2e_bad, "past_chat_fails": pch_bad, "lh_invariant_violations": lhi_bad, "lh_judge_qa_fails": lhq_bad, "lh_screen_fails": lhs_bad, "lh_unread": lhu_bad, "lh_pdf_merged_wrong": lhp_bad, "pay_audit_bad": pay_bad, "parse_moved_changes": pmv_bad, "coverage_missing": cov_bad, "verify_scope_fails": vsc_bad, "pay_audit_read": pay and f"{pay['read']}/{pay['notices']}", "lh_data_at": lhi and lhi.get("data_updated"), "cross_rule_checks": crx and crx.get("checks"), "market_at": mkc and mkc.get("date"), "supply_type_at": st and st.get("date"), "invariants_at": inv and inv.get("date")}}


if __name__ == "__main__":
    s = build()
    (DOCS / "verify-status.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[검증 요약] {'통과' if s['ok'] else '문제 있음'} · 판정 사례 {s['judge'] and s['judge']['passed']}/{s['judge'] and s['judge']['total']} · {s['crosscheck']['summary']} · 정답 불일치 {len(s['golden']['mismatches'])}건 · QA 공급유형 {s['qa']['supply_type_fails']} · 불변식 {s['qa']['invariant_violations']}")
    sys.exit(0 if s["ok"] else 1)
