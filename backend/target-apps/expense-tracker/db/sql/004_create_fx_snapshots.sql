-- 004_create_fx_snapshots.sql
-- Creates the fx_snapshots table (FR-10)

CREATE TABLE IF NOT EXISTS fx_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    currency CHAR(3) NOT NULL,
    date DATE NOT NULL,
    rate_to_usd NUMERIC(19,4) NOT NULL,
    CONSTRAINT uq_fx_currency_date UNIQUE (currency, date)
);
