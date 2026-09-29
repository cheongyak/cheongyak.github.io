"""주소 문자열 → 지역 분류, 시군구, 법정동코드(LAWD_CD)."""
from __future__ import annotations

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
    return None


def lawd_of(sigungu: Optional[str]) -> Optional[str]:
    if not sigungu:
        return None
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
