# PostgreSQL analytics layer

The project uses PostgreSQL as the persistence and reporting layer between
the Python forecasting/procurement pipeline and Power BI.

To rebuild the SQL layer, run `reset_database.sql`, populate the three
tables from notebook 07, and then create the analytical views with `views.sql`.

## Tables

- `demand_forecasts`: actual demand and forecasts from the weekly baseline,
  ML model, and REE D+1 benchmark.
- `market_prices`: day-ahead and imbalance settlement prices.
- `procurement_results`: hourly procurement quantities and costs for each
  forecasting strategy.

## Views

- `vw_strategy_summary`: aggregate procurement performance by strategy.
- `vw_monthly_costs`: monthly procurement costs.
- `vw_monthly_savings`: monthly savings between forecasting strategies.
- `vw_hourly_operations`: hourly demand, forecasts, prices, and procurement
  diagnostics used by Power BI.

Monthly aggregations use the `Europe/Madrid` timezone.

The database is populated from `notebooks/07_sql_analytics.ipynb`.
The analytical views are defined in `views.sql`.