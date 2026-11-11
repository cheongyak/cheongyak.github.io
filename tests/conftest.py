import pytest


@pytest.fixture(autouse=True)
def _isolate_market_cache(tmp_path, monkeypatch):
    """테스트가 docs/market-cache.json (실제 서비스 기록)을 읽거나 덮어쓰지 않게 한다"""
    from app import pipeline
    monkeypatch.setattr(pipeline, "MARKET_CACHE", tmp_path / "market-cache.json")
    monkeypatch.setattr(pipeline, "FRESH", tmp_path / "data-updated.txt")   # docs/data-updated.txt (마지막 정상 수집 시각)도 건드리지 않게
    monkeypatch.setattr(pipeline.notify, "PREVIOUS", tmp_path / "no-previous.json")   # 실제 서비스 결과(docs/listings.json)를 지난 결과로 쓰지 않게


@pytest.fixture(autouse=True)
def _no_real_ai_calls(tmp_path, monkeypatch):
    """시험이 실제 Claude 를 부르거나(비용) 저장소의 AI 답 폴더에 쓰지 않게 한다 (기능 ai_read·ai_read_sale).
    2026-11-11: collect.yml 이 키를 일 전체에 주고 그 안에서 pytest 를 돌려, test_notice_retry 가 실제로 한 번 불렀다(추정 $0.01, evidence/notices/ai/2026820015.json 이 저장소에 들어감)."""
    from app import ai_read
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ai_read, "DIR", tmp_path / "ai-lh")
    monkeypatch.setattr(ai_read, "SALE_DIR", tmp_path / "ai-sale")
    monkeypatch.setattr(ai_read, "SPEND", tmp_path / "ai-spend.json")
