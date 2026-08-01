-- Interpreting "counterparty" as clearing_member (member_code) from etd.executions,
-- since the question concerns trading activity (fills/executions), not EMIR reporting.
-- "This week" uses exec_time (business event time) >= start of current ISO week (Monday).
-- "Most trading activity" = total executed quantity (sum of exec_qty) and fill count per member.

SELECT
    member_code,
    COUNT(exec_id)        AS fill_count,
    SUM(exec_qty)         AS total_exec_qty
FROM `etd.executions`
WHERE exec_time >= DATEADD(DAY, -(DAYOFWEEK(CURRENT_TIMESTAMP) - 2), CAST(CURRENT_TIMESTAMP AS DATE))
GROUP BY member_code
ORDER BY total_exec_qty DESC
