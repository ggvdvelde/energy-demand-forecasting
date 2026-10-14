import pandas as pd
import numpy as np

def add_calendar_features(
    demand: pd.DataFrame,
    timezone: str = "Europe/Madrid",
) -> pd.DataFrame:
    result = demand.copy()

    local_time = result.index.tz_convert(timezone)

    result["datetime_local"] = local_time
    result["hour"] = local_time.hour
    result["day_of_week"] = local_time.day_name()
    result["month"] = local_time.month

    return result


def add_demand_lags(
    demand: pd.DataFrame,
    target: str = "demand_MW",
    lags: tuple[int, ...] = (48, 168, 336, 504),
) -> pd.DataFrame:
    result = demand.copy()

    for lag in lags:
        result[f"lag_{lag}"] = result[target].shift(lag)

    return result

def recent_demand_mean(
    demand: pd.DataFrame,
    hours: int,
    target: str = "demand_MW",
    timezone: str = "Europe/Madrid",
    cutoff_hour: int = 12,
) -> pd.Series:
    
    if not np.isfinite(hours) or hours <= 0:
        raise ValueError("hours must be a positive finite number.")

    local_times = demand.index.tz_convert(timezone)
    local_days = local_times.tz_localize(None).normalize()
    unique_days = local_days.unique()
    # Construct noon in local wall time before applying an elapsed-hour window.
    cutoffs = (unique_days - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)).tz_localize(timezone)
    starts = cutoffs - pd.Timedelta(hours=hours)

    demand = pd.Series(
        demand[target].to_numpy(dtype=float),
        index=local_times,
    ).sort_index()
    values = demand.to_numpy()
    valid = ~np.isnan(values)
    cumulative_sum = np.concatenate(([0.0], np.cumsum(np.where(valid, values, 0.0))))
    cumulative_count = np.concatenate(([0], np.cumsum(valid)))

    left = demand.index.searchsorted(starts, side="left")
    right = demand.index.searchsorted(cutoffs, side="left")
    counts = cumulative_count[right] - cumulative_count[left]
    means = np.divide(
        cumulative_sum[right] - cumulative_sum[left],
        counts,
        out=np.full(len(unique_days), np.nan),
        where=counts > 0,
    )
    return pd.Series(
        means[unique_days.get_indexer(local_days)],
        index=demand.index,
        name=f"recent_demand_{hours}h",
    )



def add_recent_demand_features(
    demand: pd.DataFrame,
    timezone: str = "Europe/Madrid",
) -> pd.DataFrame:

    result = demand.copy()

    result["recent_demand_6hs_mean"] = recent_demand_mean(
        result,
        hours=6,
        timezone=timezone,
    )

    local_days = (
        result.index
        .tz_convert(timezone)
        .tz_localize(None)
        .normalize()
    )

    recent_by_day = (
        result["recent_demand_6hs_mean"]
        .groupby(local_days)
        .first()
    )

    previous_week = (
        local_days - pd.Timedelta(days=7)
    ).map(recent_by_day)

    result["recent_regime"] = (
        result["recent_demand_6hs_mean"]
        - previous_week
    )

    return result