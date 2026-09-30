"""주소 문자열 → 지역 분류, 시군구, 법정동코드(LAWD_CD)."""
from __future__ import annotations

import re
from typing import Optional

from . import rules as R

_GYEONGGI_CITIES_WITH_GU = {
    "수원시": ["장안구", "권선구", "팔달구", "영통구"],
    "성남시": ["수정구", "중원구", "분당구"],
    "안양시": ["만안구", "동안구"],
    "안산시": ["상록구", "단원구"],
    "고양시": ["덕양구", "일산동구", "일산서구"],
    "용인시": ["처인구", "기흥구", "수지구"],
}


# 주소 첫 단어 → 시·도 짧은 이름 (17개)
SIDO = {
    "서울": "서울", "서울특별시": "서울", "부산": "부산", "부산광역시": "부산", "대구": "대구", "대구광역시": "대구",
    "인천": "인천", "인천광역시": "인천", "광주": "광주", "광주광역시": "광주", "대전": "대전", "대전광역시": "대전",
    "울산": "울산", "울산광역시": "울산", "세종": "세종", "세종특별자치시": "세종", "경기": "경기", "경기도": "경기",
    "강원": "강원", "강원도": "강원", "강원특별자치도": "강원", "충북": "충북", "충청북도": "충북",
    "충남": "충남", "충청남도": "충남", "전북": "전북", "전라북도": "전북", "전북특별자치도": "전북",
    "전남": "전남", "전라남도": "전남", "경북": "경북", "경상북도": "경북", "경남": "경남", "경상남도": "경남",
    "제주": "제주", "제주도": "제주", "제주특별자치도": "제주",
}
SIDO_ORDER = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종",
              "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def main_address(address: str) -> str:
    """'광주연구개발특구 첨단3지구 A6블록(전남광주통합특별시 북구 월출동)'처럼 괄호 안에 행정 주소가 있으면 그것을 쓴다."""
    a = (address or "").strip()
    first = a.split(" ")[0] if a else ""
    if SIDO.get(first) or re.search(r"(특별시|광역시|특별자치시|특별자치도|도)$", first):
        return a
    for inner in re.findall(r"\(([^)]*)\)", a):
        f = inner.strip().split(" ")[0] if inner.strip() else ""
        if SIDO.get(f) or re.search(r"(특별시|광역시|특별자치시|특별자치도|도)$", f):
            return inner.strip()
    return a


def sido_of(address: str) -> Optional[str]:
    first = (address or "").strip().split(" ")[0] if address else ""
    return SIDO.get(first)


def sigungu_any(address: str) -> Optional[str]:
    """시·군·구 이름 (전국). 서울·경기·인천은 법정동코드 표와 같은 이름을 쓴다."""
    known = sigungu_of(address)
    if known:
        return known.replace("인천 ", "")
    parts = (address or "").split()
    if len(parts) < 2 or sido_of(address) == "세종":
        return None
    a = parts[1]
    if not a.endswith(("시", "군", "구")):
        return None
    if a.endswith("시") and len(parts) > 2 and parts[2].endswith("구"):
        return f"{a} {parts[2]}"
    return a


def region_of(address: str) -> str:
    a = address or ""
    if a.startswith("서울"):
        return "서울"
    if a.startswith("경기"):
        return "경기"
    if a.startswith("인천"):
        return "인천"
    return "지방"


def sigungu_of(address: str) -> Optional[str]:
    a = address or ""
    reg = region_of(a)
    if reg == "서울":
        for gu in R.SEOUL_LAWD:
            if f" {gu}" in a:
                return gu
        return None
    if reg == "경기":
        for key in R.GYEONGGI_LAWD:
            city = key.split(" ")[0]
            if city in a:
                gus = _GYEONGGI_CITIES_WITH_GU.get(city)
                if gus:
                    for gu in gus:
                        if gu in a:
                            return f"{city} {gu}"
                    return city  # 구 표기가 없으면 시까지만
                return city
    if reg == "인천":
        for gu in R.INCHEON_LAWD:
            if f" {gu}" in a:
                return f"인천 {gu}"
    return None


def lawd_of(sigungu: Optional[str]) -> Optional[str]:
    if not sigungu:
        return None
    if sigungu.startswith("인천 "):
        return R.INCHEON_LAWD.get(sigungu[3:])
    return R.SEOUL_LAWD.get(sigungu) or R.GYEONGGI_LAWD.get(sigungu)


def is_regulated(address: str) -> bool:
    reg = region_of(address)
    if reg == "서울":
        return True
    if reg == "경기":
        sg = sigungu_of(address)
        if sg in R.REGULATED_GYEONGGI:
            return True
        # 성남·수원은 지정된 3개 구가 시 전체라 시 이름만 있어도 규제지역
        return sg in ("성남시", "수원시") and not ("권선구" in address)
    return False


def is_capital(address: str) -> bool:
    return region_of(address) in ("서울", "경기", "인천")
