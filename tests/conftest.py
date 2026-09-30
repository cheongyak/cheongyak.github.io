import pytest


@pytest.fixture(autouse=True)
def _isolate_market_cache(tmp_path, monkeypatch):
    """테스트가 docs/market-cache.json (실제 서비스 기록)을 읽거나 덮어쓰지 않게 한다"""
    from app import pipeline
    monkeypatch.setattr(pipeline, "MARKET_CACHE", tmp_path / "market-cache.json")
