SELECT COUNT(DISTINCT o.order_id) AS executed_order_count
FROM `etd.orders` o
WHERE EXISTS (
    SELECT 1
    FROM `etd.executions` e
    WHERE e.order_id = o.order_id
)
