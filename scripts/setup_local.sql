-- Run once with psql as the administrator of your local PostgreSQL installation.
-- Creates a dedicated demo database and logins. Existing passwords are not reset.
\set ON_ERROR_STOP on
SELECT 'CREATE ROLE salesbench_owner LOGIN PASSWORD ''demo_owner'' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='salesbench_owner')
\gexec
SELECT 'CREATE ROLE salesbench_reader LOGIN PASSWORD ''demo_reader'' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='salesbench_reader')
\gexec
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_database WHERE datname='salesbench'
             AND pg_get_userbyid(datdba)<>'salesbench_owner') THEN
    RAISE EXCEPTION 'Database salesbench has a different owner. Existing database was left untouched.';
  END IF;
END $$;
SELECT 'CREATE DATABASE salesbench OWNER salesbench_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='salesbench')
\gexec
\connect salesbench
REVOKE ALL ON DATABASE salesbench FROM PUBLIC;
GRANT CONNECT ON DATABASE salesbench TO salesbench_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE salesbench_reader SET default_transaction_read_only=on;
ALTER ROLE salesbench_reader SET search_path=salesbench,pg_catalog;
