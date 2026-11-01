import json
from unittest.mock import AsyncMock, patch

import httpx

from app.config import Settings, get_settings
from app.main import app


def test_chat_structured_json_response(client):
    req_body = {
        "message": "What is the minimum vertical clearance for a 33 kV line over a road?",
        "project_type": "substation",
        "voltage_level_kv": 33.0,
    }
    r = client.post("/chat", json=req_body)
    assert r.status_code == 200
    data = r.json()

    # Verify structured fields
    assert "reply" in data
    assert "model_used" in data
    assert "provider" in data
    assert "fallback_triggered" in data
    assert "attempt_count" in data
    assert "usage" in data
    assert "citations" in data

    # Verify usage object
    usage = data["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["cost_usd"] >= 0.0

    # Verify citations
    assert len(data["citations"]) > 0
    assert any("58" in c["regulation_no"] for c in data["citations"])


def test_chat_fallback_mechanism(client):
    # Test forcing fallback explicitly
    req_body = {
        "message": "Explain earthing requirements.",
        "force_fallback": True,
    }
    r = client.post("/chat", json=req_body)
    assert r.status_code == 200
    data = r.json()
    assert data["fallback_triggered"] is True
    assert data["model_used"] == "mock-cea-expert"
    assert data["provider"] == "mock"


def test_chat_query_clearance_33kv(client):
    r = client.post(
        "/chat",
        json={"message": "What is the minimum vertical clearance for a 33 kV line over a road?"},
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "6.1" in reply
    assert "Regulation 58" in reply
    assert "2023" in reply


def test_chat_query_earthing_diff(client):
    msg = "What changed in the safety regulations between 2010 and 2023 on earthing?"
    r = client.post("/chat", json={"message": msg})
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "2010" in reply
    assert "2023" in reply
    lower_reply = reply.lower()
    assert (
        "maintenance-free" in lower_reply
        or "chemical" in lower_reply
        or "regulation 41" in lower_reply
    )


def test_chat_query_solar_connectivity(client):
    r = client.post(
        "/chat",
        json={"message": "Which regulation covers grid connectivity for rooftop solar inverters?"},
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Connectivity to the Grid" in reply
    assert "2019" in reply
    assert "anti-islanding" in reply.lower() or "inverter" in reply.lower()


def test_chat_query_state_tariff_unanswerable(client):
    msg = "What is the per-unit feed-in tariff and net metering settlement rate paid by TANGEDCO in Tiruppur?"
    r = client.post("/chat", json={"message": msg})
    assert r.status_code == 200
    reply = r.json()["reply"]
    lower_reply = reply.lower()
    assert (
        "cannot be answered" in lower_reply
        or "tnerc" in lower_reply
        or "tangedco" in lower_reply
    )


def test_chat_streaming(client):
    r = client.post(
        "/chat",
        json={"message": "What is the clearance for 33 kV?", "stream": True},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    lines = r.text.strip().split("\n\n")
    assert len(lines) >= 2

    # Verify chunk structure
    first_chunk = json.loads(lines[0].replace("data: ", ""))
    assert "chunk" in first_chunk
    assert first_chunk["done"] is False

    # Verify final completion event
    last_event = json.loads(lines[-1].replace("data: ", ""))
    assert last_event["done"] is True
    assert "model_used" in last_event
    assert "usage" in last_event


def test_chat_primary_failure_retries_and_falls_back():
    """Verify that when primary model raises an HTTP error, it retries and then falls back smoothly."""
    mock_settings = Settings(
        app_name="VoltClause",
        environment="test",
        primary_model="gpt-4o-mini",
        fallback_model="mock-cea-expert",
        openai_api_key="fake-key-for-test",
        llm_timeout_seconds=2.0,
        llm_max_retries=2,
        llm_retry_delay_seconds=0.01,
    )
    app.dependency_overrides[get_settings] = lambda: mock_settings

    from fastapi.testclient import TestClient

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Simulate OpenAI endpoint timing out or failing with 500 error
        mock_post.side_effect = httpx.ConnectError("Connection timed out to api.openai.com")

        with TestClient(app) as test_client:
            r = test_client.post(
                "/chat",
                json={"message": "What is the minimum vertical clearance for a 33 kV line over a road?"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["fallback_triggered"] is True
            assert data["model_used"] == "mock-cea-expert"
            assert mock_post.call_count == 2  # Attempt 1 + 1 retry

    app.dependency_overrides.clear()
