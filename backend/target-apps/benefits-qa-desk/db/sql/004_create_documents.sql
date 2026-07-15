-- 004_create_documents.sql
-- Documents table tracking uploaded files and processing status

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'document_status' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE document_status AS ENUM ('waiting', 'processing', 'ready', 'failed');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id),
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    status document_status NOT NULL DEFAULT 'waiting',
    uploaded_by UUID NOT NULL REFERENCES users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents (collection_id);
