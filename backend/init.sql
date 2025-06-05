-- Library Management System Database Initialization
-- This file is executed when PostgreSQL container starts for the first time

-- Create database if it doesn't exist (PostgreSQL will use POSTGRES_DB env var)
-- Additional initialization can be added here if needed

-- Set timezone
SET timezone = 'UTC';

-- Create extensions if needed
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log initialization
SELECT 'Library Management System database initialized successfully' AS status;