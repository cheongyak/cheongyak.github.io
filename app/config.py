"""데이터를 가져오는 주소(URL)와 엔드포인트 설정.

기본값은 지금 쓰는 공공데이터포털 주소다. 주소를 바꿔야 하면 코드를 고치지 말고 환경변수로 덮어쓴다.
(GitHub Actions 에서는 워크플로의 env 또는 저장소 Variables 에 넣으면 된다.)

    APPLYHOME_BASE_URL      청약홈 분양정보 API 기본 주소
    APPLYHOME_PATH_<NAME>   청약홈 엔드포인트 경로 (NAME: GENERAL_DETAIL, GENERAL_MODEL, REMAINDER_DETAIL, ...)
    RTMS_BASE_URL           국토부 실거래가 API 기본 주소
    RTMS_PATH_<KIND>        실거래가 엔드포인트 경로 (KIND: TRADE, PRESALE, RENT)
    DATA_GO_KR_KEY          인증키 (두 API 공통)
"""
from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v or default


# ---- 청약홈 분양정보 (odcloud) ----
APPLYHOME_BASE_URL = _env("APPLYHOME_BASE_URL", "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1").rstrip("/")

# 카테고리 → (공고 개요 경로, 주택형별 경로)
APPLYHOME_ENDPOINTS = {
    "general": (_env("APPLYHOME_PATH_GENERAL_DETAIL", "/getAPTLttotPblancDetail"),
                _env("APPLYHOME_PATH_GENERAL_MODEL", "/getAPTLttotPblancMdl")),
    "remainder": (_env("APPLYHOME_PATH_REMAINDER_DETAIL", "/getRemndrLttotPblancDetail"),
                  _env("APPLYHOME_PATH_REMAINDER_MODEL", "/getRemndrLttotPblancMdl")),
}

# 아직 수집하지 않고 응답 필드만 확인하는 엔드포인트 (실행 기록에 키 목록을 남긴다)
APPLYHOME_PROBE_ENDPOINTS = {
    "오피스텔·도시형·민간임대": _env("APPLYHOME_PATH_URBTY_DETAIL", "/getUrbtyOfctlLttotPblancDetail"),
    "공공지원 민간임대": _env("APPLYHOME_PATH_PBLPVTRENT_DETAIL", "/getPblPvtRentLttotPblancDetail"),
    "임의공급": _env("APPLYHOME_PATH_OPT_DETAIL", "/getOPTLttotPblancDetail"),
}

# ---- 국토부 실거래가 ----
RTMS_BASE_URL = _env("RTMS_BASE_URL", "https://apis.data.go.kr/1613000").rstrip("/")
RTMS_ENDPOINTS = {
    "trade": _env("RTMS_PATH_TRADE", "/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"),        # 아파트 매매
    "presale": _env("RTMS_PATH_PRESALE", "/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade"),  # 분양권·입주권 전매
    "rent": _env("RTMS_PATH_RENT", "/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"),            # 전월세
}
