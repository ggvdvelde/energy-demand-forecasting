import pandas as pd
import pytest

from energy_forecasting.procurement import compute_procurement_cost


def test_procurement_accounting():

    df = pd.DataFrame({
        "demand_MW": [110, 90],
        "forecast": [100, 100],
        "day_ahead_price": [50, 50],
        "imbalance_price_up": [40, 40],
        "imbalance_price_down": [70, 70],
    })

    result = compute_procurement_cost(
        data=df,
        forecast_col="forecast",
    )

    assert result["total_cost"] == pytest.approx(10300)
    assert result["shortfall_cost"] == pytest.approx(200)
    assert result["surplus_cost"] == pytest.approx(100)
    assert result["incremental_cost"] == pytest.approx(300)
    assert result["incremental_cost_per_MWh"] == pytest.approx(1.5)


def test_perfect_forecast_has_zero_incremental_cost():

    df = pd.DataFrame({
        "demand_MW": [80, 120],
        "forecast": [80, 120],
        "day_ahead_price": [50, 60],
        "imbalance_price_up": [40, 45],
        "imbalance_price_down": [70, 75],
    })

    result = compute_procurement_cost(
        data=df,
        forecast_col="forecast",
    )

    assert result["total_cost"] == pytest.approx(11200)
    assert result["shortfall_cost"] == pytest.approx(0)
    assert result["surplus_cost"] == pytest.approx(0)
    assert result["incremental_cost"] == pytest.approx(0)
    assert result["incremental_cost_per_MWh"] == pytest.approx(0)