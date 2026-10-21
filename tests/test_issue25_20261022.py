"""이슈 #25 (2026-10-22) 남은 경고 2건 — 원문: evidence/notices/2026000502.txt · 2026930044.txt"""
import re
from datetime import date
from pathlib import Path

from app.models import Listing
from app.notice_pdf import parse_resale, parse_score_ratio
from app.validate import listing_checks

ROOT = Path(__file__).resolve().parents[1]
HEAD_EST = "세대주 요건을 공고문에서 확인하지 못해 규제지역 기준으로 추정했어요"


def test_2026000502_score_ratio_with_complex_name_header():
    """'적용비율 1 /• 구분 화성 향남 롯데캐슬 시그니처약식표기 타입() 가점제 추첨제' — 단지명·약식표기 머리가 낀 표"""
    t = (ROOT / "evidence/notices/2026000502.txt").read_text(encoding="utf-8")
    assert parse_score_ratio(t) == {"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60},
                                             {"over": 85, "upto": None, "score": 0, "lottery": 100}]}


def test_2026000502_resale_with_date_between_unit_and_number():
    """'전매제한기간 당첨자 발표일 로부터 개월(2026.11.10.) 6' — 날짜는 기준일로, 2026910006 '년(2025.12.10.)1' 은 그대로"""
    r = parse_resale(re.sub(r"\s", "", (ROOT / "evidence/notices/2026000502.txt").read_text(encoding="utf-8")))
    assert (r["months"], r["base"]) == (6, "2026-11-10")
    r = parse_resale(re.sub(r"\s", "", (ROOT / "evidence/qa/notices/2026910006.txt").read_text(encoding="utf-8")))
    assert (r["months"], r["base"]) == (12, "2025-12-10")


def _unit(households, sp_total):
    return Listing(id="2026930044-066.8113", name="영흥숲", address="경기도 수원시", region="경기", sido="경기", kind="k", unit="66", area=66, price=5,
                   category="general", regulated=True, need_head=True, households=households,
                   special_units={"newlywed": sp_total, "total": sp_total} if sp_total else None)


def test_special_only_unit_has_no_general_head_estimate():
    """일반공급 0세대·특별공급만 있는 주택형은 일반공급 세대주 요건이 쓰이지 않으니 '추정' 경고를 붙이지 않는다"""
    assert HEAD_EST not in listing_checks(_unit(0, 1), date(2026, 10, 22))
    assert HEAD_EST in listing_checks(_unit(3, 1), date(2026, 10, 22))     # 일반공급이 있으면 그대로 경고
    assert HEAD_EST in listing_checks(_unit(0, 0), date(2026, 10, 22))     # 특공 세대수를 못 읽었으면(물량 모름) 그대로 경고


def test_probe_workflow_syncs_bot_copy():
    """근거 자료 모으기가 노선 자료(chat/v2/data)를 바꾸면 화면 복사본(docs/bot/v2)도 같이 올린다 — 안 그러면 다음 수집의 pytest 가 실패"""
    t = (ROOT / ".github/workflows/probe.yml").read_text(encoding="utf-8")
    assert "python -m tools.sync_bot" in t and "docs/bot/v2" in t
