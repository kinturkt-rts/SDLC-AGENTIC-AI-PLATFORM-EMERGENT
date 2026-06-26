-- Add indexes for reviews table
CREATE INDEX IF NOT EXISTS idx_submitted_at ON reviews (submitted_at);
CREATE INDEX IF NOT EXISTS idx_risk_band ON reviews (risk_band);
CREATE INDEX IF NOT EXISTS idx_created_by ON reviews (created_by);