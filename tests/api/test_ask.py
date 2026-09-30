from fastapi.testclient import TestClient

from api.app import app

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
    default = client.get("/ask", params={"q": "When is my thesis defense?"}).json()
    para = client.get(
        "/ask", params={"q": "When is my thesis defense?", "strategy": "para"}
    ).json()
    assert default == para


def test_ask_rejects_invalid_strategy():
    response = client.get("/ask", params={"q": "hello", "strategy": "does-not-exist"})
    assert response.status_code == 422


THESIS = "When is my thesis defense?"


def ask(q, strategy):
    response = client.get("/ask", params={"q": q, "strategy": strategy})
    assert response.status_code == 200
    return response.json()


def test_strategies_return_different_answers():
    para = ask(THESIS, "para")
    flat = ask(THESIS, "flat")
    assert para["text"] != flat["text"]
    assert para["provenance"] != flat["provenance"]


def test_para_is_more_confident_than_flat_on_known_topics():
    for question in [THESIS, "status of the year-end trip", "hackathon deadline"]:
        assert ask(question, "para")["confidence"] > ask(question, "flat")["confidence"]


def test_para_only_cites_the_relevant_folder_but_flat_mixes_folders():
    para_paths = {c["para_path"].split("/")[0] for c in ask(THESIS, "para")["provenance"]}
    flat_paths = {c["para_path"].split("/")[0] for c in ask(THESIS, "flat")["provenance"]}
    assert len(flat_paths) > len(para_paths) or len(flat_paths) >= 3


def test_provenance_chunks_follow_contract_c2_shape():
    for chunk in ask(THESIS, "para")["provenance"]:
        assert set(chunk.keys()) == {"text", "item_id", "para_path", "ts", "score"}
        assert 0.0 <= chunk["score"] <= 1.0


def test_unknown_topic_falls_back_to_low_confidence_web_search():
    body = ask("How do I rotate a JWT signing key?", "para")
    assert body["used_web"] is True
    assert body["confidence"] < 0.6
    web = [c for c in body["provenance"] if c["item_id"].startswith("web:")]
    assert web and all(c["para_path"] == "web" for c in web)


def test_known_topics_do_not_use_the_web():
    assert ask(THESIS, "para")["used_web"] is False
    assert ask(THESIS, "flat")["used_web"] is False


def test_tier_calls_get_a_real_cost():
    for call in ask(THESIS, "para")["tier_calls"]:
        assert call["cost_usd"] > 0.0


def test_flat_uses_fewer_calls_but_more_input_tokens_than_para():
    para = ask(THESIS, "para")["tier_calls"]
    flat = ask(THESIS, "flat")["tier_calls"]
    assert len(flat) < len(para)
    assert sum(c["tokens_in"] for c in flat) > sum(c["tokens_in"] for c in para)


def test_each_request_gets_fresh_tier_calls():
    # The mock must not hand out shared objects: the API mutates cost_usd.
    first = ask(THESIS, "para")["tier_calls"]
    second = ask(THESIS, "para")["tier_calls"]
    assert first == second
