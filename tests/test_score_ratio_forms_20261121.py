"""가점제·추첨제 비율 표 새 꼴 두 가지 (2026-11-21 아침 자동 고치기 — 근거 자료로 들어온 새 원문이 '모든 저장 원문 비율 표' 시험을 깨뜨려 다음 수집이 멈출 상태였음).
① 머리 '구분 타입(약식표기) 가점제 추첨제' (2026000591 소사 휴먼빌)
② 추첨제 칸 하나만 있는 표 '구분 추첨제 / 전용면적 85㎡ 초과 100%' (2026000596 고창 데시앙 2블록 민영) — 줄마다 100% 하나일 때만 가점 0%·추첨 100%"""
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[1]
P = notice_pdf.parse_score_ratio


def _t(no):
    return (ROOT / f"evidence/notices/{no}.txt").read_text(encoding="utf-8")


def test_type_header_591():
    assert P(_t("2026000591")) == {"rows": [{"over": 0, "upto": 60, "score": 40, "lottery": 60}, {"over": 60, "upto": 85, "score": 40, "lottery": 60}]}


def test_lottery_only_596():
    assert P(_t("2026000596")) == {"rows": [{"over": 85, "upto": None, "score": 0, "lottery": 100}]}


def test_lottery_only_not_100_is_unknown():
    t = "전용면적별 1순위 가점제/추첨제 적용비율 구분 추첨제 전용면적 85㎡ 초과 60% 공고 제"
    assert P(t) == {"unknown": True}   # 추첨제 칸 하나인데 100% 가 아니면 짐작하지 않음
