"""지방 공사 임대 (app/local_rental.py, 기능 local_rental, 2026-10-22) — 마이홈포털 API 실제 응답(evidence/qa/myhome-probe.json)으로."""
import json
import re
from datetime import date
from pathlib import Path

from app import local_rental as M

ROOT = Path(__file__).resolve().parent.parent


def _probe_rows():
    s = json.loads((ROOT / "evidence" / "qa" / "myhome-probe.json").read_text(encoding="utf-8"))["기본 JSON"]["body"]
    rows = []
    for m in re.finditer(r'\{\s*"pblancId".*?\n\s*\}', s, re.S):   # 저장본은 60,000자에서 잘려 있어 온전한 줄만
        try:
            rows.append(json.loads(m.group(0)))
        except Exception:
            pass
    return rows


def test_real_response_gwangju():
    """2026-10-22 실제 응답: 광주광역시도시공사 금호빛여울채 영구임대 — 접수 10-27~30, 발표 2027-02-17, 보증금 2,460,000원·월 48,900원, 200호"""
    rows = _probe_rows()
    assert rows, "응답 저장본 없음"
    notices, count = M.build(rows, date(2026, 10, 22))
    assert all(N["inst"] not in M.SKIP for N in notices) and count["LH·SH·GH 뺌"] > 0
    g = next(N for N in notices if N["inst"] == "광주광역시도시공사")
    assert g["id"] == "LOC-21443" and g["type"] == "영구임대" and g["org"] == "LOCAL" and g["judge_type"] is False
    assert g["schedule"][0]["apply_start"] == "2026-10-27" and g["schedule"][0]["apply_end"] == "2026-10-30" and g["schedule"][0]["winner"] == "2027-02-17"
    assert g["rents"][0]["deposit"] == 2460000 and g["rents"][0]["rent"] == 48900 and g["units"][0]["households"] == 200
    assert g["office"]["tel"] == "062-225-2280" and g["url"].startswith("https://www.gmcc.co.kr/")


def test_correction_replaces_old_and_old_notices_drop():
    base = {"suplyInsttNm": "인천도시공사", "suplyTyNm": "국민임대", "pblancNm": "x", "rcritPblancDe": "20261001", "beginDe": "20261020", "endDe": "20261025", "hsmpNm": "가", "rentGtn": 0, "mtRntchrg": None}
    rows = [dict(base, pblancId="1"), dict(base, pblancId="2", sttusNm="정정공고", beforePblancId="1"),
            dict(base, pblancId="3", rcritPblancDe="20260101", endDe="20260110")]
    notices, count = M.build(rows, date(2026, 10, 22))
    assert [N["id"] for N in notices] == ["LOC-2"] and count["정정 전 공고 뺌"] == 1 and count["지난 공고 뺌"] == 1
    assert notices[0]["rents"] == []      # 보증금 0·월세 없음 → 비움 (공고문 확인)
