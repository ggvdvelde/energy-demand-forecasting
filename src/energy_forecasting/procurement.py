import numpy as np
import pandas as pd


def build_procurement_results(
    data: pd.DataFrame,
    forecast_col: str,
    strategy: str,
) -> pd.DataFrame:
    """
    Build hourly procurement-cost results for one forecasting strategy.
    """

    actual = data["demand_MW"]
    forecast = data[forecast_col]

    result = pd.DataFrame(
        index=data.index
    )

    result["strategy"] = strategy
    result["forecast_mw"] = forecast

    result["forecast_error_mw"] = (
        actual - forecast
    )

    result["shortfall_mwh"] = (
        result["forecast_error_mw"]
        .clip(lower=0)
    )

    result["surplus_mwh"] = (
        (-result["forecast_error_mw"])
        .clip(lower=0)
    )

    result["day_ahead_cost_eur"] = (
        forecast
        * data["day_ahead_price"]
    )

    result["imbalance_settlement_eur"] = (
        result["shortfall_mwh"]
        * data["imbalance_price_down"]
        -
        result["surplus_mwh"]
        * data["imbalance_price_up"]
    )

    result["total_cost_eur"] = (
        result["day_ahead_cost_eur"]
        + result["imbalance_settlement_eur"]
    )

    perfect_cost = (
        actual
        * data["day_ahead_price"]
    )

    result["incremental_cost_eur"] = (
        result["total_cost_eur"]
        - perfect_cost
    )

    return result


def compute_procurement_cost(
    data: pd.DataFrame,
    forecast_col: str,
) -> dict[str, float]:
    """
    Compute aggregate procurement and imbalance costs.
    """

    hourly = build_procurement_results(
        data=data,
        forecast_col=forecast_col,
        strategy="strategy",
    )

    actual = data["demand_MW"]

    shortfall_cost = (
        hourly["shortfall_mwh"]
        * (
            data["imbalance_price_down"]
            - data["day_ahead_price"]
        )
    )

    surplus_cost = (
        hourly["surplus_mwh"]
        * (
            data["day_ahead_price"]
            - data["imbalance_price_up"]
        )
    )

    incremental_cost = (
        hourly["incremental_cost_eur"]
    )

    if not np.allclose(
        shortfall_cost + surplus_cost,
        incremental_cost,
    ):
        raise ValueError(
            "Mismatch between incremental cost "
            "and shortfall/surplus costs."
        )

    return {
        "total_cost":
            hourly["total_cost_eur"].sum(),

        "shortfall_cost":
            shortfall_cost.sum(),

        "surplus_cost":
            surplus_cost.sum(),

        "incremental_cost":
            incremental_cost.sum(),

        "incremental_cost_per_MWh": (
            incremental_cost.sum()
            / actual.sum()
        ),
    }