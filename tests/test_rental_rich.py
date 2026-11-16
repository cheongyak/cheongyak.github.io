"""임대 정적 페이지 보강 (기능 rental_rich, 2026-11-17 운영자: 글이 짧은 임대 목록·상세에 모집 개요·자격 확인 항목).

수집 데이터에 있는 값만 쓰고(기준을 지어내지 않음), 스위치를 끄면 보강 전과 같다.
"""
from tools import seo_pages as sp

THIN = {"id": "GH-1", "org": "GH", "name": "시험 영구임대주택 예비입주자 모집 공고", "type": "영구임대", "region": "경기도", "posted": "2026-11-11", "close": "2026-11-25",
        "schedule": [{"apply_start": "2026-11-23", "apply_end": "2026-11-25"}], "units": [], "rents": [], "terms": None,
        "files": [{"kind": "PDF 공고문", "name": "모집공고문.pdf", "url": "https://example.org/a.pdf"}], "notice_text": 41289, "office": {"tel": "031-000-0000"}}
PVT = {"id": "PVT-1", "name": "시험 민간임대", "type": "공공지원 민간임대", "region": "경기도", "posted": "2026-11-05", "close": "2026-11-10", "schedule": [{"apply_start": "2026-11-10", "apply_end": "2026-11-10"}],
       "complexes": [{"name": "시험 민간임대", "address": "경기도 의정부시", "households": 909, "builder": "시험신탁"}],
       "units": [{"type": "49", "area": 49.95, "households": 115, "general": 0, "special": {"청년": 45, "신혼부부": 0, "고령자": 70}}, {"type": "59A", "area": 59.99, "households": 181, "general": 181, "special": {"청년": 0, "신혼부부": 0, "고령자": 0}}]}
AI = dict(THIN, id="SH-1", notice_ai={"groups": [{"name": "신혼부부", "items": [{"k": "income_pct", "label": "소득", "text": "120% 이하", "quote": "월평균 소득 120% 이하"}]}]})


def _on(monkeypatch, v):
    monkeypatch.setattr(sp, "feature", lambda name: v if name == "rental_rich" else True)


def test_detail_has_overview_and_checklist(monkeypatch):
    _on(monkeypatch, True)
    b = sp.rental_page("gh", THIN)[2]
    assert "모집 개요" in b and "GH(경기주택도시공사)" in b and "모집공고문.pdf" in b and "031-000-0000" in b and "41,289자" in b
    assert "신청 전에 공고문에서 확인할 것" in b and "자동으로 읽지 못했어요" in b
    assert b.index("모집 개요") < b.index(">일정<") if ">일정<" in b else True
    assert not sp.FORBID.search(b)
    # 기준 숫자를 지어내지 않는다 — 읽지 못한 공고에 소득 % · 자산 금액이 없다
    assert "% 이하" not in b and "만 원 이하" not in b


def test_pvt_special_supply_table(monkeypatch):
    _on(monkeypatch, True)
    b = sp.rental_page("pvt", PVT)[2]
    assert "청년 특별공급" in b and "일반공급은 모두 181세대, 청년 특별공급 45세대, 고령자 특별공급 70세대예요(청약홈 공고)" in b
    assert "청약 신청금" in b and "<td>사업 주체</td><td>시험신탁</td>" in b


def test_ai_reference_only_when_switch_on(monkeypatch):
    _on(monkeypatch, True)
    b = sp.rental_page("sh", AI)[2]
    assert "공고문에서 읽은 자격 기준 (참고)" in b and "120% 이하" in b and "판정에는 쓰지 않았어요" in b
    monkeypatch.setattr(sp, "feature", lambda name: name != "ai_read_sh")
    assert "120% 이하" not in sp.rental_page("sh", AI)[2]


def test_switch_off_is_as_before(monkeypatch):
    _on(monkeypatch, False)
    b = sp.rental_page("gh", THIN)[2]
    assert "모집 개요" not in b and "신청 전에 공고문에서 확인할 것" not in b
    assert sp.rent_list_extra("gh", [THIN], [("출처", "2026-11-16 10:27")]) == "" and sp.rent_open_list({"gh": [THIN]}) == ""


def test_list_extra_counts(monkeypatch):
    _on(monkeypatch, True)
    x = sp.rent_list_extra("gh", [THIN, dict(THIN, id="GH-2", type="국민임대")], [("GH 누리집", "2026-11-16 10:27")])
    assert "영구임대 1건" in x and "국민임대 1건" in x and "경기도 2건" in x and "마지막 수집 2026-11-16 10:27" in x and "유형별로 무엇이 다른가요" in x
    assert sp.rent_state(dict(THIN, schedule=[{"apply_start": "2000-01-01", "apply_end": "2000-01-02"}])) == "접수 마감"
    assert sp.rent_state({"schedule": [{"apply_start": "2999-01-01", "apply_end": "2999-01-02"}]}) == "접수 예정"
