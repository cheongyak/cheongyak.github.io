"""한글 HWPX 공고문 → 글 (2026-10-22 운영자 '판정 미지원 공고문도 다 읽어오도록').

SH 공고 일부는 공고문이 PDF 없이 .hwpx 로만 올라온다(SH-311349 은평구 은빛주택 '…모집 공고문.hwpx').
HWPX(OWPML, KS X 6101)는 zip 안의 Contents/section0.xml, section1.xml … 에 본문이 있고, 글자는 <hp:t> 에, 문단은 <hp:p> 다.
표 칸 안의 문단도 <hp:p> 라 문서 순서대로 걸으면서 <hp:t> 글자를 모으고 문단이 끝날 때 줄을 바꾼다(PDF 글처럼 한 줄 = 한 문단).
옛 .hwp(바이너리)는 읽지 않는다 — 실패하면 None 과 이유."""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

MAX_BYTES = 30_000_000


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def section_text(xml_bytes: bytes) -> str:
    out: list[str] = []
    line: list[str] = []
    for ev, el in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        name = _local(el.tag)
        if name == "t":
            line.append("".join(el.itertext()))
        elif name in ("tab",):
            pass
        elif name == "p":
            s = re.sub(r"[ \t ]+", " ", "".join(line)).strip()
            if s:
                out.append(s)
            line = []
            el.clear()
    return "\n".join(out)


def hwpx_to_text(data: bytes) -> tuple[Optional[str], str]:
    """HWPX 바이트 → (글, 기록용 문장). 글자가 500자 미만이면 못 읽은 것으로 본다(PDF 와 같은 기준)."""
    if not data or data[:2] != b"PK":
        return None, "HWPX 아님(zip 아님)"
    if len(data) > MAX_BYTES:
        return None, f"HWPX 너무 큼({len(data)}바이트)"
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        secs = sorted((n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)), key=lambda n: int(re.search(r"(\d+)", n).group(1)))
        if not secs:
            return None, "HWPX 본문(Contents/section*.xml) 없음"
        t = "\n".join(section_text(z.read(n)) for n in secs)
    except Exception as e:
        return None, f"HWPX 해석 실패 {e.__class__.__name__}"
    if len(t) < 500:
        return None, f"글자를 못 읽는 HWPX({len(t)}자)"
    return t, f"HWPX 읽음 {len(t)}자"
