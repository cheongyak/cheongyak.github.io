"""세대주 요건의 뜻 (2026-10-02 MASTER QA 원문 대조). need_head = 공급 전체의 신청 대상이 '무주택세대주'인가.
투기과열·청약과열의 '1순위 … 세대주일 것'(요약표 1순위 칸 '필요')은 1순위 요건이라 need_head 가 아니라 규제지역 규칙으로 판정한다
(need_head 로 읽으면 세대원을 2순위까지 '신청 불가'로 만든다 — 판정 사례 rank2-00·01·audit-051)."""
import pathlib
import re

from app import notice_pdf

ROOT = pathlib.Path(__file__).resolve().parent.parent


def text(no):
    f = ROOT / "evidence" / "notices" / f"{no}.txt"
    return (f if f.exists() else ROOT / "evidence" / "qa" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_regulated_first_rank_head_is_not_need_head():
    for no in ("2026000453", "2026000399", "2026000103", "2026000241"):
        t = text(no)
        assert re.search(r"세대주\s*요건\s*-\s*-\s*-\s*필요\s*필요\s*필요\s*필요\s*-", t), no   # 원문: 1순위 칸 '필요'
        assert notice_pdf.parse_notice(t)["need_head"] is False, no                        # 공급 전체 대상은 무주택세대구성원
