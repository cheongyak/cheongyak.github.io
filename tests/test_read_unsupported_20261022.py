"""판정 미지원 공고의 공고문도 읽기 (2026-10-22 운영자 '판정미지원 공고문 확인으로 뜨는애들 공고문도 다 읽어오도록').
- SH: 공고문이 PDF 없이 한글 .hwpx 로만 올라온 공고(SH-311349 은빛주택) → app/hwpx_text
- LH 주거복지(매입임대·든든전세·신혼희망 행복주택): 공고문 PDF(못 읽으면 .hwpx)·주택목록 엑셀 → app/lh_welfare.read_notice"""
import io
import json
import zipfile

import httpx

from app.hwpx_text import hwpx_to_text, section_text

NS = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'


def _hwpx(sections: list[str]) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        for i, body in enumerate(sections):
            z.writestr(f"Contents/section{i}.xml", f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {NS}>{body}</hs:sec>')
    return b.getvalue()


def _p(*runs) -> str:
    return "<hp:p>" + "".join(f"<hp:run><hp:t>{r}</hp:t></hp:run>" for r in runs) + "</hp:p>"


def test_hwpx_paragraphs_tables_and_section_order():
    tbl = ("<hp:p><hp:run><hp:tbl><hp:tr><hp:tc><hp:subList>" + _p("청약접수") + "</hp:subList></hp:tc>"
           "<hp:tc><hp:subList>" + _p("2026.10.27 ~ 2026.10.29") + "</hp:subList></hp:tc></hp:tr></hp:tbl></hp:run></hp:p>")
    long = _p("은평구 홀몸어르신 은빛주택 ", "잔여세대 입주자 모집 공고") + tbl + _p("■ 신청자격 ", "만 65세 이상 무주택 홀몸어르신") + _p("가" * 600)
    t, m = hwpx_to_text(_hwpx([long, _p("두 번째 구역")]))
    lines = t.split("\n")
    assert lines[0] == "은평구 홀몸어르신 은빛주택 잔여세대 입주자 모집 공고"   # 한 문단의 여러 run 은 한 줄
    assert lines[1:3] == ["청약접수", "2026.10.27 ~ 2026.10.29"]              # 표 칸 문단은 칸마다 한 줄, 문서 순서대로
    assert "■ 신청자격 만 65세 이상 무주택 홀몸어르신" in lines and lines[-1] == "두 번째 구역"
    assert m.startswith("HWPX 읽음")


def test_hwpx_failures_are_reported_not_guessed():
    assert hwpx_to_text(b"%PDF-1.7")[0] is None                 # zip 아님
    assert hwpx_to_text(_hwpx([_p("짧음")]))[0] is None          # 500자 미만 = 못 읽음
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("mimetype", "x")
    assert "없음" in hwpx_to_text(b.getvalue())[1]
    assert section_text(f'<hs:sec {NS}></hs:sec>'.encode()) == ""


def test_sh_picks_hwpx_only_when_no_pdf():
    from app.sh_rental import pick_hwpx, pick_pdf
    files = [{"oriFileNm": "은빛주택 1호점 잔여세대 입주자 모집 공고문.hwpx"}]
    assert pick_pdf(files) is None and pick_hwpx(files)["oriFileNm"].endswith(".hwpx")
    files2 = [{"oriFileNm": "신청서 서식.hwpx"}, {"oriFileNm": "모집 공고문.hwpx"}]
    assert pick_hwpx(files2)["oriFileNm"] == "모집 공고문.hwpx"   # 서식보다 공고문


def test_xlsx_house_list_to_csv():
    from openpyxl import Workbook
    from app.lh_welfare import xlsx_to_csv
    wb = Workbook(); ws = wb.active
    ws.append(["연번", "주소", "전용면적", "임대보증금", "월임대료"]); ws.append([1, "김포시 …", 39.5, 30000000, 150000]); ws.append([None, None, None, None, None])
    b = io.BytesIO(); wb.save(b)
    t, m = xlsx_to_csv(b.getvalue())
    assert t.splitlines()[1].startswith("1,김포시") and m == "주택목록 2줄"   # 빈 줄은 뺌, 값은 그대로
    assert xlsx_to_csv(b"not xlsx")[0] is None


def test_lh_welfare_reads_hwpx_when_pdf_fails(tmp_path, monkeypatch):
    import app.lh_welfare as W
    monkeypatch.setattr(W, "TEXT_DIR", tmp_path / "lh")
    monkeypatch.setattr(W, "LIST_DIR", tmp_path / "lists")
    body = _p("청년 매입임대주택 예비입주자 모집공고") + _p("나" * 700)
    hx = _hwpx([body])

    def h(req):
        u = str(req.url)
        if u.endswith("pdf"):
            return httpx.Response(200, content=b"<html>not pdf</html>")
        if u.endswith("hwpx"):
            return httpx.Response(200, content=hx)
        return httpx.Response(404)
    http = httpx.Client(transport=httpx.MockTransport(h))
    rec = {"id": "T1", "type": "매입임대", "name": "청년 매입임대", "region": "경기도", "url": "https://x/view", "units": [], "rents": [],
           "notice_pdf": "https://x/pdf", "files": [{"kind": "공고문(hwp)", "name": "공고문.hwpx", "url": "https://x/hwpx"},
                                                     {"kind": "공고문(PDF)", "name": "공고문.pdf", "url": "https://x/pdf"}]}
    msg = W.read_notice(http, rec)
    assert "HWPX 읽음" in msg and rec["notice_text"] and (tmp_path / "lh" / "T1.txt").read_text(encoding="utf-8").startswith("청년 매입임대주택")
    assert rec["rents"] == []          # 임대조건 표가 없는 글이면 짐작해서 만들지 않음
    assert "house_list" not in rec     # 주택목록 첨부가 없으면 없음


def test_newlywed_happy_rents_with_suffix_types():
    """광주선운2 신혼희망타운 행복주택(2015122300020886) 원문 [금회모집 임대조건]: 55A-1·55B-1(주거약자) 신혼부부·한부모가족
    임대보증금 67,400천원 = 계약금 3,370 + 잔금 64,030, 월 342,610원 (A-1·A-3블록 같은 금액). 주택형 '-1' 을 떼지 않는다.
    칸이 합쳐진 다음 주택형(55B-1·55C-1)은 금액 줄이 따로 없어 짐작해서 만들지 않는다"""
    from pathlib import Path
    from app.lh_terms import parse_lh_rents
    t = (Path(__file__).resolve().parents[1] / "evidence/lh/2015122300020886.txt").read_text(encoding="utf-8", errors="replace")
    rows = parse_lh_rents(t, [])
    assert [(r["type"], r["group"], r["deposit"], r["rent"]) for r in rows] == [
        ("55A-1", "신혼부부·한부모", 67400000, 342610), ("55B-1", "신혼부부·한부모", 67400000, 342610)]
