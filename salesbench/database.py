"""PostgreSQL connections. Credentials are never written to result files."""
import os
from dataclasses import dataclass,field
import psycopg
from psycopg import sql

DEFAULT_READER_URL='postgresql://salesbench_reader:demo_reader@127.0.0.1:55432/salesbench'
DEFAULT_ADMIN_URL='postgresql://salesbench_owner:demo_owner@127.0.0.1:55432/salesbench'

@dataclass(frozen=True)
class Database:
    dsn: str=field(repr=False)
    schema: str='salesbench'

    @classmethod
    def from_env(cls):
        return cls(os.getenv('DATABASE_URL',DEFAULT_READER_URL))


def database_info(database):
    with psycopg.connect(database.dsn,connect_timeout=5) as db:
        db.read_only=True
        db.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(sql.Identifier(database.schema)))
        version=db.execute('SHOW server_version').fetchone()[0]
        counts=db.execute('SELECT (SELECT COUNT(*) FROM orders), (SELECT COUNT(*) FROM customers)').fetchone()
        return dict(engine='PostgreSQL',version=version,schema=database.schema,orders=counts[0],customers=counts[1])
