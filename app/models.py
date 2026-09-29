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
    sigungu: Optional[str] = None            # "광진구", "성남시 분당구" 등
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
    jeonse: Optional[float] = None           # 예상 전세 보증금 (억)
    jeonse_note: str = ""

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
    url: Optional[str] = None
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
