-- 005_add_faq_tsvector_trigger.sql
-- Idempotent: GIN index on search_vector + trigger to maintain it

-- GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_faq_tsv
    ON healthcare_clinic_bot.faq_entries USING GIN (search_vector);

-- Function to auto-update search_vector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION healthcare_clinic_bot.faq_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.question, '') || ' ' || COALESCE(NEW.answer, ''));
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger (idempotent pattern)
DROP TRIGGER IF EXISTS trg_faq_search_vector ON healthcare_clinic_bot.faq_entries;

CREATE TRIGGER trg_faq_search_vector
    BEFORE INSERT OR UPDATE ON healthcare_clinic_bot.faq_entries
    FOR EACH ROW
    EXECUTE FUNCTION healthcare_clinic_bot.faq_search_vector_update();
