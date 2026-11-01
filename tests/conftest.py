import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_usage_tracker
from app.services.usage import UsageTracker


@pytest.fixture
def temp_usage_tracker(tmp_path):
    tracker = UsageTracker(log_file=str(tmp_path / "test_usage.jsonl"))
    return tracker


@pytest.fixture
def client(temp_usage_tracker):
    test_settings = Settings(
        app_name="VoltClause",
        environment="test",
        primary_model="gpt-4o-mini",
        fallback_model="mock-cea-expert",
        openai_api_key=None,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_usage_tracker] = lambda: temp_usage_tracker
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
