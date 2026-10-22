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


def test_switch_exists_and_screen_gated():
    """스위치가 config 에 있고(10-22 11시 운영자 '켜줘'로 켬), 화면은 스위치가 꺼지면 파일을 부르지도 않는다"""
    assert isinstance(json.loads((ROOT / "docs/config.json").read_text(encoding="utf-8"))["features"]["lh_welfare"], bool)
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "on('lh_welfare') ? fetch('lh-welfare.json'" in html   # 꺼져 있으면 파일을 부르지도 않는다


def test_workflow_step_is_optional_and_add_is_safe():
    t = (ROOT / ".github/workflows/lh-rental.yml").read_text(encoding="utf-8")
    step = t[t.index("python -m app.lh_welfare") - 200: t.index("python -m app.lh_welfare")]
    assert "continue-on-error: true" in step                       # 실패해도 LH 임대 수집은 그대로
    assert re.search(r'\[ -f "\$f" \] && git add "\$f"', t)          # 파일이 없을 때 git add 가 멈추지 않게


def test_correction_replaces_original():
    """정정 공고가 있으면 원 공고는 뺀다 — 2026-10-22 실제 쌍 3개 (운영자 '정정공고로 보여줘야지')"""
    from app.lh_welfare import drop_superseded
    rows = [{"PAN_ID": "0802", "PAN_NM": "[경기남부] 든든전세 매입임대주택 예비입주자 모집공고(비분양전환)"},
            {"PAN_ID": "0927", "PAN_NM": "[정정공고][경기남부] 든든전세 매입임대주택 예비입주자 모집공고(비분양전환)"},
            {"PAN_ID": "0901", "PAN_NM": "[경남지역본부]26년 4차 분양전환형 든든전세주택 예비입주자 모집 공고(모집권역 완화)"},
            {"PAN_ID": "0934", "PAN_NM": "[정정공고][경남지역본부]26년 4차 분양전환형 든든전세주택 예비입주자 모집 공고(모집권역 완화)"},
            {"PAN_ID": "0902", "PAN_NM": "[경남지역본부]26년 4차 비분양전환형 든든전세주택 입주자 모집 공고"},   # 비슷하지만 다른 공고 — 그대로
            {"PAN_ID": "0731", "PAN_NM": "[온라인 접수 불가, 관할 주거복지지사 현장접수] 경기남부지역본부 2026년 일반 매입임대주택 입주자 모집공고"},
            {"PAN_ID": "0769", "PAN_NM": "[정정공고][온라인 접수 불가, 관할 주거복지지사 현장접수] 경기남부지역본부 2026년 일반 매입임대주택 입주자 모집공고"}]
    log = []
    assert [r["PAN_ID"] for r in drop_superseded(rows, log)] == ["0927", "0934", "0902", "0769"]
    assert len(log) == 3 and all(l.startswith("[목록·정정]") for l in log)
    # 정정 공고만 있고 원 공고가 없으면 그대로, 원 공고만 있으면 그대로
    assert [r["PAN_ID"] for r in drop_superseded(rows[1:2] + rows[4:5], [])] == ["0927", "0902"]
