"""신청자격 제목 글자 사이 띄어쓰기 '3. 신 청 자 격 입주자 모집공고일(…) 현재 서울특별시에 거주하는 성년자인 무주택세대구성원'
(서울 영구임대 2015122300021109, 2026-11-20 아침 자동 고치기 — 규칙이 '신청자격'만 찾아 거주 요건을 못 읽고 느슨한 읽기로만 채워지던 것)."""
from pathlib import Path

from app.lh_terms import parse_lh_terms, parse_local, flat

ROOT = Path(__file__).resolve().parents[1]


def test_spaced_title_reads_local():
    t = flat("3. 신 청 자 격 \n입주자 모집공고일(2026.11.19.) 현재 서울특별시에 거주하는 성년자인 무주택세대구성원으로, 영구임대")
    loc = parse_local(t, "서울특별시")
    assert loc and (loc["name"], loc["sido"], loc["sigun"]) == ("서울특별시", "서울", None)


def test_unspaced_title_still_reads():
    loc = parse_local("신청자격 입주자 모집공고일(2026.11.19.) 현재 부산광역시에 거주하는 성년자인 무주택세대구성원", "부산광역시")
    assert loc and loc["sido"] == "부산"


def test_spaced_title_without_full_sentence_not_read():
    # '성년자인 무주택세대구성원'이 없으면 읽지 않는다(추측 금지) — 화면은 '확인'
    assert parse_local("신 청 자 격 입주자 모집공고일(2026.11.19.) 현재 서울특별시에 거주하는 사람", "서울특별시") is None


def test_original_21109():
    text = (ROOT / "evidence/lh/2015122300021109.txt").read_text(encoding="utf-8")
    r = parse_lh_terms(text, "영구임대", "2026년 서울특별시 영구임대주택 예비입주자 모집", "서울특별시")
    assert {k: r["local"][k] for k in ("name", "sido", "sigun")} == {"name": "서울특별시", "sido": "서울", "sigun": None}
    assert not r.get("local_unread")
