from unittest.mock import MagicMock
from app.api.chat_models import _calc_cost


def test_calc_cost_per_1k():
    cfg = MagicMock()
    cfg.pricing_unit = "per_1k"
    cfg.price_input_per_1k = 0.01
    cfg.price_output_per_1k = 0.02

    cost = _calc_cost(cfg, prompt_tokens=1500, completion_tokens=800)
    # 1500/1000 * 0.01 + 800/1000 * 0.02 = 0.015 + 0.016 = 0.031
    assert abs(cost - 0.031) < 0.0001


def test_calc_cost_per_1m():
    cfg = MagicMock()
    cfg.pricing_unit = "per_1m"
    cfg.price_input_per_1k = 1.5   # $1.50 per 1M tokens
    cfg.price_output_per_1k = 3.0  # $3.00 per 1M tokens

    cost = _calc_cost(cfg, prompt_tokens=500_000, completion_tokens=200_000)
    # 500000/1000000 * 1.5 + 200000/1000000 * 3.0 = 0.75 + 0.6 = 1.35
    assert abs(cost - 1.35) < 0.0001


def test_calc_cost_null_unit_defaults_to_per_1k():
    cfg = MagicMock()
    cfg.pricing_unit = None
    cfg.price_input_per_1k = 0.01
    cfg.price_output_per_1k = 0.02

    cost = _calc_cost(cfg, prompt_tokens=1000, completion_tokens=500)
    assert abs(cost - 0.02) < 0.0001


def test_calc_cost_zero_price():
    cfg = MagicMock()
    cfg.pricing_unit = "per_1m"
    cfg.price_input_per_1k = 0
    cfg.price_output_per_1k = 0

    cost = _calc_cost(cfg, prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == 0.0
