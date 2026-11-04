import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        app_name="examate-rag",
        environment="test",
        llm_provider="fake",
        cost_log_path=str(tmp_path / "cost.jsonl"),
        price_input_per_million=0.5,
        price_output_per_million=1.5,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        c.settings = settings
        yield c
    app.dependency_overrides.clear()
