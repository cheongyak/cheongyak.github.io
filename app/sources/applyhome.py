"""한국부동산원 청약홈 분양정보 조회 서비스 (공공데이터포털, odcloud).

- 공고 개요(*Detail)와 주택형별 분양가(*Mdl)가 다른 엔드포인트라 공고마다 두 번 호출한다.
- 일반분양(APT)과 무순위·잔여세대·불법행위 재공급(Remndr)은 접수일 필드명이 다르다.
- 필드명은 공개 구현체와 문서로 확인한 값이다. 처음 연결할 때 `python -m app.inspect_fields` 로
  실제 응답의 키를 꼭 확인하고, 다르면 아래 FIELD 후보 목록에 추가한다.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional

import httpx

from .. import config

# 주소는 app/config.py 에서 관리한다 (환경변수로 바꿀 수 있음). 아래 이름은 기존 코드 호환용.
BASE = config.APPLYHOME_BASE_URL
ENDPOINTS = config.APPLYHOME_ENDPOINTS

# 표준 필드 → 응답에서 찾아볼 후보 키 (앞에서부터)
FIELD = {
    "notice_no": ["PBLANC_NO"],
    "manage_no": ["HOUSE_MANAGE_NO"],
    "name": ["HOUSE_NM"],
    "address": ["HSSPLY_ADRES"],
    "kind": ["HOUSE_SECD_NM", "HOUSE_DTL_SECD_NM"],
    "notice": ["RCRIT_PBLANC_DE"],
    "apply": ["RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE", "GNRL_RNK1_CRSPAREA_RCPTDE"],
    "apply_end": ["RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE"],
    "winner": ["PRZWNER_PRESNATN_DE"],
    "contract": ["CNTRCT_CNCLS_BGNDE"],
    "contract_end": ["CNTRCT_CNCLS_ENDDE"],
    "total_households": ["TOT_SUPLY_HSHLDCO"],
    "area_name": ["SUBSCRPT_AREA_CODE_NM"],        # 공급지역 (서울/경기/...)
    "move_in": ["MVN_PREARNGE_YM"],
    "url": ["PBLANC_URL", "HMPG_ADRES"],
    "house_secd": ["HOUSE_SECD"],                   # 주택구분 코드 (예: "04" 무순위)
    "house_dtl": ["HOUSE_DTL_SECD_NM"],             # 주택상세구분 (민영/국민 등, 일반분양 개요에 있을 때만)
    "rent_secd": ["RENT_SECD_NM"],                  # 분양/임대 구분 (있을 때만)
    "special_apply": ["SPSPLY_RCEPT_BGNDE"],        # 특별공급 접수 시작 (2026-09-29 무순위 응답에서 필드 확인, 값은 null)
    "special_apply_end": ["SPSPLY_RCEPT_ENDDE"],
    "area_code_nm": ["SUBSCRPT_AREA_CODE_NM"],      # 공급지역 이름 (서울/경기/...)
    # 아래 셋은 일반분양(APT) 개요에만 있을 수 있다. 무순위 개요에는 없음 (2026-09-29 실제 응답 확인)
    # → 없으면 주소로 규제지역을 판정한다.
    "speculative": ["SPECLT_RDN_EARTH_AT"],        # 투기과열지구 Y/N
    "adjusted": ["MDAT_TRGET_AREA_SECD"],          # 조정대상지역 Y/N
    "price_cap": ["PARCPRC_ULS_AT"],               # 분양가상한제 Y/N
    # 주택형별(Mdl)
    "house_ty": ["HOUSE_TY"],
    "price": ["LTTOT_TOP_AMOUNT", "SUPLY_AMOUNT"],  # 만 원
    "households": ["SUPLY_HSHLDCO", "SPSPLY_HSHLDCO"],
}


class ApplyhomeError(RuntimeError):
    pass


def pick(raw: dict, key: str):
    for k in FIELD[key]:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def to_date(v) -> Optional[str]:
    """'20261006', '2026-10-06', '2026.10.06' → '2026-10-06'."""
    if not v:
        return None
    d = re.sub(r"[^0-9]", "", str(v))
    if len(d) >= 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    if len(d) == 6:
        return f"{d[:4]}-{d[4:6]}"
    return None


def to_int(v) -> Optional[int]:
    if v in (None, ""):
        return None
    d = re.sub(r"[^0-9]", "", str(v))
    return int(d) if d else None


def area_of(house_ty: Optional[str]) -> Optional[float]:
    m = re.match(r"^\s*(\d+(?:\.\d+)?)", house_ty or "")
    return float(m.group(1)) if m else None


def unit_label(house_ty: Optional[str]) -> str:
    """'084.9811C' → '84C'."""
    a = area_of(house_ty)
    suffix = re.sub(r"^[\d.\s]+", "", house_ty or "")
    return f"{int(a) if a else ''}{suffix}" or (house_ty or "")


class ApplyhomeClient:
    def __init__(self, service_key: Optional[str] = None, client: Optional[httpx.Client] = None):
        self.key = service_key or os.environ.get("DATA_GO_KR_KEY")
        if not self.key:
            raise ApplyhomeError("환경변수 DATA_GO_KR_KEY 가 없어요. .env 에 일반 인증키(Decoding)를 넣어 주세요.")
        self.http = client or httpx.Client(timeout=20)

    def _get(self, path: str, **params) -> dict:
        params = {"page": 1, "perPage": 100, "returnType": "JSON", "serviceKey": self.key, **params}
        r = self.http.get(config.APPLYHOME_BASE_URL + path, params=params)
        if r.status_code == 401:
            raise ApplyhomeError("인증키가 거절됐어요. 발급 직후라면 1~2시간 뒤 다시 시도하세요. Decoding 키를 쓰세요.")
        r.raise_for_status()
        return r.json()

    def notices(self, category: str, since: Optional[str] = None, max_pages: int = 30) -> list[dict]:
        """공고 개요. since(YYYY-MM-DD) 이후 모집공고만 돌려준다.

        무순위 개요는 1,700건 넘게 쌓여 있고 최신 공고가 앞에 온다 (2026-09-29 확인).
        서버 필터(cond[RCRIT_PBLANC_DE::GTE])를 먼저 시도하고, 안 되면 페이지를 넘기다
        since 보다 오래된 공고만 나오는 페이지에서 멈춘다.
        """
        path = config.APPLYHOME_ENDPOINTS[category][0]
        use_filter = bool(since)
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            params = {"page": page}
            if use_filter:
                params["cond[RCRIT_PBLANC_DE::GTE]"] = since
            try:
                data = self._get(path, **params).get("data", [])
            except httpx.HTTPStatusError:
                if not use_filter:
                    raise
                use_filter, out = False, []          # 필터 미지원 → 처음부터 다시
                data = self._get(path, page=1).get("data", [])
            fresh = [d for d in data if not since or (to_date(pick(d, "notice")) or "") >= since]
            out.extend(fresh)
            if len(data) < 100 or (since and not use_filter and not fresh):
                break
        return out

    def models(self, category: str, notice_no: str) -> list[dict]:
        path = config.APPLYHOME_ENDPOINTS[category][1]
        return self._get(path, **{"cond[PBLANC_NO::EQ]": notice_no}).get("data", [])


def normalize(detail: dict, model: dict, category: str) -> dict:
    """개요 1건 + 주택형 1건 → Listing 생성용 dict (시세·규제 판정 전)."""
    price_manwon = to_int(pick(model, "price"))
    house_ty = pick(model, "house_ty")
    yn = lambda v: None if v is None else str(v).upper() in ("Y", "1", "TRUE")
    return {
        "notice_no": str(pick(detail, "notice_no") or pick(detail, "manage_no") or ""),
        "name": pick(detail, "name") or "",
        "address": pick(detail, "address") or "",
        "kind": pick(detail, "kind") or ("무순위·잔여세대" if category == "remainder" else "일반분양"),
        "category": category,
        "house_ty": house_ty,
        "unit": unit_label(house_ty),
        "area": area_of(house_ty),
        "households": to_int(pick(model, "households")),
        "notice": to_date(pick(detail, "notice")),
        "apply": to_date(pick(detail, "apply")),
        "apply_end": to_date(pick(detail, "apply_end")),
        "winner": to_date(pick(detail, "winner")),
        "contract": to_date(pick(detail, "contract")),
        "contract_end": to_date(pick(detail, "contract_end")),
        "total_households": to_int(pick(detail, "total_households")),
        "move_in": to_date(pick(detail, "move_in")),
        "url": pick(detail, "url"),
        "supply_type": pick(detail, "kind"),
        "house_secd": pick(detail, "house_secd"),
        "house_dtl": pick(detail, "house_dtl"),
        "rent_secd": pick(detail, "rent_secd"),
        "special_apply": to_date(pick(detail, "special_apply")),
        "special_apply_end": to_date(pick(detail, "special_apply_end")),
        "area_code_nm": pick(detail, "area_code_nm"),
        "price": price_manwon / 10000 if price_manwon else None,
        "speculative": yn(pick(detail, "speculative")),
        "adjusted": yn(pick(detail, "adjusted")),
        "price_cap": yn(pick(detail, "price_cap")),
    }


RAW_KEYS: dict[str, list[str]] = {}   # 실행 기록용: 엔드포인트별 실제 응답 키


def iter_open_listings(client: ApplyhomeClient, today: str, since: str) -> Iterable[dict]:
    """접수가 끝나지 않은 공고를 주택형 단위로 펼쳐서 돌려준다."""
    for category in config.APPLYHOME_ENDPOINTS:
        for d in client.notices(category, since=since):
            RAW_KEYS.setdefault(f"{category} 개요", sorted(d.keys()))
            end = to_date(pick(d, "apply_end")) or to_date(pick(d, "apply"))
            if end and end < today:
                continue
            no = str(pick(d, "notice_no") or "")
            if not no:
                continue
            for m in client.models(category, no):
                RAW_KEYS.setdefault(f"{category} 주택형", sorted(m.keys()))
                yield normalize(d, m, category)


def probe_fields(client: ApplyhomeClient) -> dict[str, list[str]]:
    """아직 수집하지 않는 엔드포인트의 실제 응답 키를 확인한다 (필터 추가 전 근거 확보용)."""
    out = {}
    for name, path in config.APPLYHOME_PROBE_ENDPOINTS.items():
        try:
            rows = client._get(path, perPage=1).get("data", [])
            out[name] = sorted(rows[0].keys()) if rows else ["(데이터 없음)"]
        except Exception as e:
            out[name] = [f"(실패: {e.__class__.__name__})"]
    return out
