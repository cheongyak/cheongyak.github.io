"""2026-11-11 밤 자동 개선: LH 제한사항 표의 거주의무 줄이 기준일 칸 '최초 입주가능일' 꼴이면 읽지 못해
실거주 의무가 '확인 필요'로 남던 것 (HANDOFF 107 '광교 527·528 거주의무 5년 — 표 글자 순서가 흐트러져 규칙이 못 읽음', AI 참고 내용만 붙어 있었음).
  2026000528 광교 공공분양 '거주의무 최초 입주가능일 년 5 주택법 제 조의 …'(PDF 글이 칸 순서를 섞음) · 본문 '최초 입주가능일부터 3년 이내에 입주 … 5년 동안 계속 거주'
정답 tests/golden/notices.json (원문 문장 직접 확인).
토지임대부(2026000373·041 — 90일 안 입주)·지분적립형(2026000527 — 거주의무기간 임대 금지)은 화면 전세 판단이 '3년 안 입주 → 전세 한 번 가능'만 알아서
기간을 채우면 틀린 안내가 된다 → 그 판단을 고치기 전까지 이 꼴로는 읽지 않고 '확인 필요'를 지킨다(다른 눈 검토)."""
import json
from pathlib import Path

import pytest

from app import notice_pdf
from app.models import Listing
from app.pipeline import apply_notice

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _text(nid):
    for d in ("evidence/notices", "evidence/qa/notices"):
        f = ROOT / d / f"{nid}.txt"
        if f.exists():
            return f.read_text(encoding="utf-8")
    pytest.skip(f"{nid} 원문 없음")


def test_gwanggyo_528_duty_from_first_movein_row():
    found = notice_pdf.parse_notice(_text("2026000528"))
    assert found.get("residence_duty") == 5 == GOLD["2026000528"]["fields"]["residence_duty"]
    assert "최초 입주가능일" in found["quotes"]["residence_duty"]
    assert not found.get("conflicts")


@pytest.mark.parametrize("nid", ["2026000373", "2026000041", "2026000527"])
def test_landlease_equity_stay_unknown(nid):
    """토지임대부·지분적립형은 아직 읽지 않음 — 화면이 '전세 한 번 가능'으로 잘못 안내하지 않게 '확인 필요' 유지."""
    assert notice_pdf.parse_notice(_text(nid)).get("residence_duty") is None


HEAD = "구분 기준일 (~로부터) 기간 관련법령 재당첨제한 당첨자 발표일 10년 「주택공급에 관한 규칙」 제54조 전매제한 당첨자 발표일 10년 「주택법」 제64조\n"


@pytest.mark.parametrize("row,want", [
    ("거주의무 최초 입주가능일 3년 「주택법」 제57조의2, 「주택법 시행령」 제60조의2", 3),
    ("거주의무 최초 입주가능일 년 2 주택법 제 조의 57 2", 2),
])
def test_row_forms(row, want):
    assert notice_pdf.parse_notice(HEAD + row).get("residence_duty") == want


@pytest.mark.parametrize("text", [
    "거주의무 최초 입주가능일 5년 「주택법」 제57조의2",                  # 같은 표의 재당첨제한 줄이 앞에 없음 — 표 줄인지 모름
    HEAD + "거주의무 최초 입주가능일 년 5 이내에 입주하여야 합니다",           # 바로 뒤에 관련 법령 이름이 없음
    HEAD + "최초 입주가능일 5년 「주택법」 제57조의2",                       # 거주의무 줄이 아님
    HEAD + "거주의무 최초 입주가능일 7년 「주택법」 제57조의2",                # 1~5년 밖
    HEAD + "거주의무 최초 입주가능일 년 5 공공주택 특별법 제 조의 49 5 「 」 ⑥",   # 지분적립형(공공주택 특별법)
    "토지임대부 분양주택 " + HEAD + "거주의무 최초 입주가능일 5년 「주택법」 제57조의2",   # 토지임대부
])
def test_not_read(text):
    assert notice_pdf.parse_notice(text).get("residence_duty") is None


def _apply(L, found, monkeypatch):
    monkeypatch.setattr(notice_pdf, "fetch_notice_text", lambda url, client=None: (None, "받기 생략(시험)", None))
    from app import pipeline
    monkeypatch.setattr(pipeline, "recheck_attachments", lambda cached, client=None, budget=60: {})
    cache = {L.id.split("-")[0]: {"found": found, "notice_pdf": "https://x/p.pdf", "v": pipeline.PARSER_VERSION}}
    apply_notice([L], [], previous={}, cache=cache)
    return L


def test_gwanggyo_listing_gets_duty(monkeypatch):
    """수도권 분양가상한제 공공분양(528) — 화면 실거주 의무가 '확인 필요'(None) 대신 5년."""
    found = notice_pdf.parse_notice(_text("2026000528"))
    L = Listing(id="2026000528-084.7637A", name="광교 자연앤 센트레빌(A17BL) 공공분양주택", address="경기도 수원시", region="경기",
                kind="공공분양", category="general", unit="84A", price=9.493, households=10, apply="2026-11-09",
                notice="2026-10-30", url="https://www.applyhome.co.kr/2026000528", capital=True, price_cap=True, residence_duty=None)
    L = _apply(L, found, monkeypatch)
    assert L.residence_duty == 5 and ("실거주 의무", "5년") in L.limits
