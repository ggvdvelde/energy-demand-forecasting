import numpy as np
import pandas as pd

from energy_forecasting.features import (
    add_demand_lags,
    recent_demand_mean,
)


def test_demand_lags_use_past_observations():

    index = pd.date_range(
        "2025-01-01",
        periods=200,
        freq="h",
        tz="UTC",
    )

    demand = pd.DataFrame(
        {
            "demand_MW": np.arange(200, dtype=float),
        },
        index=index,
    )

    result = add_demand_lags(
        demand,
        lags=(48, 168),
    )

    assert result.iloc[168]["lag_48"] == 120
    assert result.iloc[168]["lag_168"] == 0


def test_recent_demand_mean_respects_d_minus_1_cutoff():

    index_local = pd.date_range(
        "2025-01-01 00:00",
        "2025-01-03 23:00",
        freq="h",
        tz="Europe/Madrid",
    )

    index_utc = index_local.tz_convert("UTC")

    values = np.zeros(len(index_utc))

    previous_day_window = (
        (index_local.date == pd.Timestamp("2025-01-02").date())
        & (index_local.hour >= 6)
        & (index_local.hour < 12)
    )

    values[previous_day_window] = [1, 2, 3, 4, 5, 6]

    # These values are deliberately huge. They occur at or after
    # the D-1 12:00 forecast cutoff and must not affect the feature.
    unavailable_future_data = (
        (index_local.date == pd.Timestamp("2025-01-02").date())
        & (index_local.hour >= 12)
    )

    values[unavailable_future_data] = 1000

    demand = pd.DataFrame(
        {
            "demand_MW": values,
        },
        index=index_utc,
    )

    recent = recent_demand_mean(
        demand,
        hours=6,
        timezone="Europe/Madrid",
        cutoff_hour=12,
    )

    target_day = (
        recent.index.normalize()
        == pd.Timestamp(
            "2025-01-03",
            tz="Europe/Madrid",
        )
    )

    target_values = recent.loc[target_day]

    assert len(target_values) == 24
    assert np.allclose(target_values.to_numpy(), 3.5)