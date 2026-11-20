"""무순위 전매제한 문장이 뒤섞인 꼴 '당첨자발표일 로부터 (2026.10.26.) 개월간 적용됩니다6 .' — 날짜가 '로부터' 뒤, 숫자가 문장 끝
(2026910298 한양립스 에듀포레 조합원 취소분, 2026-11-21 아침 자동 고치기 — 근거 자료로 들어온 새 원문이 '모든 저장 원문 전매제한' 시험을 깨뜨려 다음 수집이 멈출 상태였음).
1쪽 표 칸 '최초 당첨자발표일 로부터 개월(2026.10.26.) 6'과 날짜·단위·숫자가 맞을 때만 읽는다."""
import re
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[1]


def _flat(t):
    return re.sub(r"\s+", "", t)


def test_original_910298():
    r = notice_pdf.parse_resale(_flat((ROOT / "evidence/notices/2026910298.txt").read_text(encoding="utf-8")))
    assert (r["months"], r["base"], r["passed"]) == (6, "2026-10-26", False)


def test_table_disagree_not_read():
    t = _flat((ROOT / "evidence/notices/2026910298.txt").read_text(encoding="utf-8"))
    assert notice_pdf.parse_resale(t.replace("개월(2026.10.26.)6", "개월(2026.10.26.)3")) is None   # 표 숫자가 다르면 짐작하지 않음
    assert notice_pdf.parse_resale(t.replace("개월(2026.10.26.)6", "개월(2026.10.25.)6")) is None   # 날짜가 다르면 읽지 않음
