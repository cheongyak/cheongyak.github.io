"""공고(Listing)와 사용자 조건(Profile) 데이터 구조.

금액 단위: Listing 은 억 원(float), Profile 은 만 원(int) — 사용자가 만 원 단위로 입력하기 때문.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Listing(BaseModel):
    id: str                                  # 공고번호 + 주택형 (예: "2026930040-084.9811C")
    name: str
    address: str
    region: Literal["서울", "경기", "인천", "지방"]
    sigungu: Optional[str] = None            # "광진구", "성남시 분당구" 등 (법정동코드 표 기준, 시세 조회용)
    sido: Optional[str] = None               # 시·도 (서울, 경기, 부산 ... 17개) — 주소에서 추출
    district: Optional[str] = None           # 시·군·구 (전국) — 주소에서 추출, 필터용
    supply_type: Optional[str] = None        # 청약홈 HOUSE_SECD_NM 원본 (APT, 무순위, 불법행위 재공급 ...)
    house_secd: Optional[str] = None         # 청약홈 HOUSE_SECD 원본 코드
    house_dtl: Optional[str] = None          # 청약홈 HOUSE_DTL_SECD_NM (있을 때만: 민영/국민 등)
    rent_secd: Optional[str] = None          # 청약홈 RENT_SECD_NM (있을 때만: 분양/임대)
    special_apply: Optional[str] = None      # 특별공급 접수 시작일 (있을 때만)
    special_apply_end: Optional[str] = None
    kind: str                                # "무순위 · 불법행위 재공급" 등
    category: Literal["general", "remainder"]
    target: Optional[str] = None             # 신혼부부 등 특정 대상 전용 공급
    unit: str                                # "84C" 등
    area: Optional[float] = None             # 전용면적 ㎡
    households: Optional[int] = None

    notice: Optional[str] = None             # 모집공고일 YYYY-MM-DD
    apply: Optional[str] = None              # 접수 시작일
    apply_end: Optional[str] = None
    winner: Optional[str] = None
    contract: Optional[str] = None
    balance: Optional[str] = None            # 잔금일(모르면 None)
    move_in: Optional[str] = None            # 입주예정월 YYYY-MM

    price: float                             # 분양가 (억)
    ext: float = 0.0                         # 발코니 확장 등 필수 추가비 (억)
    contract_rate: float = 0.10
    mid_rate: float = 0.0                    # 중도금 비율 (일반분양 보통 0.6, 준공 후 재공급은 0)

    mkt_low: Optional[float] = None          # 보수 시세 (억)
    mkt_base: Optional[float] = None         # 기준 시세 (억)
    mkt_note: str = ""
    mkt_basis: Optional[str] = None          # same_complex | district_newbuild | None
    mkt_count: int = 0                       # 시세 계산에 쓴 거래 수
    mkt_direct_excluded: int = 0             # 시세 계산에서 뺀 직거래 수
    mkt_comps: list[dict] = Field(default_factory=list)     # 근거 거래 (최근순 최대 8건, 국토부 실거래가)
    jeonse: Optional[float] = None           # 예상 전세 보증금 (억)
    jeonse_note: str = ""
    jeonse_comps: list[dict] = Field(default_factory=list)  # 근거 전세 거래

    capital: bool = True
    regulated: bool = True
    land_permit: bool = False
    price_cap: bool = False
    residence_duty: Optional[int] = 0        # 년. None 이면 공고문 확인 필요
    jeonse_weak: bool = False
    unregistered: bool = True                # 입주 직후 등기 전

    need_head: bool = True
    need_account: bool = False
    limits: list[tuple[str, str]] = Field(default_factory=list)
    url: Optional[str] = None                # 청약홈 공고 페이지
    notice_pdf: Optional[str] = None         # 입주자모집공고문 PDF (읽은 경우)
    from_notice: list[str] = Field(default_factory=list)    # 공고문에서 읽어 반영한 항목
    checks: list[str] = Field(default_factory=list)         # 자동 검증에서 걸린 항목 (화면에 '데이터 확인 필요'로 표시)
    geo: Optional[dict] = None               # 좌표 {lat, lng, precision: exact|dong, query, matched, source} (app/geo.py)
    account_months: Optional[int] = None     # 1순위 청약통장 가입기간(개월). 공고문에서 읽은 값, 못 읽으면 None (화면에서 지역 기준으로 추정)
    deposit_count: Optional[int] = None      # 국민주택·신혼희망타운 청약통장 납입 인정 횟수 기준(회). 공고문에서 읽은 값
    competition: Optional[dict] = None       # 청약홈 경쟁률·당첨가점 {rows:[{rank,reside,supply,req,rate,rate_num}], scores:[{reside,low,top,avg}]}
    area_comps: Optional[list[dict]] = None  # 신청 전 참고: 같은 시·군·구 최근 12개월 비슷한 면적 단지의 1순위 경쟁률·당첨가점
    map_query: Optional[str] = None          # 네이버 지도 검색어 (주소에서 '일원', 블록명 등을 뺀 것)
    nearby: Optional[list[dict]] = None      # 주변 역·학교 직선거리 [{kind, name, m, walk, lat, lng}] · None 이면 아직 조회 안 함
    sample: bool = False


class Profile(BaseModel):
    seoul: bool = True
    household: Literal["head", "parents", "spouse", "other"] = "parents"
    parents60: bool = False
    parentsOwn: bool = False
    headSince: str = ""
    selfOwn: bool = False
    married: bool = False
    spouseOwn: bool = False
    spouseIncome: int = 0
    spouseLoan: int = 0
    account: Literal["yes", "no", "unknown"] = "unknown"
    recentWin: bool = False
    cash: int = 0
    liquid: int = 0
    deposit: int = 0
    income: int = 0
    loanMonthly: int = 0
    firstTime: bool = True


class PlanOptions(BaseModel):
    mode: Optional[Literal["live", "jeonse"]] = None   # None 이면 전세 가능 여부로 자동 선택
    family: int = 0                                   # 가족 지원 (만 원)
    jeonse: Optional[int] = None                      # 사용자가 고친 전세 보증금 (만 원)
