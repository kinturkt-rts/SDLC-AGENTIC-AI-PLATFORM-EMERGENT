-- 007_seed.sql
-- Dev/test seed data for conference-speaker platform
-- Password for all seed users: "ConferencePass2024!"

-- ===================== USERS =====================
INSERT INTO users (id, username, email, password_hash, role, is_active) VALUES
    ('a1b2c3d4-0001-4000-a000-000000000001', 'admin', 'admin@example.com', '__BCRYPT_PLACEHOLDER__', 'admin', TRUE),
    ('a1b2c3d4-0002-4000-a000-000000000002', 'organizer1', 'organizer1@example.com', '__BCRYPT_PLACEHOLDER__', 'organizer', TRUE),
    ('a1b2c3d4-0003-4000-a000-000000000003', 'organizer2', 'organizer2@example.com', '__BCRYPT_PLACEHOLDER__', 'organizer', TRUE),
    ('a1b2c3d4-0004-4000-a000-000000000004', 'speaker1', 'speaker1@example.com', '__BCRYPT_PLACEHOLDER__', 'speaker', TRUE),
    ('a1b2c3d4-0005-4000-a000-000000000005', 'speaker2', 'speaker2@example.com', '__BCRYPT_PLACEHOLDER__', 'speaker', TRUE),
    ('a1b2c3d4-0006-4000-a000-000000000006', 'moderator1', 'moderator1@example.com', '__BCRYPT_PLACEHOLDER__', 'moderator', TRUE),
    ('a1b2c3d4-0007-4000-a000-000000000007', 'moderator2', 'moderator2@example.com', '__BCRYPT_PLACEHOLDER__', 'moderator', TRUE),
    ('a1b2c3d4-0008-4000-a000-000000000008', 'attendee1', 'attendee1@example.com', '__BCRYPT_PLACEHOLDER__', 'attendee', TRUE),
    ('a1b2c3d4-0009-4000-a000-000000000009', 'attendee2', 'attendee2@example.com', '__BCRYPT_PLACEHOLDER__', 'attendee', TRUE),
    ('a1b2c3d4-000a-4000-a000-00000000000a', 'attendee3', 'attendee3@example.com', '__BCRYPT_PLACEHOLDER__', 'attendee', TRUE)
ON CONFLICT DO NOTHING;

-- ===================== CONFERENCES =====================
INSERT INTO conferences (id, name, description, start_date, end_date, status) VALUES
    ('b1b2c3d4-0001-4000-b000-000000000001', 'TechConnect 2025', 'Annual technology conference featuring AI, cloud, and DevOps tracks.', '2025-06-15', '2025-06-18', 'draft'),
    ('b1b2c3d4-0002-4000-b000-000000000002', 'DevOps Summit 2025', 'A two-day summit focused on CI/CD, infrastructure as code, and platform engineering.', '2025-09-10', '2025-09-11', 'draft'),
    ('b1b2c3d4-0003-4000-b000-000000000003', 'Data Science Forum', 'Exploring latest trends in ML, data engineering, and analytics.', '2025-03-20', '2025-03-22', 'published'),
    ('b1b2c3d4-0004-4000-b000-000000000004', 'Cloud Native Day', 'Single-day event on Kubernetes, serverless, and microservices.', '2025-07-05', '2025-07-05', 'draft'),
    ('b1b2c3d4-0005-4000-b000-000000000005', 'Security Conference 2024', 'Past conference on cybersecurity and zero trust architecture.', '2024-11-01', '2024-11-03', 'archived')
ON CONFLICT DO NOTHING;

-- ===================== VENUES =====================
INSERT INTO venues (id, name, address, description) VALUES
    ('c1b2c3d4-0001-4000-c000-000000000001', 'Convention Center Downtown', '100 Main Street, Metropolis, ST 10001', 'Large multi-hall venue with modern AV facilities.'),
    ('c1b2c3d4-0002-4000-c000-000000000002', 'University Conference Hall', '500 Campus Drive, College Town, ST 20002', 'Academic venue with tiered lecture halls and breakout rooms.'),
    ('c1b2c3d4-0003-4000-c000-000000000003', 'Tech Hub Coworking', '250 Innovation Blvd, Silicon Heights, ST 30003', 'Modern coworking space with event areas.'),
    ('c1b2c3d4-0004-4000-c000-000000000004', 'Riverside Hotel & Events', '75 River Road, Riverside, ST 40004', 'Hotel ballroom and meeting rooms with catering.'),
    ('c1b2c3d4-0005-4000-c000-000000000005', 'City Arts Center', '12 Gallery Lane, Downtown, ST 50005', 'Cultural center with flexible event spaces.')
ON CONFLICT DO NOTHING;

-- ===================== ROOMS =====================
INSERT INTO rooms (id, venue_id, name, capacity) VALUES
    ('d1b2c3d4-0001-4000-d000-000000000001', 'c1b2c3d4-0001-4000-c000-000000000001', 'Grand Hall A', 500),
    ('d1b2c3d4-0002-4000-d000-000000000002', 'c1b2c3d4-0001-4000-c000-000000000001', 'Breakout Room 1', 50),
    ('d1b2c3d4-0003-4000-d000-000000000003', 'c1b2c3d4-0001-4000-c000-000000000001', 'Breakout Room 2', 100),
    ('d1b2c3d4-0004-4000-d000-000000000004', 'c1b2c3d4-0002-4000-c000-000000000002', 'Lecture Hall 101', 200),
    ('d1b2c3d4-0005-4000-d000-000000000005', 'c1b2c3d4-0002-4000-c000-000000000002', 'Seminar Room A', 40),
    ('d1b2c3d4-0006-4000-d000-000000000006', 'c1b2c3d4-0003-4000-c000-000000000003', 'Open Event Space', 150),
    ('d1b2c3d4-0007-4000-d000-000000000007', 'c1b2c3d4-0004-4000-c000-000000000004', 'Ballroom', 300),
    ('d1b2c3d4-0008-4000-d000-000000000008', 'c1b2c3d4-0004-4000-c000-000000000004', 'Meeting Room B', 30),
    ('d1b2c3d4-0009-4000-d000-000000000009', 'c1b2c3d4-0005-4000-c000-000000000005', 'Gallery Space', 80),
    ('d1b2c3d4-000a-4000-d000-00000000000a', 'c1b2c3d4-0005-4000-c000-000000000005', 'Workshop Room', 25)
ON CONFLICT DO NOTHING;

-- ===================== SPEAKERS =====================
INSERT INTO speakers (id, user_id, name, bio, photo_url, contact_email) VALUES
    ('e1b2c3d4-0001-4000-e000-000000000001', 'a1b2c3d4-0004-4000-a000-000000000004', 'Dr. Sarah Chen', 'AI researcher with 15 years of experience in NLP and machine learning. Published over 40 papers.', 'https://example.com/photos/sarah-chen.jpg', 'sarah.chen@university.edu'),
    ('e1b2c3d4-0002-4000-e000-000000000002', 'a1b2c3d4-0005-4000-a000-000000000005', 'Marcus Williams', 'Cloud architect and DevOps evangelist. AWS Solutions Architect Professional certified.', 'https://example.com/photos/marcus-williams.jpg', 'marcus.w@techcorp.io'),
    ('e1b2c3d4-0003-4000-e000-000000000003', NULL, 'Priya Patel', 'Full-stack engineer specializing in React and Node.js. Open-source contributor to several major frameworks.', 'https://example.com/photos/priya-patel.jpg', 'priya@devstudio.com'),
    ('e1b2c3d4-0004-4000-e000-000000000004', NULL, 'James O''Brien', 'Cybersecurity expert and former penetration tester. Author of "Secure by Design" workshop series.', 'https://example.com/photos/james-obrien.jpg', 'james.obrien@securityfirm.net'),
    ('e1b2c3d4-0005-4000-e000-000000000005', NULL, 'Aisha Mohammed', 'Data engineering lead with experience building petabyte-scale pipelines. Speaker at 20+ conferences.', 'https://example.com/photos/aisha-m.jpg', 'aisha.m@datacompany.com'),
    ('e1b2c3d4-0006-4000-e000-000000000006', NULL, 'Tom Nakamura', 'Platform engineer and Kubernetes expert. Maintains several CNCF projects.', 'https://example.com/photos/tom-n.jpg', 'tom.nakamura@cloudnative.org')
ON CONFLICT DO NOTHING;

-- ===================== PROPOSALS =====================
INSERT INTO proposals (id, speaker_id, title, abstract, topic_tags, preferred_duration, av_requirements, status) VALUES
    ('f1b2c3d4-0001-4000-f000-000000000001', 'e1b2c3d4-0001-4000-e000-000000000001', 'Transformers in Production: Lessons from Large-Scale NLP', 'This talk covers practical challenges deploying transformer models at scale including latency optimization, model serving, and monitoring.', '["AI", "NLP", "MLOps"]'::jsonb, 45, 'Projector, lapel mic, screen sharing support', 'accepted'),
    ('f1b2c3d4-0002-4000-f000-000000000002', 'e1b2c3d4-0002-4000-e000-000000000002', 'Zero-Downtime Deployments with Kubernetes', 'Deep dive into blue-green, canary, and rolling deployment strategies using Kubernetes native features.', '["DevOps", "Kubernetes", "Cloud"]'::jsonb, 60, 'Projector, internet access for live demo', 'accepted'),
    ('f1b2c3d4-0003-4000-f000-000000000003', 'e1b2c3d4-0003-4000-e000-000000000003', 'Building Accessible React Applications', 'Workshop on implementing WCAG 2.1 AA compliance in React apps using aria attributes and semantic HTML.', '["Frontend", "React", "Accessibility"]'::jsonb, 90, 'Projector, whiteboard, participant laptops', 'pending'),
    ('f1b2c3d4-0004-4000-f000-000000000004', 'e1b2c3d4-0004-4000-e000-000000000004', 'Threat Modeling for Modern Web Applications', 'Introduction to STRIDE methodology applied to microservice architectures with hands-on exercises.', '["Security", "Architecture", "Web"]'::jsonb, 60, 'Projector, whiteboard', 'pending'),
    ('f1b2c3d4-0005-4000-f000-000000000005', 'e1b2c3d4-0005-4000-e000-000000000005', 'Real-Time Data Pipelines with Apache Kafka', 'Architecture patterns for building fault-tolerant streaming pipelines processing millions of events per second.', '["Data Engineering", "Kafka", "Streaming"]'::jsonb, 45, 'Projector, internet access', 'pending'),
    ('f1b2c3d4-0006-4000-f000-000000000006', 'e1b2c3d4-0006-4000-e000-000000000006', 'Service Mesh Demystified', 'Comparing Istio, Linkerd, and Consul Connect for production microservices networking.', '["Cloud Native", "Service Mesh", "Networking"]'::jsonb, 45, 'Projector', 'accepted'),
    ('f1b2c3d4-0007-4000-f000-000000000007', 'e1b2c3d4-0001-4000-e000-000000000001', 'Ethics in AI: Building Responsible Systems', 'A framework for identifying and mitigating bias in ML systems with case studies from industry.', '["AI", "Ethics", "Responsible AI"]'::jsonb, 30, 'Projector, lapel mic', 'pending')
ON CONFLICT DO NOTHING;

-- ===================== SESSIONS =====================
INSERT INTO sessions (id, conference_id, proposal_id, title, description, duration_minutes, status) VALUES
    ('00aabb01-0001-4000-a000-000000000001', 'b1b2c3d4-0003-4000-b000-000000000003', 'f1b2c3d4-0001-4000-f000-000000000001', 'Transformers in Production: Lessons from Large-Scale NLP', 'Practical session on deploying transformer models at enterprise scale.', 45, 'published'),
    ('00aabb01-0002-4000-a000-000000000002', 'b1b2c3d4-0003-4000-b000-000000000003', 'f1b2c3d4-0002-4000-f000-000000000002', 'Zero-Downtime Deployments with Kubernetes', 'Learn blue-green and canary deployments with live demo.', 60, 'published'),
    ('00aabb01-0003-4000-a000-000000000003', 'b1b2c3d4-0001-4000-b000-000000000001', NULL, 'Opening Keynote: Future of Tech', 'Welcome address and keynote for TechConnect 2025.', 30, 'draft'),
    ('00aabb01-0004-4000-a000-000000000004', 'b1b2c3d4-0001-4000-b000-000000000001', NULL, 'Panel: Cloud vs On-Premise in 2025', 'Expert panel discussion on infrastructure decisions for modern enterprises.', 60, 'draft'),
    ('00aabb01-0005-4000-a000-000000000005', 'b1b2c3d4-0003-4000-b000-000000000003', 'f1b2c3d4-0006-4000-f000-000000000006', 'Service Mesh Demystified', 'Comparing modern service mesh solutions for production use.', 45, 'accepted'),
    ('00aabb01-0006-4000-a000-000000000006', 'b1b2c3d4-0001-4000-b000-000000000001', NULL, 'Workshop: Hands-on with Terraform', 'Interactive workshop on infrastructure as code with Terraform.', 120, 'draft'),
    ('00aabb01-0007-4000-a000-000000000007', 'b1b2c3d4-0002-4000-b000-000000000002', NULL, 'CI/CD Best Practices', 'Overview of modern CI/CD pipeline architectures.', 45, 'draft')
ON CONFLICT DO NOTHING;

-- ===================== SCHEDULE ENTRIES =====================
INSERT INTO schedule_entries (id, session_id, conference_id, room_id, start_time, end_time) VALUES
    ('00ccdd01-0001-4000-c000-000000000001', '00aabb01-0001-4000-a000-000000000001', 'b1b2c3d4-0003-4000-b000-000000000003', 'd1b2c3d4-0004-4000-d000-000000000004', '2025-03-20 09:00:00+00', '2025-03-20 09:45:00+00'),
    ('00ccdd01-0002-4000-c000-000000000002', '00aabb01-0002-4000-a000-000000000002', 'b1b2c3d4-0003-4000-b000-000000000003', 'd1b2c3d4-0004-4000-d000-000000000004', '2025-03-20 10:00:00+00', '2025-03-20 11:00:00+00'),
    ('00ccdd01-0003-4000-c000-000000000003', '00aabb01-0005-4000-a000-000000000005', 'b1b2c3d4-0003-4000-b000-000000000003', 'd1b2c3d4-0005-4000-d000-000000000005', '2025-03-20 09:00:00+00', '2025-03-20 09:45:00+00'),
    ('00ccdd01-0004-4000-c000-000000000004', '00aabb01-0003-4000-a000-000000000003', 'b1b2c3d4-0001-4000-b000-000000000001', 'd1b2c3d4-0001-4000-d000-000000000001', '2025-06-15 09:00:00+00', '2025-06-15 09:30:00+00'),
    ('00ccdd01-0005-4000-c000-000000000005', '00aabb01-0004-4000-a000-000000000004', 'b1b2c3d4-0001-4000-b000-000000000001', 'd1b2c3d4-0001-4000-d000-000000000001', '2025-06-15 10:00:00+00', '2025-06-15 11:00:00+00')
ON CONFLICT DO NOTHING;

-- ===================== SESSION SPEAKERS =====================
INSERT INTO session_speakers (session_id, speaker_id) VALUES
    ('00aabb01-0001-4000-a000-000000000001', 'e1b2c3d4-0001-4000-e000-000000000001'),
    ('00aabb01-0002-4000-a000-000000000002', 'e1b2c3d4-0002-4000-e000-000000000002'),
    ('00aabb01-0005-4000-a000-000000000005', 'e1b2c3d4-0006-4000-e000-000000000006'),
    ('00aabb01-0004-4000-a000-000000000004', 'e1b2c3d4-0001-4000-e000-000000000001'),
    ('00aabb01-0004-4000-a000-000000000004', 'e1b2c3d4-0002-4000-e000-000000000002'),
    ('00aabb01-0003-4000-a000-000000000003', 'e1b2c3d4-0005-4000-e000-000000000005')
ON CONFLICT DO NOTHING;

-- ===================== SESSION MODERATORS =====================
INSERT INTO session_moderators (session_id, user_id) VALUES
    ('00aabb01-0001-4000-a000-000000000001', 'a1b2c3d4-0006-4000-a000-000000000006'),
    ('00aabb01-0002-4000-a000-000000000002', 'a1b2c3d4-0007-4000-a000-000000000007'),
    ('00aabb01-0005-4000-a000-000000000005', 'a1b2c3d4-0006-4000-a000-000000000006'),
    ('00aabb01-0003-4000-a000-000000000003', 'a1b2c3d4-0007-4000-a000-000000000007'),
    ('00aabb01-0004-4000-a000-000000000004', 'a1b2c3d4-0006-4000-a000-000000000006')
ON CONFLICT DO NOTHING;

-- ===================== ATTENDANCE RECORDS =====================
INSERT INTO attendance_records (id, session_id, count, recorded_by, recorded_at) VALUES
    ('00eeff01-0001-4000-e000-000000000001', '00aabb01-0001-4000-a000-000000000001', 145, 'a1b2c3d4-0006-4000-a000-000000000006', '2025-03-20 09:50:00+00'),
    ('00eeff01-0002-4000-e000-000000000002', '00aabb01-0002-4000-a000-000000000002', 180, 'a1b2c3d4-0007-4000-a000-000000000007', '2025-03-20 11:05:00+00'),
    ('00eeff01-0003-4000-e000-000000000003', '00aabb01-0005-4000-a000-000000000005', 35, 'a1b2c3d4-0006-4000-a000-000000000006', '2025-03-20 09:50:00+00'),
    ('00eeff01-0004-4000-e000-000000000004', '00aabb01-0001-4000-a000-000000000001', 150, 'a1b2c3d4-0002-4000-a000-000000000002', '2025-03-20 09:52:00+00'),
    ('00eeff01-0005-4000-e000-000000000005', '00aabb01-0002-4000-a000-000000000002', 195, 'a1b2c3d4-0002-4000-a000-000000000002', '2025-03-20 11:10:00+00')
ON CONFLICT DO NOTHING;
