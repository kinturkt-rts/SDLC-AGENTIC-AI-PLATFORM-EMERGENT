-- 001_create_students.sql
-- Student Management API — students table (FR-1, FR-2, FR-6, FR-8)

CREATE TABLE IF NOT EXISTS students (
    id              SERIAL PRIMARY KEY,
    student_id      VARCHAR(50) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    course          VARCHAR(255) NOT NULL,
    enrollment_date DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive')),
    CONSTRAINT chk_enrollment_date CHECK (enrollment_date <= CURRENT_DATE)
);

CREATE INDEX IF NOT EXISTS idx_students_course ON students (course);
CREATE INDEX IF NOT EXISTS idx_students_status ON students (status);
