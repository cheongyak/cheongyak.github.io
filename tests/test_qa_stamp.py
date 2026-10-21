"""검사 결과 데이터 지문 (tools/qa/stamp.py, 2026-10-21 사용자 '이런 실수로 베타 참고용이 나오지 않도록 · 유사한 실수 점검').
지난 데이터로 돌린 검사 결과를 다른 워크플로의 검증 요약이 세지 않게, 그리고 그런 결과가 오래 남지 않게 하는 규칙을 고정한다."""
import re
from pathlib import Path

from tools.qa import stamp

ROOT = Path(__file__).resolve().parents[1]
WF = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / ".github/workflows").glob("*.yml")}


def test_every_result_read_by_status_has_deps():
    names = set(re.findall(r'qa\("([a-z0-9\-]+\.json)"\)', (ROOT / "tools/verify_status.py").read_text(encoding="utf-8")))
    assert names and names <= set(stamp.DEPS), names - set(stamp.DEPS)


def test_is_current_compares_only_its_deps():
    cur = {"listings": "a", "lh": "b", "sh": "c", "gh": "e", "pvt": "f", "code": "d"}
    assert stamp.is_current("lh-qa.json", {"_data": {"lh": "b", "sh": "c", "gh": "e", "pvt": "f", "code": "d"}}, cur)
    assert not stamp.is_current("lh-qa.json", {"_data": {"lh": "b", "sh": "OLD", "gh": "e", "pvt": "f", "code": "d"}}, cur)   # SH 를 다시 수집한 뒤의 옛 결과
    assert not stamp.is_current("input-nav.json", {"problems": []}, cur)                                  # 지문 없는 옛 결과
    assert stamp.is_current("invariants.json", {"_data": {"listings": "a"}}, dict(cur, code="changed"))   # 화면 코드와 상관없는 검사


def test_workflows_stamp_before_saving_results():
    """검사 결과를 저장하는 워크플로는 저장 전에 지문을 찍는다 (verify_status 가 찍거나 tools.qa.stamp)"""
    for name, t in WF.items():
        adds = [m.start() for m in re.finditer(r"git add[^\n]*evidence/qa/([a-z\-]+\.json)", t) if any(f"evidence/qa/{n}" in m.group(0) for n in stamp.DEPS)]
        if not adds:
            continue
        marks = [m.start() for m in re.finditer(r"tools\.verify_status|tools\.qa\.stamp", t)]
        assert marks and min(marks) < min(adds), name


def test_data_changing_workflows_rerun_verify():
    """검사를 다 돌리지 않고 데이터를 바꾸는 워크플로는 저장 뒤 판정 검증을 다시 돌린다"""
    for name in ("notice-retry.yml", "sh-rental.yml"):
        assert "verify.yml" in WF[name] and "actions: write" in WF[name], name
    assert "input_nav.cjs" in WF["collect.yml"]                    # 수집 데이터에 기대는 검사는 수집에서도 돈다
    assert "--full" in WF["verify.yml"]                            # 판정 검증 뒤에도 지난 결과가 남으면 실패


def test_saved_results_are_committed_where_produced():
    """돌린 검사 결과는 같은 실행에서 저장한다 (예전 pay-audit.json 은 어디서도 저장하지 않아 옛 파일이 남았다)"""
    for wf, names in (("collect.yml", ["pay-audit", "input-nav", "lh-unread"]), ("verify.yml", ["pay-audit", "input-nav", "lh-unread", "lh-qa"])):
        for n in names:
            assert f"evidence/qa/{n}.json" in WF[wf], (wf, n)
