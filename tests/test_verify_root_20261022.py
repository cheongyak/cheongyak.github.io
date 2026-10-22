"""2026-10-22 '베타 참고용' 반복 원인 정리 — 경고 이력(evidence/qa/warn-history.json, tools/qa/warn_history.py)에서 확인한 구조적 원인별 회귀 시험."""
import json
import pathlib

from tools.qa import invariants

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _row(**k):
    base = {"id": "2026000001-084.0000A", "category": "general", "supply_type": "APT", "kind": "APT", "price": 5.0, "area": 84.0,
            "households": 10, "notice": "2026-09-01", "apply": "2026-09-10", "apply_end": "2026-09-12", "winner": "2026-09-20", "sido": "서울"}
    base.update(k)
    return base


def test_zero_fetch_keeps_only_rows_within_retention():
    """원인 (10-06 00:03·10-08 00:27 실제): 자정 수집이 청약홈에서 0건을 받아 지난 결과를 통째로 다시 씀 → 발표 후 14일 지난 공고가 화면에 남음
    → 불변식 위반 1·13건 → 전체 '베타 참고용'. 일부 유형만 0건일 때(restore_missing_category)는 이미 보관 기간을 걸렀는데 전부 0건일 때만 빠져 있었다."""
    from datetime import date
    from app.pipeline import keep_previous
    rows = [_row(id="a", winner="2026-09-20"), _row(id="b", winner="2026-09-25"), _row(id="c", winner=None, apply_end="2026-10-07")]
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 4))] == ["a", "b", "c"]    # 09-20+14 = 10-04 까지 보관
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 5))] == ["b", "c"]
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 8))] == ["b"]
    assert [x["id"] for x in keep_previous([{"id": "x", "name": "날짜 없음"}], date(2026, 10, 8))] == ["x"]   # 날짜를 모르면 빼지 않음 (test_pipeline 0건 시험)


def test_zero_fetch_replay_20261008():
    """그날 실제 데이터(커밋 489dac05 docs/listings.json)로: 그대로 두면 위반 13, 보관 기간을 거르면 0"""
    import subprocess
    from datetime import date
    from app.pipeline import keep_previous
    r = subprocess.run(["git", "show", "489dac05:docs/listings.json"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        import pytest
        pytest.skip("얕은 clone 이라 그날 커밋이 없음")
    rows = json.loads(r.stdout)
    rows = rows["listings"] if isinstance(rows, dict) else rows
    name = "보관 기간 지난 공고가 목록에 남음"
    assert invariants.check(rows, "2026-10-08", True)["violations"][name]["count"] == 13
    assert name not in invariants.check(keep_previous(rows, date(2026, 10, 8)), "2026-10-08", True)["violations"]


def test_violations_keep_every_id():
    """화면이 위반 공고 하나하나에 '데이터 확인 필요'를 붙이려면 예시 5개가 아니라 전부 필요 (verify_scope)"""
    rows = [_row(id=f"2026000{n:03d}-084.0000A", price=None) for n in range(8)]
    v = invariants.check(rows, "2026-09-01", True)["violations"]["금액 범위 (억)"]
    assert v["count"] == 8 and len(v["examples"]) == 5 and len(v["ids"]) == 8


# ---- 원인 D: 재공급 특별공급 세대수를 표 모양 하나에 기대 읽음 (읽기 규칙 26·30·31·44 — 3주에 5번 새 표 모양) ----
def _texts():
    import glob
    out = {}
    for f in sorted(glob.glob(str(ROOT / "evidence" / "notices" / "20269300*.txt")) + glob.glob(str(ROOT / "evidence" / "qa" / "notices" / "20269300*.txt"))):
        out.setdefault(pathlib.Path(f).stem, pathlib.Path(f).read_text(encoding="utf-8"))
    return out


def test_scale_sentence_agrees_with_table_on_every_saved_original():
    """공급규모 문장과 공급대상 표를 둘 다 읽은 원문은 유형별 특공 합이 모두 같아야 한다 (2026-10-22 기준 7건 모두 같음). 다르면 둘 중 하나를 잘못 읽은 것"""
    from app import notice_pdf
    both = 0
    for n, t in _texts().items():
        sc, st = notice_pdf.parse_resupply_scale(t), notice_pdf.parse_sp_table(t)
        if not (sc and st and sc["special_total"] is not None):
            continue
        sums = {}
        for row in st.values():
            for k, v in row.items():
                if k != "total" and v:
                    sums[k] = sums.get(k, 0) + v
        assert sum(sums.values()) == sc["special_total"], n
        if sc["special"]:
            assert sums == {k: v for k, v in sc["special"].items() if v}, n
        both += 1
    assert both >= 6


def test_scale_sentence_golden():
    """원문에서 직접 확인한 공급규모 문장 (2026-10-22): 영흥숲 '불법행위 재공급 1세대 [특별공급 1세대(신혼부부 1세대)]',
    장항 '불법행위재공급 6세대(노부모부양 특별공급 4세대, 일반공급 2세대)', 2026930040 '불법행위재공급 1세대[일반공급 1세대]'"""
    from app import notice_pdf
    T = _texts()
    g = lambda n: {k: v for k, v in notice_pdf.parse_resupply_scale(T[n]).items() if k != "quote"}
    assert g("2026930044") == {"total": 1, "special_total": 1, "special": {"newlywed": 1}, "general": None}
    assert g("2026930038") == {"total": 6, "special_total": 4, "special": {"elder": 4}, "general": 2}
    if "2026930040" in T:
        assert g("2026930040") == {"total": 1, "special_total": 0, "special": {}, "general": 1}


def test_scale_sentence_refuses_what_is_not_written():
    from app import notice_pdf
    p = notice_pdf.parse_resupply_scale
    assert p("■ 공급규모 : 총 307세대 중 불법행위재공급 1세대 및 부대복리시설")["special_total"] is None          # 내역 없음 → 모름
    assert p("■ 공급규모 : 총 772세대 중 불법행위재공급 3세대 [특별공급 1세대(노부모부양 1세대) 포함]")["general"] is None   # 일반 2세대는 적혀 있지 않음 → 짐작 안 함
    assert p("■ 공급규모 : 총 1세대 중 불법행위재공급 2세대 [특별공급 2세대(신혼부부 1세대)]") is None           # 유형 합 1 ≠ 특공 2 → 읽지 않음
    assert p("■ 공급규모 : 불법행위재공급 2세대 [특별공급 1세대, 일반공급 2세대]") is None                     # 1+2 ≠ 2
    assert p("공급규모 아파트 지하 층 지상 층 개동 총 세대 중 불법행위재공급 주택 세대 일반공급 세대 : 3 , 29 5 504 1 [ 1 ]") is None   # 숫자 떨어진 PDF 글 (2026930037)


def _L(id_, **k):
    from types import SimpleNamespace
    return SimpleNamespace(id=id_, category="remainder", notice_conflicts=[], special_units=None, from_notice=[], notice_quotes=None, **k)


def test_new_table_shape_falls_back_to_sentence():
    """신규 표 모양(읽기 규칙이 모르는 모양)이 와도: 영흥숲 원문에서 따로 표를 지우면 표는 못 읽지만 문장으로 신혼부부 1세대를 채운다 (주택형 하나)"""
    from app import notice_pdf
    from app.pipeline import resupply_scale
    t = _texts()["2026930044"]
    t2 = t[:t.index("■ 특별공급 공급세대수")] + t[t.index("■ 공급금액"):]
    found = notice_pdf.parse_notice(t2)
    assert "sp_table" not in found and found["supply_scale"]["special"] == {"newlywed": 1}
    L = _L("2026930044-066.8113 ")
    assert resupply_scale(L, found, [L]) == "문장으로 채움"
    assert L.special_units["newlywed"] == 1 and L.special_units["total"] == 1 and "특별공급 세대수 (재공급·공급규모 문장)" in L.from_notice


def test_sentence_does_not_guess_which_type_when_several():
    from app.pipeline import resupply_scale
    found = {"supply_scale": {"total": 3, "special_total": 3, "special": {"first": 3}, "general": None, "quote": "…"}}
    a, b = _L("2026930039-059.9901A"), _L("2026930039-074.8177A")
    assert resupply_scale(a, found, [a, b]) is None and a.special_units is None      # 탕정 2·1 을 문장만으로는 나눌 수 없음
    zero = {"supply_scale": {"total": 1, "special_total": 0, "special": {}, "general": 1, "quote": "…"}}
    assert resupply_scale(a, zero, [a, b]) == "문장으로 채움" and a.special_units["total"] == 0   # 특공 0 은 주택형이 여럿이어도 확정


def test_table_vs_sentence_mismatch_is_flagged_on_the_listing():
    """표와 문장이 다르면 그 주택형에 '데이터 확인 필요'(notice_conflicts → validate) — 조용히 한쪽을 고르지 않는다"""
    from app.pipeline import resupply_scale
    found = {"sp_table": {"084.9958A": {"elder": 3, "total": 3}, "084.9478B": {"elder": 2, "total": 2}},
             "supply_scale": {"total": 6, "special_total": 4, "special": {"elder": 4}, "general": 2, "quote": "…"}}
    a, b = _L("2026930038-084.9958A"), _L("2026930038-084.9478B")
    assert resupply_scale(a, found, [a, b]) == "대조 불일치" and "공급규모 문장 4세대" in a.notice_conflicts[0]
    found["sp_table"]["084.9478B"] = {"elder": 1, "total": 1}
    c = _L("2026930038-084.9958A")
    assert resupply_scale(c, found, [c, b]) == "대조 일치" and c.notice_conflicts == []


# ---- 원인 A: 공고 하나의 문제가 사이트 전체 '베타 참고용'이 되던 구조 (verify_status.ok 하나 = 검사 25가지의 AND) ----
def _scope(**k):
    from tools.verify_status import scope
    base = dict(gate=True, judge={"total": 1, "passed": 1, "failed": []}, cc_bad=[], gold_bad=[], cc_missing=False, full_stale=[], stale=[],
                system={}, notice={}, listing={}, coverage=0)
    base.update(k)
    return scope(**base)


def test_listing_problem_is_flagged_on_that_listing_not_site_wide():
    """10-22 06:18 실제: 영흥숲 한 주택형의 불변식 위반 → 245개 공고 전부에 '공고문과 다른 값' 경고. 이제 그 주택형에만"""
    s = _scope(listing={"invariants.json": (1, [("2026930044-066.8113", "재공급 일반 0세대인데 특공 세대수 없음")])})
    assert s["banner"] is None
    assert s["flagged"] == {"2026930044-066.8113": ["자동 검증(데이터 불변식): 재공급 일반 0세대인데 특공 세대수 없음"]}


def test_listing_problem_without_ids_is_not_hidden():
    """어느 공고인지 모르는 실패(옛 결과·도구 오류)는 숨기지 않고 사이트 전체에 알린다"""
    s = _scope(listing={"lh-unread.json": (2, [("2015122300020930", "못 읽음"), (None, "error x")])})
    assert s["banner"]["kind"] == "notice" and "어느 공고인지 모름" in " ".join(s["banner"]["why"])
    assert "2015122300020930" in s["flagged"]


def test_system_problems_keep_site_wide_banner_with_accurate_text():
    assert _scope(cc_bad=["[검증·공고문 불일치] x"])["banner"]["kind"] == "notice"          # 앱 기준표가 공고문과 다름 → 모든 판정
    assert _scope(gold_bad=["[검증·정답 불일치] x"])["banner"]["kind"] == "notice"
    j = _scope(judge={"total": 2, "passed": 1, "failed": [{"id": "c1"}]})["banner"]
    assert j["kind"] == "judge" and "판정 계산" in j["text"] and "공고문과 다른 값" not in j["text"]   # 예전엔 화면 검사 실패도 '공고문과 다른 값'이라고 했다
    assert _scope(system={"입력 버튼": 2})["banner"]["kind"] == "judge"


def test_unverified_is_not_treated_as_pass():
    """검증을 못 돌린 것은 통과가 아니다: 판정 결과 없음·공고문 대조 못 함 → 전체 경고('끝까지 마치지 못해'), 지난 결과 → 재검증 대기"""
    assert _scope(judge=None)["banner"]["kind"] == "unverified"
    assert _scope(cc_missing=True)["banner"]["kind"] == "unverified"
    s = _scope(stale=["market-check.json"])
    assert s["banner"] is None and s["pending"] == ["시세 원자료 대조"]


def test_gate_off_counts_nothing():
    assert _scope(gate=False, system={"입력 버튼": 2}, listing={"invariants.json": (1, [("x", "y")])}) == {"banner": None, "flagged": {}, "pending": [], "coverage_missing": 0}


def test_warn_history_scope_matches_verify_status_rules():
    """경고 이력 도구의 '지금 규칙이면' 나눔이 verify_status.scope 와 같은 기준인지"""
    from tools.qa.warn_history import scope_of
    assert scope_of(["invariant_violations:1", "lh_unread:4"]) == "공고별 표시"
    assert scope_of(["golden:3"]) == "전체·공고문 불일치"
    assert scope_of(["input_nav_problems:2"]) == "전체·판정 계산"
    assert scope_of(["crosscheck_none", "invariant_violations:13"]) == "전체·검증 미완료"
    assert scope_of(["cross_rule_fails:8", "lh_invariant_violations:3"]) == "전체·판정 계산"   # 화면 검사가 섞이면 전체


def test_verify_run_results_match_workflow_save_list():
    """판정 검증이 만들어야 하는 결과(VERIFY_RUN)는 verify.yml 이 저장하는 파일이어야 하고, 저장 단계는 없는 파일 때문에 통째로 실패하지 않아야 한다
    (2026-10-22 verify-scope.json 이 Actions 에서 안 만들어져 git add 가 실패 → 09:56 검증 결과가 '성공'인데 저장 안 됨)"""
    from tools.verify_status import VERIFY_RUN
    y = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    assert all(f"evidence/qa/{x}" in y for x in VERIFY_RUN)
    assert "git add -A -- $(keep " in y
    assert "existsSync('/opt/pw-browsers/chromium')" in (ROOT / "tools" / "qa" / "verify_scope.cjs").read_text(encoding="utf-8")
