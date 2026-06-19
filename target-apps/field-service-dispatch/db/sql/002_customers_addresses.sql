-- Migration 002: customers and service_addresses tables
-- Schema: field_service_dispatch

CREATE TABLE IF NOT EXISTS field_service_dispatch.customers (
    id UUID PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customers_is_active
    ON field_service_dispatch.customers (is_active);

CREATE TABLE IF NOT EXISTS field_service_dispatch.service_addresses (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES field_service_dispatch.customers(id),
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    postal_code TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_service_addresses_customer_id
    ON field_service_dispatch.service_addresses (customer_id);
