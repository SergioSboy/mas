"""Public baseline templates. Demo responses reuse these, not evaluator gold."""
TEMPLATES = {
 'monthly': "SELECT to_char(date,'YYYY-MM') AS label, SUM(total) AS value FROM orders WHERE status='completed' GROUP BY label",
 'category': "SELECT i.category AS label, SUM(i.quantity*i.price) AS value FROM items i JOIN orders o ON o.id=i.order_id WHERE o.status='completed' GROUP BY i.category",
 'average': "SELECT c.region AS label, AVG(o.total) AS value FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.status='completed' GROUP BY c.region",
 'customers': "SELECT c.region AS label, COUNT(DISTINCT o.customer_id) AS value FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.status='completed' GROUP BY c.region",
 'total': "SELECT 'Всего' AS label, SUM(total) AS value FROM orders WHERE status='completed'",
 'returns': "SELECT c.region AS label, 1.0*COUNT(DISTINCT CASE WHEN r.order_id IS NOT NULL THEN o.id END)/COUNT(DISTINCT o.id) AS value FROM orders o JOIN customers c ON c.id=o.customer_id LEFT JOIN returns r ON r.order_id=o.id WHERE o.status='completed' GROUP BY c.region"
}


def intent(question):
    q = question.lower()
    for word, name in [('долю возвратов','returns'),('средний чек','average'),('уникальных покупателей','customers'),('категориям','category'),('месяцам','monthly'),('общую выручку','total')]:
        if word in q:
            return name
    raise ValueError('Вопрос не входит в поддерживаемые шаблоны')
