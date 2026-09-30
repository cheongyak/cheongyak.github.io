"""웹 앱이 부르는 API 서버.

    uvicorn app.api:app --reload

GET  /listings              등급이 매겨진 공고 목록 (grade=lotto|consider|flat|pass 로 거르기)
GET  /listings/{id}         공고 하나 + 등급 + 전세 가능 여부
POST /listings/{id}/judge   내 조건(Profile)과 계획(PlanOptions)을 보내면 자격·자금까지 판정
GET  /rules                 지금 적용 중인 규칙 값
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import rules as R
from .engine import grade, judge
from .models import Listing, PlanOptions, Profile
from .pipeline import DATA

app = FastAPI(title="청약패스 API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])

GRADE_ORDER = {"lotto": 0, "consider": 1, "flat": 2, "pass": 3, "unknown": 4}


def load() -> list[Listing]:
    path = Path(os.environ.get("LISTINGS_PATH", DATA))
    if not path.exists():
        return []
    return [Listing(**x) for x in json.loads(path.read_text(encoding="utf-8"))]


def status_of(L: Listing, today: str) -> str:
    """모집 상태: 예정 / 접수중 / 마감 (접수 시작·종료일 기준)."""
    start, end = L.special_apply or L.apply, L.apply_end or L.apply
    if start and today < start:
        return "예정"
    if end and today > end:
        return "마감"
    return "접수중"


@app.get("/listings")
def listings(grade_filter: Optional[str] = None, region: Optional[str] = None, sido: Optional[str] = None,
             district: Optional[str] = None, supply_type: Optional[str] = None, status: Optional[str] = None,
             date_field: str = "apply", date_from: Optional[str] = None, date_to: Optional[str] = None):
    """모든 조건은 함께 적용된다 (AND). date_field: notice|apply|apply_end|winner."""
    from datetime import date as _d
    today = _d.today().isoformat()
    if date_field not in ("notice", "apply", "apply_end", "winner"):
        raise HTTPException(400, "date_field 는 notice, apply, apply_end, winner 중 하나예요.")
    rows = []
    for L in load():
        g = grade(L)
        if grade_filter and g["grade"] != grade_filter:
            continue
        if region and L.region != region:
            continue
        if sido and L.sido != sido:
            continue
        if district and L.district != district:
            continue
        if supply_type and L.supply_type != supply_type:
            continue
        if status and status_of(L, today) != status:
            continue
        dv = getattr(L, date_field)
        if (date_from or date_to) and not dv:
            continue
        if date_from and dv < date_from:
            continue
        if date_to and dv > date_to:
            continue
        rows.append({"listing": L.model_dump(), "grade": g})
    rows.sort(key=lambda r: (GRADE_ORDER[r["grade"]["grade"]], r["listing"]["apply"] or "9999"))
    return rows


def _find(listing_id: str) -> Listing:
    for L in load():
        if L.id == listing_id:
            return L
    raise HTTPException(404, "공고를 찾을 수 없어요.")


@app.get("/listings/{listing_id}")
def listing(listing_id: str):
    return judge(_find(listing_id))


class JudgeBody(BaseModel):
    profile: Profile
    plan: PlanOptions = PlanOptions()


@app.post("/listings/{listing_id}/judge")
def judge_listing(listing_id: str, body: JudgeBody):
    return judge(_find(listing_id), body.profile, body.plan)


@app.get("/rules")
def current_rules():
    return {k: v for k, v in vars(R).items() if k.isupper() and not k.endswith("_LAWD")}
