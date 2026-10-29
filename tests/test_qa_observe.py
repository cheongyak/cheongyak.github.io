"""새 검사 관찰 기간 (기능 qa_observe, 2026-10-22 '아직 남은 것' — 경고 원인 1위 '검사 도구·기대값 오류' 6/19번 12.5시간).
새 검사·기대값은 config.json qa_observe 로 먼저 돌려 결과만 보고(검증 현황 '관찰 중 검사'), 7일 넘게 실패 0 을 확인한 뒤 verify_status.GATED 로 옮긴다."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_every_check_is_gated_or_observed():
    """새 결과 파일을 tools/qa/stamp.DEPS 에 넣으면서 관찰 없이 바로 관문(GATED)에 걸 수 없다"""
    from tools.qa.stamp import DEPS
    from tools.verify_status import GATED
    observe = json.loads((ROOT / "docs" / "config.json").read_text(encoding="utf-8")).get("qa_observe") or {}
    loose = [k for k in DEPS if k not in GATED and k not in observe]
    assert not loose, f"관문에도 관찰에도 없는 검사 {loose} — config.json qa_observe 에 시작일과 함께 넣을 것"
    assert not (set(GATED) & set(observe)), "관찰 중이면서 관문에도 있는 검사"


def test_observed_failure_does_not_raise_warning(tmp_path, monkeypatch):
    from tools import verify_status as V
    d = {"fails": ["x"]}
    assert V.generic_bad(d) == 1 and V.generic_bad({"count": 3}) == 3 and V.generic_bad({"ok": True}) is None


def test_build_reports_observed_without_gating(monkeypatch):
    """관찰 중 검사의 실패는 ok·banner 를 바꾸지 않고 observe 에만 남는다"""
    from tools import verify_status as V
    from tools.qa import stamp
    qa = ROOT / "evidence" / "qa" / "verify-scope.json"
    old = qa.read_text(encoding="utf-8") if qa.exists() else None
    cfg = ROOT / "docs" / "config.json"
    cfg_old = cfg.read_text(encoding="utf-8")   # 관찰 중 검사가 없어도(10-30 모두 관문으로 옮김) 시험용으로 하나를 관찰 중으로 둔다
    c = json.loads(cfg_old); c["qa_observe"] = {"verify-scope.json": "2026-10-22"}
    try:
        cfg.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        qa.write_text(json.dumps({"date": "2026-10-22", "states": 4, "fails": ["listing"], "_data": stamp.want("verify-scope.json")}), encoding="utf-8")
        monkeypatch.setattr(stamp, "stamp_all", lambda: [])
        s = V.build()
        o = [x for x in s["observe"] if x["name"] == "verify-scope.json"]
        assert o and o[0]["fails"] == 1 and o[0]["state"] == "관찰 중"
        assert not any("경고 범위" in w for w in ((s.get("banner") or {}).get("why") or []))
    finally:
        cfg.write_text(cfg_old, encoding="utf-8")
        if old is None:
            qa.unlink(missing_ok=True)
        else:
            qa.write_text(old, encoding="utf-8")
