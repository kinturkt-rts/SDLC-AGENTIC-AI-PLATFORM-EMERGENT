-- 004_create_fx_rate_snapshots.sql
-- FX rate snapshot table (FR-2, FR-9)

CREATE TABLE IF NOT EXISTS fx_rate_snapshots (
    currency CHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    usd_rate NUMERIC(19,6) NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (currency, rate_date)
);
