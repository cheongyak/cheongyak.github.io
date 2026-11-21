"""가점제·추첨제 비율 표 새 꼴 (2026-11-22 아침 자동 고치기 — 2026000521 더샵 천안라크원).
제목에서 '적용비율'이 빠지고 다음 표 제목이 글자마다 띄어 끼어든 꼴:
'전용면적별 순위 가점제 추첨제 - 1 / 가 점 산 정 기 준 주 택 공 급 에 관 한 규 칙 별 표 의 나 목 - ( 1 2 ) 「 」 구분 가점제 추첨제 …'"""
import json
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[1]
P = notice_pdf.parse_score_ratio
HEAD = "전용면적별 순위 가점제 추첨제 - 1 / 가 점 산 정 기 준 주 택 공 급 에 관 한 규 칙 별 표 의 나 목 - ( 1 2 ) 「 」 구분 가점제 추첨제 "


def test_golden_score_ratio_521():
    gold = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))["2026000521"]["fields"]["score_ratio"]
    text = (ROOT / "evidence/notices/2026000521.txt").read_text(encoding="utf-8")
    assert P(text) == gold
    o = notice_pdf.parse_notice(text)
    assert o["score_ratio"] == gold
    assert "전용면적 초과85㎡ - 100%" in o["quotes"]["score_ratio"]


def test_missing_title_form_short():
    t = HEAD + "전용면적 초과 이하60 85㎡ ㎡ 40% 60% 전용면적 초과85㎡ - 100% 가점항목 가점상한"
    assert P(t) == {"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60}, {"over": 85, "upto": None, "score": 0, "lottery": 100}]}


def test_missing_title_form_rejects_bad_numbers():
    assert P(HEAD + "전용면적 초과 이하60 85㎡ ㎡ 40% 50% 가점항목") == {"unknown": True}             # 합이 100 이 아니면 읽지 않음
    assert P(HEAD + "전용면적 이하60㎡ 40% 60% 전용면적 초과85㎡ - 100% 가점항목") == {"unknown": True}   # 60~85 줄이 빠져 면적이 안 이어지면 읽지 않음


def test_missing_title_needs_spaced_subtitle():
    # '- 1 /' 뒤에 띄어 쓴 '가 점 산 정 기 준' 제목이 없으면 이 꼴로 보지 않는다 (다른 글을 표로 오인하지 않게)
    assert P("전용면적별 순위 가점제 추첨제 - 1 / 구분 가점제 추첨제 전용면적 초과85㎡ - 100%") is None
