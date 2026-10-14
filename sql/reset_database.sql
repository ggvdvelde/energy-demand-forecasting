-- WARNING:
-- This script removes the analytical views and tables used by the project.
-- Run it only when rebuilding the PostgreSQL analytics layer.

DROP VIEW IF EXISTS vw_monthly_savings CASCADE;
DROP VIEW IF EXISTS vw_monthly_costs CASCADE;
DROP VIEW IF EXISTS vw_strategy_summary CASCADE;
DROP VIEW IF EXISTS vw_hourly_operations CASCADE;

DROP TABLE IF EXISTS procurement_results CASCADE;
DROP TABLE IF EXISTS market_prices CASCADE;
DROP TABLE IF EXISTS demand_forecasts CASCADE;