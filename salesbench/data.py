"""Reproducible PostgreSQL fixture and public task contracts."""
import datetime
import psycopg
from psycopg import sql
from .database import Database

SCHEMA = """customers(id INTEGER PRIMARY KEY, region TEXT NOT NULL);
orders(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), date DATE NOT NULL, status TEXT NOT NULL, total NUMERIC(12,2) NOT NULL);
items(order_id INTEGER REFERENCES orders(id), category TEXT NOT NULL, quantity INTEGER NOT NULL, price NUMERIC(12,2) NOT NULL);
returns(order_id INTEGER REFERENCES orders(id), reason TEXT NOT NULL);"""
RULES = '''Диалект SQL: PostgreSQL 14+. Поле orders.date имеет тип DATE.
Выручка и средний чек считаются только по status='completed'.
items может содержать несколько строк на заказ. returns может содержать несколько
причин на один заказ. Доля возвратов = число уникальных завершённых заказов с
хотя бы одной причиной возврата / число уникальных завершённых заказов.
SQL должен возвращать ровно две колонки label (текст) и value (число).
Сортировка строк не оценивается. Итоговые числа не округляй в SQL.'''
TASKS = [
    dict(id='T1', question='Покажи выручку завершённых заказов по месяцам.', chart='line'),
    dict(id='T2', question='Покажи выручку по категориям товаров завершённых заказов.', chart='bar'),
    dict(id='T3', question='Найди средний чек завершённых заказов по регионам.', chart='bar'),
    dict(id='T4', question='Посчитай уникальных покупателей с завершёнными заказами по регионам.', chart='bar'),
    dict(id='T5', question='Покажи общую выручку только завершённых заказов.', chart='bar'),
    dict(id='T6', question='Покажи долю возвратов завершённых заказов по регионам. Не считай один заказ дважды.', chart='bar'),
]


def fixture_rows():
    rows={'customers':[(i,['Москва','Казань','Тула'][(i-1)%3]) for i in range(1,7)],'orders':[],'items':[],'returns':[]}
    for i in range(1,49):
        month=1+(i-1)//16
        qty,price=1+i%3,100+25*(i%5)
        extra=50+10*(i%4)
        rows['orders'].append((i,1+(i-1)%6,datetime.date(2026,month,1+(i-1)%16),'cancelled' if i%7==0 else 'completed',qty*price+extra))
        rows['items'].extend([(i,'Техника' if i%2 else 'Книги',qty,price),(i,'Аксессуары',1,extra)])
        if i%5==0:
            rows['returns'].append((i,'повреждение'))
            if i%10==0:
                rows['returns'].append((i,'комплектация'))
    return rows


def create_database(admin_dsn, schema='salesbench', reader_role='salesbench_reader'):
    """Create a NEW dedicated schema, never drop or overwrite existing user data.

    Database and reader login are provisioned by Docker bootstrap or by an admin.
    Returns False for an existing schema, leaving it untouched.
    """
    with psycopg.connect(admin_dsn,connect_timeout=5) as db:
        if db.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(schema,)).fetchone():
            return False
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        db.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(sql.Identifier(schema)))
        for definition in SCHEMA.split(';'):
            if definition.strip():
                db.execute('CREATE TABLE '+definition)
        for table,rows in fixture_rows().items():
            with db.cursor() as cursor:
                cursor.executemany(sql.SQL('INSERT INTO {} VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(sql.Placeholder() for _ in rows[0])),rows)
        db.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(reader_role)))
        db.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(reader_role)))
    return True


def bootstrap_sql():
    """Export the same fixture used in tests as a Docker initialization script."""
    statements=['-- Generated fixture. Runs only on a new Docker volume.','BEGIN;','CREATE SCHEMA salesbench;','SET LOCAL search_path TO salesbench, pg_catalog;']
    statements += ['CREATE TABLE '+d.strip()+';' for d in SCHEMA.split(';') if d.strip()]
    for table,rows in fixture_rows().items():
        for row in rows:
            values=','.join(sql.Literal(v).as_string() for v in row)
            statements.append(f'INSERT INTO {table} VALUES ({values});')
    statements += ['GRANT USAGE ON SCHEMA salesbench TO salesbench_reader;','GRANT SELECT ON ALL TABLES IN SCHEMA salesbench TO salesbench_reader;','COMMIT;']
    return '\n'.join(statements)+'\n'
