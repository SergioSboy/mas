-- These are disposable local demo credentials, not production credentials.
CREATE ROLE salesbench_reader LOGIN PASSWORD 'demo_reader'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE salesbench FROM PUBLIC;
GRANT CONNECT ON DATABASE salesbench TO salesbench_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE salesbench_reader SET default_transaction_read_only = on;
ALTER ROLE salesbench_reader SET search_path = salesbench, pg_catalog;
