"""LH 주거복지(매입임대·든든전세)·신혼희망타운 행복주택 목록 (기능 lh_welfare, 2026-10-22 운영자 '넣어줘').
목록 원본: evidence/qa/lh/list-all.json (LH 원천 점검이 대분류 없이 받은 실제 응답, 2026-10-22)."""
import json
import re
from pathlib import Path

from app.lh_welfare import WANT, keep, kind_of, record

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "evidence/qa/lh/list-all.json").read_text(encoding="utf-8"))
TODAY = "2026-10-22"


def test_picks_only_welfare_and_newlywed_happy_open_notices():
    picks = [r for r in ROWS if keep(r, TODAY)]
    ids = {r["PAN_ID"] for r in picks}
    # 운영자가 짚은 공고들
    assert {"2015122300020923", "2015122300020934", "2015122300020900", "2015122300020886"} <= ids
    for r in picks:
        assert r["UPP_AIS_TP_CD"] in WANT and r["AIS_TP_CD_NM"] in WANT[r["UPP_AIS_TP_CD"]]
        assert r["PAN_SS"] != "접수마감"
    # 기존 '임대주택'(06)·상가·토지·공공분양 본 공고는 받지 않는다 (LH 임대 수집과 겹치지 않게)
    assert not any(r["UPP_AIS_TP_CD"] in ("06", "01", "22", "05") or r["AIS_TP_CD_NM"] == "공공분양(신혼희망)" for r in picks)
    # 마감·접수마감 공고는 뺀다
    assert "2015122300020929" not in ids   # 대구경북 든든전세(분양전환형) 정정 — 접수마감


def test_kind_and_list_only_record():
    r = next(x for x in ROWS if x["PAN_ID"] == "2015122300020923")
    assert kind_of(r) == "든든전세"
    rec = record(r, None, None)
    assert rec["judge_type"] is False and rec["welfare"] is True and rec["terms"] is None and rec["rents"] == []
    assert rec["type_api"] == "매입임대" and rec["upper"] == "주거복지"
    y = next(x for x in ROWS if x["PAN_ID"] == "2015122300020900")
    assert kind_of(y) == "매입임대" and "청년" in y["PAN_NM"]   # 화면 청년 주택 탭은 제목의 '청년'으로


def test_switch_off_by_default_and_screen_gated():
    assert json.loads((ROOT / "docs/config.json").read_text(encoding="utf-8"))["features"]["lh_welfare"] is False
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "on('lh_welfare') ? fetch('lh-welfare.json'" in html   # 꺼져 있으면 파일을 부르지도 않는다


def test_workflow_step_is_optional_and_add_is_safe():
    t = (ROOT / ".github/workflows/lh-rental.yml").read_text(encoding="utf-8")
    step = t[t.index("python -m app.lh_welfare") - 200: t.index("python -m app.lh_welfare")]
    assert "continue-on-error: true" in step                       # 실패해도 LH 임대 수집은 그대로
    assert re.search(r'\[ -f "\$f" \] && git add "\$f"', t)          # 파일이 없을 때 git add 가 멈추지 않게
