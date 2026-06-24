-- Set search path to notice_board_ui schema
SET search_path TO notice_board_ui;

-- Dev re-apply: drop stale table if a prior partial run left mismatched columns
DROP TABLE IF EXISTS notices CASCADE;

-- Notices table for company announcements
CREATE TABLE notices (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    author_display_name VARCHAR(100) NOT NULL,
    start_date DATE,
    end_date DATE,
    archived BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_notices_category ON notices(category_id);
CREATE INDEX IF NOT EXISTS idx_notices_active ON notices(archived, start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_notices_dates ON notices(start_date, end_date);