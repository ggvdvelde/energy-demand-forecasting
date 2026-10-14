-- ============================================================
-- Energy Demand Forecasting & Procurement Analytics
-- Analytical views used by Power BI
-- ============================================================

-- 1. Strategy-level procurement performance
CREATE VIEW vw_strategy_summary AS

SELECT
    pr.strategy,

    COUNT(*) AS n_hours,

    SUM(
        pr.incremental_cost_eur
    ) AS incremental_cost_eur,

    SUM(
        df.actual_demand_mw
    ) AS supplied_mwh,

    SUM(
        pr.incremental_cost_eur
    )
    /
    SUM(
        df.actual_demand_mw
    ) AS incremental_cost_eur_per_mwh

FROM procurement_results pr

JOIN demand_forecasts df
    ON pr.timestamp_utc
     = df.timestamp_utc

WHERE df.is_blackout = FALSE

GROUP BY pr.strategy;


-- 2. Monthly procurement costs
CREATE VIEW vw_monthly_costs AS

SELECT
    DATE_TRUNC(
        'month',
        pr.timestamp_utc
        AT TIME ZONE 'Europe/Madrid'
    ) AS month,

    pr.strategy,

    SUM(
        pr.incremental_cost_eur
    ) AS incremental_cost_eur,

    SUM(
        df.actual_demand_mw
    ) AS supplied_mwh,

    SUM(
        pr.incremental_cost_eur
    )
    /
    SUM(
        df.actual_demand_mw
    ) AS incremental_cost_eur_per_mwh

FROM procurement_results pr

JOIN demand_forecasts df
    ON pr.timestamp_utc
     = df.timestamp_utc

WHERE df.is_blackout = FALSE

GROUP BY
    DATE_TRUNC(
        'month',
        pr.timestamp_utc
        AT TIME ZONE 'Europe/Madrid'
    ),
    pr.strategy;

-- 3. Monthly savings across forecasting strategies
CREATE VIEW vw_monthly_savings AS

SELECT
    month,

    MAX(
        CASE
            WHEN strategy = 'lag168'
            THEN incremental_cost_eur_per_mwh
        END
    ) AS lag168_cost_eur_per_mwh,

    MAX(
        CASE
            WHEN strategy = 'ml'
            THEN incremental_cost_eur_per_mwh
        END
    ) AS ml_cost_eur_per_mwh,

    MAX(
        CASE
            WHEN strategy = 'ree'
            THEN incremental_cost_eur_per_mwh
        END
    ) AS ree_cost_eur_per_mwh,

    MAX(
        CASE
            WHEN strategy = 'lag168'
            THEN incremental_cost_eur_per_mwh
        END
    )
    -
    MAX(
        CASE
            WHEN strategy = 'ml'
            THEN incremental_cost_eur_per_mwh
        END
    )
    AS ml_savings_vs_lag168_eur_per_mwh,

    MAX(
        CASE
            WHEN strategy = 'ml'
            THEN incremental_cost_eur_per_mwh
        END
    )
    -
    MAX(
        CASE
            WHEN strategy = 'ree'
            THEN incremental_cost_eur_per_mwh
        END
    )
    AS ree_savings_vs_ml_eur_per_mwh

FROM vw_monthly_costs

GROUP BY month;

-- 4. Hourly operational diagnostics
CREATE VIEW vw_hourly_operations AS

SELECT
    pr.timestamp_utc,
    pr.strategy,

    df.actual_demand_mw,

    pr.forecast_mw,
    pr.forecast_error_mw,
    pr.shortfall_mwh,
    pr.surplus_mwh,

    pr.incremental_cost_eur,

    mp.day_ahead_eur_mwh,
    mp.imbalance_up_eur_mwh,
    mp.imbalance_down_eur_mwh,

    df.is_blackout

FROM procurement_results pr

JOIN demand_forecasts df
    ON pr.timestamp_utc
     = df.timestamp_utc

JOIN market_prices mp
    ON pr.timestamp_utc
     = mp.timestamp_utc;