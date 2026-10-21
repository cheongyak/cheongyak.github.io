"""GH(경기주택도시공사) 임대 공고 수집 (app/gh_rental.py, 기능 gh_rental, 2026-10-21) — 게시판 목록 읽기·거르기.
evidence/qa/gh 의 목록 HTML 은 2026-10-21 tools/qa/gh_probe.py 가 GH 누리집에서 받은 것."""
from pathlib import Path

from app.gh_rental import SALE, SKIP, WANT, files_in, kind_of, rows_from

ROOT = Path(__file__).resolve().parents[1]


def _page():
    for f in sorted((ROOT / "evidence/qa/gh").glob("*.html")):
        t = f.read_text(encoding="utf-8")
        if "srCategoryId=12 ->" in t.splitlines()[0]:
            return t
    raise AssertionError("주택 분류 목록 HTML 없음")


def test_rows_and_filter():
    rows = {r["no"]: r for r in rows_from(_page())}
    assert rows["65277"]["title"].startswith("'26년 하반기 경기행복주택") and rows["65277"]["date"] == "2026-10-16"
    keep = lambda r: bool(WANT.search(r["title"]) and not SKIP.search(r["title"]) and not SALE.search(r["title"]))
    assert keep(rows["65277"]) and keep(rows["65116"])            # 경기행복주택 추가모집 · 기숙사 추가모집
    assert not keep(rows["65275"])                                 # 분양주택(민영주택) 임의공급 → 청약홈
    assert not keep(rows["65152"]) and not keep(rows["65135"])    # 예비입주자 발표·선정결과
    assert kind_of(rows["65277"]["title"]) == "행복주택"
    f = rows["65275"]["files"]
    assert f and f[0]["name"].endswith("입주자모집공고문.pdf") and "attachNo=83492" in f[0]["url"]


def test_files_in_alt_name():
    h = '<a href="?mode=download&amp;articleNo=1&amp;attachNo=2"> <img src="x.png" alt="GH 공고문.pdf - 다운로드"> </a>'
    assert files_in(h) == [{"name": "공고문.pdf", "url": "https://www.gh.or.kr/gh/announcement-of-salerental001.do?mode=download&articleNo=1&attachNo=2"}]
