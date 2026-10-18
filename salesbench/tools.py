import html
import math
from decimal import Decimal
import psycopg
from psycopg import sql as pgsql


def query(database, sql, timeout=2):
    """Real PostgreSQL, reader role, read-only transaction and server timeout.

    Execute one prepared SELECT subquery, cap results on the server, convert
    PostgreSQL NUMERIC values to JSON-compatible numbers at the tool boundary.
    """
    if not isinstance(sql,str) or not sql.lstrip().lower().startswith(('select','with')):
        raise ValueError('Разрешён только SELECT или WITH')
    statement=sql.strip().removesuffix(';')
    with psycopg.connect(database.dsn,connect_timeout=5) as db:
        db.read_only=True
        db.execute(pgsql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(pgsql.Identifier(database.schema)))
        db.execute("SELECT set_config('statement_timeout', %s, true)",(str(max(1,int(timeout*1000))),))
        with db.cursor() as cursor:
            cursor.execute('SELECT * FROM ('+statement+') AS sb_result LIMIT 501',prepare=True)
            if [column.name for column in cursor.description] != ['label','value']:
                raise ValueError('Нужны колонки label, value в этом порядке')
            rows=cursor.fetchmany(501)
        if len(rows)>500:
            raise ValueError('Лимит 500 строк')
        if not rows or any(isinstance(v,bool) or not isinstance(v,(int,float,Decimal)) or not math.isfinite(v) for _,v in rows):
            raise ValueError('Нужны непустые конечные числовые результаты')
        return [dict(label=str(k),value=float(v) if isinstance(v,Decimal) else v) for k,v in rows]


def statistics(rows):
    best=max(rows,key=lambda x:x['value'])
    vals=[x['value'] for x in rows]
    return dict(count=len(rows),sum=sum(vals),mean=sum(vals)/len(vals),minimum=min(vals),maximum=max(vals),leader=best)


def make_report(rows, payload):
    chart=payload.get('chart')
    if chart not in ('bar','line'):
        raise ValueError('chart должен быть bar или line')
    summary=payload.get('summary','')
    if not isinstance(summary,str) or len(summary.strip())<10:
        raise ValueError('Нужна краткая текстовая сводка')
    claim=payload.get('claim',{})
    if not any(str(r['label'])==str(claim.get('label')) and isinstance(claim.get('value'),(int,float)) and math.isclose(r['value'],claim['value'],rel_tol=1e-6,abs_tol=1e-6) for r in rows):
        raise ValueError('Числовое утверждение сводки не подтверждено таблицей')
    return dict(summary=summary,claim=claim,chart=chart,statistics=statistics(rows))


def chart_svg(rows, kind):
    """A data chart for the local report, with labels and values, no external CDN."""
    rows=sorted(rows,key=lambda r:r['label']) if kind=='line' else rows
    maximum=max((abs(r['value']) for r in rows),default=1) or 1
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 270" role="img" aria-label="График результата">']
    points=[]
    for i,r in enumerate(rows):
        x=70+i*560/max(len(rows),1)
        y=220-r['value']/maximum*160
        if kind=='bar':
            parts.append(f'<rect x="{x}" y="{y}" width="{min(75,400/max(len(rows),1))}" height="{220-y}" fill="#147D92"/>')
        else:
            points.append(f'{x},{y}')
            parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#147D92"/>')
        parts.append(f'<text x="{x}" y="{y-10}" font-size="14">{r["value"]:.3f}</text><text x="{x}" y="245" font-size="13">{html.escape(r["label"])}</text>')
    if points:
        parts.append('<polyline points="'+' '.join(points)+'" fill="none" stroke="#147D92" stroke-width="3"/>')
    return ''.join(parts)+'</svg>'
