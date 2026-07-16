-- Migration 001: Create departments and job_roles tables
-- Schema: training_compliance

CREATE SCHEMA IF NOT EXISTS training_compliance;

CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS job_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL
);
