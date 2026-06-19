-- Repair dev seed bcrypt when 011_seed.sql used __BCRYPT_PLACEHOLDER__.
-- Password: AssetPass123!

SET search_path TO it_asset_lifecycle, public;

UPDATE it_asset_lifecycle.users
SET password_hash = '$2b$12$OMB3ODJ1T3V02PmiyuyBpe2aGE6/UddAdZVeaMpg83qiqLbY5iNDe'
WHERE username IN ('kevin_admin', 'sarah_staff', 'mike_staff', 'dana_finance');
