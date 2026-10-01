"""수집 설정·지난 결과 읽기 (알림 공통).

예전에는 ntfy 푸시 알림을 여기서 보냈다. 2026-10-01 정리로 ntfy 는 삭제했고, 알림은 웹 푸시(app/webpush.py)만 쓴다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "docs" / "config.json"
PREVIOUS = ROOT / "docs" / "listings.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_previous_ids() -> Optional[set[str]]:
    """지난 실행 결과의 공고 id. 파일이 없으면 None (첫 실행이라 '새 공고' 알림을 보내지 않는다)."""
    try:
        return {x["id"] for x in json.loads(PREVIOUS.read_text(encoding="utf-8"))}
    except Exception:
        return None
