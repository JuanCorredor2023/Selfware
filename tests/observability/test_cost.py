from observability.cost import estimate_cost_usd


def test_estimate_cost_unknown_model_is_zero():
    assert estimate_cost_usd("modelo-desconocido", 1000, 1000) == 0.0
