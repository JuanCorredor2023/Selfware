from fastapi.testclient import TestClient

from selfware.api.app import app

client = TestClient(app)


def test_ask_returns_answer_shape():
    response = client.get(
        "/ask", params={"q": "what are my active projects", "strategy": "para"}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "text",
        "confidence",
        "provenance",
        "used_web",
        "tier_calls",
    }
    assert isinstance(body["text"], str)
    assert isinstance(body["provenance"], list)
    assert isinstance(body["tier_calls"], list)


def test_ask_defaults_strategy_to_para():
    response = client.get("/ask", params={"q": "hello"})
    assert response.status_code == 200
    assert "para" in response.json()["text"]


def test_ask_rejects_invalid_strategy():
    response = client.get("/ask", params={"q": "hello", "strategy": "does-not-exist"})
    assert response.status_code == 422
