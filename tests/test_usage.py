from app.services.llm import calculate_cost


def test_usage_initial_empty(client):
    r = client.get("/usage")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 0
    assert data["total_prompt_tokens"] == 0
    assert data["total_completion_tokens"] == 0
    assert data["total_tokens"] == 0
    assert data["total_cost_usd"] == 0.0
    assert data["breakdown_by_model"] == {}
    assert data["recent_logs"] == []


def test_usage_records_after_chat(client):
    # Make a chat request
    resp = client.post(
        "/chat",
        json={"message": "What is the minimum vertical clearance for a 33 kV line over a road?"},
    )
    assert resp.status_code == 200

    # Verify usage endpoint reflects the call
    r = client.get("/usage")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 1
    assert data["total_tokens"] > 0
    assert len(data["recent_logs"]) == 1
    model_name = resp.json()["model_used"]
    assert model_name in data["breakdown_by_model"]
    assert data["breakdown_by_model"][model_name]["requests"] == 1


def test_usage_cost_calculation():
    # gpt-4o-mini: 1000 prompt tokens @ $0.15/1M + 500 completion @ $0.60/1M
    # cost = (1000 * 0.15 + 500 * 0.60) / 1,000,000 = (150 + 300) / 1,000,000 = 0.00045
    cost = calculate_cost("gpt-4o-mini", 1000, 500)
    assert cost == 0.00045

    # mock-cea-expert: $0
    mock_cost = calculate_cost("mock-cea-expert", 1000, 500)
    assert mock_cost == 0.0


def test_usage_reset(client):
    client.post("/chat", json={"message": "Query 1"})
    usage_before = client.get("/usage").json()
    assert usage_before["total_requests"] == 1

    reset_res = client.post("/usage/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"

    usage_after = client.get("/usage").json()
    assert usage_after["total_requests"] == 0
    assert usage_after["total_tokens"] == 0
    assert len(usage_after["recent_logs"]) == 0
