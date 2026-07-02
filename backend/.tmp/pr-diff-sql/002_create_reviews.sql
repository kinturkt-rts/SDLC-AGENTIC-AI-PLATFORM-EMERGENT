-- 002_create_reviews.sql
-- Create reviews table per design §3

CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL,
    diff_text TEXT NOT NULL,
    file_count INT,
    lines_added INT,
    lines_removed INT,
    summary TEXT,
    risk_factors TEXT[],
    risk_score INT,
    risk_band risk_band_enum,
    model_id TEXT,
    created_by TEXT
);

-- Indexes per design §3
CREATE INDEX IF NOT EXISTS idx_reviews_submitted_at ON reviews (submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_risk_band ON reviews (risk_band);
CREATE INDEX IF NOT EXISTS idx_reviews_submitted_at_risk_band ON reviews (submitted_at, risk_band);
