from fastapi.testclient import TestClient

from selfware.api.app import app
from selfware.observability.cost import estimate_cost_usd

client = TestClient(app)


def ask(q, strategy="para"):
    return client.get("/ask", params={"q": q, "strategy": strategy}).json()


def test_cost_starts_empty():
    body = client.get("/cost").json()
    assert body["total_usd"] == 0.0
    assert body["query_count"] == 0
    assert body["call_count"] == 0
    assert body["tiers"] == []


def test_cost_totals_match_the_price_list():
    answer = ask("When is my thesis defense?")
    expected = sum(
        estimate_cost_usd(c["model"], c["tokens_in"], c["tokens_out"])
        for c in answer["tier_calls"]
    )
    body = client.get("/cost").json()
    assert round(body["total_usd"], 10) == round(expected, 10)
    assert body["query_count"] == 1
    assert body["call_count"] == len(answer["tier_calls"])
    assert body["per_query_usd"] == body["total_usd"]


def test_cost_accumulates_across_questions():
    ask("When is my thesis defense?", "para")
    ask("When is my thesis defense?", "flat")
    ask("How do I rotate a JWT signing key?", "para")
    body = client.get("/cost").json()
    assert body["query_count"] == 3
    assert round(body["per_query_usd"], 10) == round(body["total_usd"] / 3, 10)


def test_tier_split_is_consistent():
    ask("When is my thesis defense?", "para")
    ask("How do I rotate a JWT signing key?", "flat")
    body = client.get("/cost").json()
    tiers = {t["tier"]: t for t in body["tiers"]}
    assert set(tiers) == {"nano", "ultra"}
    assert round(sum(t["cost_share"] for t in body["tiers"]), 6) == 1.0
    assert round(sum(t["call_share"] for t in body["tiers"]), 6) == 1.0
    assert sum(t["calls"] for t in body["tiers"]) == body["call_count"]
    assert sum(t["tokens_in"] for t in body["tiers"]) == body["tokens_in"]
    assert sum(t["tokens_out"] for t in body["tiers"]) == body["tokens_out"]
    # Ultra is ~17x pricier per input token, so it dominates the cost.
    assert body["tiers"][0]["tier"] == "ultra"
    assert tiers["nano"]["label"] == "Nemotron Nano"
    assert tiers["ultra"]["label"] == "Nemotron Ultra"


def test_flat_only_traffic_has_no_nano_calls():
    ask("When is my thesis defense?", "flat")
    body = client.get("/cost").json()
    assert [t["tier"] for t in body["tiers"]] == ["ultra"]


def test_average_latency_is_the_mean_over_calls():
    answer = ask("When is my thesis defense?")
    latencies = [c["latency_ms"] for c in answer["tier_calls"]]
    body = client.get("/cost").json()
    assert round(body["avg_latency_ms"], 6) == round(sum(latencies) / len(latencies), 6)
