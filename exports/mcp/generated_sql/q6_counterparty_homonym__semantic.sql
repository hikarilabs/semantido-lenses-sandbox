-- Interpreting "counterparty" as clearing_member (member_code) from etd.executions,
-- since the question is about trading activity (fills/executions), not EMIR reporting.
-- "Most trading activity" = highest total executed quantity this week.
-- "This week" = Monday of the current ISO week through now.

SELECT
    member_code,
    COUNT(exec_id)        AS fill_count,
    SUM(exec_qty)         AS total_exec_qty
FROM `etd.executions`
WHERE exec_time >= CAST(DATE_TRUNC('week', NOW()) AS TIMESTAMP)
  AND exec_time <  NOW()
GROUP BY member_code
ORDER BY total_exec_qty DESC
