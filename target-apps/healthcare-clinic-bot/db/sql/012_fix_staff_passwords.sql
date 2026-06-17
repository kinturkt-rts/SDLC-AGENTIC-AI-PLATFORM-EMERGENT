-- Fix staff demo passwords when 011_seed.sql used a placeholder bcrypt hash.
-- Password: changeme
-- Use dollar-quoting ($pwd$...$pwd$) so psql does not mis-parse $ in bcrypt hashes.

UPDATE healthcare_clinic_bot.users
SET hashed_password = $pwd$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve$pwd$
WHERE username IN ('admin', 'dr.jones', 'nurse.smith', 'frontdesk.lee', 'receptionist.garcia');
