-- Migration 005: Create employees table and add circular FK constraints
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department_id UUID NOT NULL REFERENCES departments(id),
    job_role_id UUID NOT NULL REFERENCES job_roles(id),
    manager_id UUID REFERENCES employees(id),
    is_active BOOLEAN NOT NULL DEFAULT true,
    user_account_id UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_employees_manager_id ON employees (manager_id);
CREATE INDEX IF NOT EXISTS idx_employees_is_active ON employees (is_active);
CREATE INDEX IF NOT EXISTS idx_employees_department_id ON employees (department_id);

-- Add the deferred FK from users.employee_id -> employees.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_users_employee_id'
          AND table_schema = current_schema()
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT fk_users_employee_id
            FOREIGN KEY (employee_id) REFERENCES employees(id);
    END IF;
END $$;
