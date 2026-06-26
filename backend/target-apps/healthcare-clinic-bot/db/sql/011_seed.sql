-- 011_seed.sql
-- Dev/test fixture data. ON CONFLICT DO NOTHING for idempotency.
-- Covers all 4 tables; respects FK order.

------------------------------------------------------------
-- USERS (5 rows — 1 admin per design §6.2, plus 4 extra staff/patient demos)
------------------------------------------------------------
INSERT INTO healthcare_clinic_bot.users (id, username, hashed_password, role, created_at)
VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'admin',
     '$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve',  -- bcrypt of 'changeme'
     'staff', '2024-01-10 08:00:00+00'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'dr.jones',
     '$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve',
     'staff', '2024-01-11 09:00:00+00'),
    ('a1b2c3d4-0003-4000-8000-000000000003', 'nurse.smith',
     '$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve',
     'staff', '2024-01-12 10:00:00+00'),
    ('a1b2c3d4-0004-4000-8000-000000000004', 'frontdesk.lee',
     '$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve',
     'staff', '2024-01-13 11:00:00+00'),
    ('a1b2c3d4-0005-4000-8000-000000000005', 'receptionist.garcia',
     '$2b$12$xGUxYzyVED7bFMAt1zPjjuMfUGu1RMGxWis97cfaJOXTJZgl7u3ve',
     'staff', '2024-01-14 12:00:00+00')
ON CONFLICT DO NOTHING;

------------------------------------------------------------
-- FAQ ENTRIES (8 rows across 3+ categories per design §6.2)
-- search_vector populated automatically by trigger
------------------------------------------------------------
INSERT INTO healthcare_clinic_bot.faq_entries (id, category, question, answer, is_active, created_at, updated_at)
VALUES
    (1, 'office_hours', 'What are the clinic''s office hours?',
     'We are open Monday through Friday from 8:00 AM to 6:00 PM and Saturday from 9:00 AM to 1:00 PM. We are closed on Sundays and federal holidays.',
     true, '2024-02-01 08:00:00+00', '2024-02-01 08:00:00+00'),
    (2, 'office_hours', 'Are you open on holidays?',
     'The clinic is closed on all major federal holidays including New Year''s Day, Memorial Day, Independence Day, Labor Day, Thanksgiving, and Christmas Day.',
     true, '2024-02-01 08:05:00+00', '2024-02-01 08:05:00+00'),
    (3, 'insurance', 'What insurance plans do you accept?',
     'We accept Blue Cross Blue Shield, Aetna, Cigna, UnitedHealthcare, and Medicare. Please call the front desk to verify your specific plan.',
     true, '2024-02-02 09:00:00+00', '2024-02-02 09:00:00+00'),
    (4, 'insurance', 'Do you accept Medicare?',
     'Yes, we are a Medicare-participating provider. Please bring your Medicare card to your appointment.',
     true, '2024-02-02 09:10:00+00', '2024-02-02 09:10:00+00'),
    (5, 'parking_booking', 'Where can I park when visiting the clinic?',
     'Free parking is available in the lot directly behind the building. Enter from Oak Street. Handicapped spaces are located near the rear entrance.',
     true, '2024-02-03 10:00:00+00', '2024-02-03 10:00:00+00'),
    (6, 'parking_booking', 'How do I book an appointment?',
     'You can book an appointment by calling (555) 123-4567 during office hours, or by using the patient portal at portal.exampleclinic.com. Walk-ins are accepted but appointments are preferred.',
     true, '2024-02-03 10:15:00+00', '2024-02-03 10:15:00+00'),
    (7, 'general', 'What should I bring to my first visit?',
     'Please bring a valid photo ID, your insurance card, a list of current medications, and any relevant medical records or referral letters from your previous physician.',
     true, '2024-02-04 11:00:00+00', '2024-02-04 11:00:00+00'),
    (8, 'general', 'What is the clinic''s cancellation policy?',
     'We require at least 24 hours notice for appointment cancellations. Late cancellations or no-shows may be subject to a $25 fee.',
     true, '2024-02-04 11:30:00+00', '2024-02-04 11:30:00+00')
ON CONFLICT DO NOTHING;

-- Reset the faq_entries sequence to avoid PK conflicts on future inserts
SELECT setval(pg_get_serial_sequence('healthcare_clinic_bot.faq_entries', 'id'),
              GREATEST((SELECT MAX(id) FROM healthcare_clinic_bot.faq_entries), 1));

------------------------------------------------------------
-- CHAT SESSIONS (5 rows)
------------------------------------------------------------
INSERT INTO healthcare_clinic_bot.chat_sessions (id, session_label, created_at)
VALUES
    ('b2c3d4e5-0001-4000-8000-000000000001', 'Demo: Office Hours Inquiry', '2024-03-01 14:00:00+00'),
    ('b2c3d4e5-0002-4000-8000-000000000002', 'Demo: Insurance Question', '2024-03-01 14:30:00+00'),
    ('b2c3d4e5-0003-4000-8000-000000000003', 'Demo: Parking Directions', '2024-03-02 09:00:00+00'),
    ('b2c3d4e5-0004-4000-8000-000000000004', 'Demo: Fallback Example', '2024-03-02 10:00:00+00'),
    ('b2c3d4e5-0005-4000-8000-000000000005', 'Demo: Multi-turn Conversation', '2024-03-03 11:00:00+00')
ON CONFLICT DO NOTHING;

------------------------------------------------------------
-- CHAT MESSAGES (10 rows — 2 per session: 1 user + 1 assistant)
------------------------------------------------------------
INSERT INTO healthcare_clinic_bot.chat_messages (session_id, role, content, is_fallback, created_at)
VALUES
    ('b2c3d4e5-0001-4000-8000-000000000001', 'user',
     'What are your office hours?', false, '2024-03-01 14:00:10+00'),
    ('b2c3d4e5-0001-4000-8000-000000000001', 'assistant',
     'We are open Monday through Friday from 8:00 AM to 6:00 PM and Saturday from 9:00 AM to 1:00 PM. This information is for general purposes only and is not medical advice.',
     false, '2024-03-01 14:00:14+00'),

    ('b2c3d4e5-0002-4000-8000-000000000002', 'user',
     'Do you accept Blue Cross?', false, '2024-03-01 14:30:05+00'),
    ('b2c3d4e5-0002-4000-8000-000000000002', 'assistant',
     'Yes, we accept Blue Cross Blue Shield along with Aetna, Cigna, UnitedHealthcare, and Medicare. This information is for general purposes only and is not medical advice.',
     false, '2024-03-01 14:30:09+00'),

    ('b2c3d4e5-0003-4000-8000-000000000003', 'user',
     'Where do I park?', false, '2024-03-02 09:00:05+00'),
    ('b2c3d4e5-0003-4000-8000-000000000003', 'assistant',
     'Free parking is available in the lot directly behind the building. Enter from Oak Street. This information is for general purposes only and is not medical advice.',
     false, '2024-03-02 09:00:09+00'),

    ('b2c3d4e5-0004-4000-8000-000000000004', 'user',
     'What is the dosage for ibuprofen?', false, '2024-03-02 10:00:05+00'),
    ('b2c3d4e5-0004-4000-8000-000000000004', 'assistant',
     'I don''t have information on that topic. For medical questions, please contact the clinic directly at (555) 123-4567. This information is for general purposes only and is not medical advice.',
     true, '2024-03-02 10:00:08+00'),

    ('b2c3d4e5-0005-4000-8000-000000000005', 'user',
     'Can I get an appointment on Saturday?', false, '2024-03-03 11:00:05+00'),
    ('b2c3d4e5-0005-4000-8000-000000000005', 'assistant',
     'We are open on Saturdays from 9:00 AM to 1:00 PM. You can book an appointment by calling (555) 123-4567. This information is for general purposes only and is not medical advice.',
     false, '2024-03-03 11:00:10+00')
ON CONFLICT DO NOTHING;
