-- 012_fix_user_password_hashes.sql
-- Repair dev seed bcrypt hashes (011 used placeholder values).
-- admin → Admin123!, staff* → Staff123!

SET search_path TO inventory_app;

UPDATE inventory_app.users
SET password_hash = '$2b$12$OjWI13flUsRs1v3My7gcCe/VfXJTswBhGHf9slrYILtNKd3wvSDVW'
WHERE username = 'admin';

UPDATE inventory_app.users
SET password_hash = '$2b$12$D85QqslNti5gnzmPxclL6eu7HqACPRVWN/kx3MQQxKFQRjTCUCG2u'
WHERE username IN ('staff', 'staff_alice', 'staff_bob', 'staff_carol');
