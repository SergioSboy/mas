"""Held-out evaluator. Gold SQL is never sent to the agents or the critic."""
import math
from .tools import query

# Independently formulated SQL. Order does not matter, numeric tolerance is 1e-6.
GOLD = {
 'T1': "SELECT to_char(date_trunc('month',date),'YYYY-MM') label, SUM(total) value FROM orders WHERE status='completed' GROUP BY to_char(date_trunc('month',date),'YYYY-MM')",
 'T2': "SELECT category label, SUM(quantity*price) value FROM items WHERE order_id IN (SELECT id FROM orders WHERE status='completed') GROUP BY category",
 'T3': "SELECT region label, SUM(total)*1.0/COUNT(*) value FROM customers, orders WHERE customers.id=customer_id AND status='completed' GROUP BY region",
 'T4': "SELECT region label, COUNT(*) value FROM customers WHERE id IN (SELECT customer_id FROM orders WHERE status='completed') GROUP BY region",
 'T5': "SELECT 'Всего' label, SUM(total) value FROM orders WHERE status IN ('completed')",
 'T6': "SELECT region label, AVG(CASE WHEN EXISTS(SELECT 1 FROM returns r WHERE r.order_id=o.id) THEN 1.0 ELSE 0.0 END) value FROM orders o JOIN customers c ON c.id=o.customer_id WHERE status='completed' GROUP BY region"
}


def assess(db, task, state, require_complete=False):
    expected=query(db,GOLD[task['id']])
    actual=state.get('rows',[])
    expected=sorted(expected,key=lambda r:r['label'])
    actual=sorted(actual,key=lambda r:r['label'])
    numeric=len(actual)==len(expected) and all(a['label']==b['label'] and math.isclose(a['value'],b['value'],rel_tol=1e-6,abs_tol=1e-6) for a,b in zip(actual,expected))
    report=state.get('report',{})
    chart=report.get('chart')==task['chart']
    # Numeric claim is validated by the shared reporting tool. Prose still needs manual review.
    complete=bool(report.get('summary')) and bool(report.get('claim'))
    return dict(success=bool(numeric and chart and complete and (not require_complete or state.get('completed',False))),table_correct=numeric,chart_correct=chart,report_present=complete,expected=expected)
