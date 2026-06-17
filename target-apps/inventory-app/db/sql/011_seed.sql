-- 011_seed.sql
-- Inventory Desk DEV-ONLY seed data.
-- Per design §6.2 + FR-10: seeds two users (admin/Admin123!, staff/Staff123!)
-- with bcrypt-hashed passwords. Additional categories, products, and stock
-- movements are inserted to populate every §3 table for local development
-- and QA fixtures (5-10 rows per table per Context). ROTATE BEFORE PRODUCTION.
--
-- NOTE: bcrypt hashes below were generated with `bcrypt` cost=12.
--       Dev-only fixtures — NEVER use these in production.

SET search_path TO inventory_app;

-- ---------------------------------------------------------------------------
-- USERS  (stable UUIDs so dev/test code can reference them)
-- ---------------------------------------------------------------------------
INSERT INTO inventory_app.users (id, username, password_hash, role, is_active)
VALUES
    ('11111111-1111-1111-1111-111111111111',
     'admin',
     '$2b$12$OjWI13flUsRs1v3My7gcCe/VfXJTswBhGHf9slrYILtNKd3wvSDVW',
     'admin', true),
    ('22222222-2222-2222-2222-222222222222',
     'staff',
     '$2b$12$D85QqslNti5gnzmPxclL6eu7HqACPRVWN/kx3MQQxKFQRjTCUCG2u',
     'staff', true),
    ('33333333-3333-3333-3333-333333333333',
     'staff_alice',
     '$2b$12$D85QqslNti5gnzmPxclL6eu7HqACPRVWN/kx3MQQxKFQRjTCUCG2u',
     'staff', true),
    ('44444444-4444-4444-4444-444444444444',
     'staff_bob',
     '$2b$12$D85QqslNti5gnzmPxclL6eu7HqACPRVWN/kx3MQQxKFQRjTCUCG2u',
     'staff', true),
    ('55555555-5555-5555-5555-555555555555',
     'staff_carol',
     '$2b$12$D85QqslNti5gnzmPxclL6eu7HqACPRVWN/kx3MQQxKFQRjTCUCG2u',
     'staff', false)
ON CONFLICT (username) DO NOTHING;

-- ---------------------------------------------------------------------------
-- CATEGORIES  (stable UUIDs for FK reference below)
-- ---------------------------------------------------------------------------
INSERT INTO inventory_app.categories (id, name, slug)
VALUES
    ('aaaaaaa1-0000-0000-0000-000000000001', 'Electronics',     'electronics'),
    ('aaaaaaa1-0000-0000-0000-000000000002', 'Office Supplies', 'office-supplies'),
    ('aaaaaaa1-0000-0000-0000-000000000003', 'Hardware',        'hardware'),
    ('aaaaaaa1-0000-0000-0000-000000000004', 'Apparel',         'apparel'),
    ('aaaaaaa1-0000-0000-0000-000000000005', 'Beverages',       'beverages')
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- PRODUCTS  (mix of normal stock and low_stock <= 5 for FR-6 testing)
-- ---------------------------------------------------------------------------
INSERT INTO inventory_app.products (id, category_id, sku, name, unit_price, qty_on_hand)
VALUES
    ('bbbbbbb1-0000-0000-0000-000000000001',
     'aaaaaaa1-0000-0000-0000-000000000001',
     'ELEC-USB-001', 'USB-C Charger 30W', 19.99, 50),
    ('bbbbbbb1-0000-0000-0000-000000000002',
     'aaaaaaa1-0000-0000-0000-000000000001',
     'ELEC-HDP-002', 'HDMI Cable 2m',      9.50,  3),   -- low stock
    ('bbbbbbb1-0000-0000-0000-000000000003',
     'aaaaaaa1-0000-0000-0000-000000000002',
     'OFFC-PEN-010', 'Ballpoint Pen Pack', 4.25, 120),
    ('bbbbbbb1-0000-0000-0000-000000000004',
     'aaaaaaa1-0000-0000-0000-000000000002',
     'OFFC-PAD-011', 'A4 Notepad',         2.75,  5),   -- low stock boundary
    ('bbbbbbb1-0000-0000-0000-000000000005',
     'aaaaaaa1-0000-0000-0000-000000000003',
     'HARD-SCR-100', 'Screwdriver Set',   24.00, 18),
    ('bbbbbbb1-0000-0000-0000-000000000006',
     'aaaaaaa1-0000-0000-0000-000000000003',
     'HARD-NLS-101', 'Nails 1kg Box',      6.80, 45),
    ('bbbbbbb1-0000-0000-0000-000000000007',
     'aaaaaaa1-0000-0000-0000-000000000004',
     'APPR-TSH-200', 'Cotton T-Shirt L',  12.00,  2),   -- low stock
    ('bbbbbbb1-0000-0000-0000-000000000008',
     'aaaaaaa1-0000-0000-0000-000000000005',
     'BEVR-COF-300', 'Ground Coffee 250g', 8.99, 30)
ON CONFLICT (sku) DO NOTHING;

-- ---------------------------------------------------------------------------
-- STOCK MOVEMENTS  (history per FR-8; reasons cover all enum values)
-- created_at staggered so DESC ordering can be verified in tests.
-- ---------------------------------------------------------------------------
INSERT INTO inventory_app.stock_movements
    (id, product_id, delta, reason, note, performed_by, created_at)
VALUES
    ('ccccccc1-0000-0000-0000-000000000001',
     'bbbbbbb1-0000-0000-0000-000000000001',
      50, 'restock', 'Initial stock load',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '7 days'),
    ('ccccccc1-0000-0000-0000-000000000002',
     'bbbbbbb1-0000-0000-0000-000000000002',
      10, 'restock', 'Cable replenishment',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '6 days'),
    ('ccccccc1-0000-0000-0000-000000000003',
     'bbbbbbb1-0000-0000-0000-000000000002',
      -7, 'sale',    'Bulk sale to office tenant',
     '22222222-2222-2222-2222-222222222222',
     now() - interval '4 days'),
    ('ccccccc1-0000-0000-0000-000000000004',
     'bbbbbbb1-0000-0000-0000-000000000003',
     120, 'restock', 'Quarterly pen order',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '5 days'),
    ('ccccccc1-0000-0000-0000-000000000005',
     'bbbbbbb1-0000-0000-0000-000000000004',
      10, 'restock', 'Notepad restock',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '3 days'),
    ('ccccccc1-0000-0000-0000-000000000006',
     'bbbbbbb1-0000-0000-0000-000000000004',
      -5, 'sale',    'Sold to walk-in',
     '33333333-3333-3333-3333-333333333333',
     now() - interval '2 days'),
    ('ccccccc1-0000-0000-0000-000000000007',
     'bbbbbbb1-0000-0000-0000-000000000005',
      20, 'restock', 'Tools delivery',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '4 days'),
    ('ccccccc1-0000-0000-0000-000000000008',
     'bbbbbbb1-0000-0000-0000-000000000005',
      -2, 'adjustment', 'Damaged in transit',
     '44444444-4444-4444-4444-444444444444',
     now() - interval '1 day'),
    ('ccccccc1-0000-0000-0000-000000000009',
     'bbbbbbb1-0000-0000-0000-000000000007',
      -3, 'sale',    'Counter sale',
     '22222222-2222-2222-2222-222222222222',
     now() - interval '12 hours'),
    ('ccccccc1-0000-0000-0000-000000000010',
     'bbbbbbb1-0000-0000-0000-000000000008',
      30, 'restock', 'Coffee resupply',
     '11111111-1111-1111-1111-111111111111',
     now() - interval '6 hours')
ON CONFLICT (id) DO NOTHING;
