-- Create risk_band enum type
CREATE TYPE risk_band_enum AS ENUM ('low', 'medium', 'high');

-- Create reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    diff_text TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    lines_added INTEGER NOT NULL DEFAULT 0,
    lines_removed INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    risk_score INTEGER NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_band risk_band_enum NOT NULL,
    model_id TEXT NOT NULL,
    created_by TEXT NOT NULL
);