import pytest


@pytest.fixture(autouse=True)
def _isolate_market_cache(tmp_path, monkeypatch):
    """테스트가 docs/market-cache.json (실제 서비스 기록)을 읽거나 덮어쓰지 않게 한다"""
    from app import pipeline
    monkeypatch.setattr(pipeline, "MARKET_CACHE", tmp_path / "market-cache.json")
    monkeypatch.setattr(pipeline, "FRESH", tmp_path / "data-updated.txt")   # docs/data-updated.txt (마지막 정상 수집 시각)도 건드리지 않게
    monkeypatch.setattr(pipeline.notify, "PREVIOUS", tmp_path / "no-previous.json")   # 실제 서비스 결과(docs/listings.json)를 지난 결과로 쓰지 않게


@pytest.fixture(autouse=True)
def _ai_answers_in_tmp(tmp_path, monkeypatch):
    """시험이 저장소의 AI 답 폴더(evidence/lh/ai·evidence/notices/ai)를 읽거나 쓰지 않게 한다 (기능 ai_read·ai_read_sale).
    2026-11-11: 수집이 Claude API 를 부르던 하루 동안 시험이 실제로 한 번 불러 답 파일이 저장소에 들어갔다. 11-12 부터 수집은 API 를 부르지 않는다(키는 청약봇 전용)."""
    from app import ai_read
    monkeypatch.setattr(ai_read, "DIR", tmp_path / "ai-lh")
    monkeypatch.setattr(ai_read, "SALE_DIR", tmp_path / "ai-sale")
    monkeypatch.setattr(ai_read, "SH_DIR", tmp_path / "ai-sh")
