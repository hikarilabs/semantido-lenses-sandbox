-- Interpreting "trading activity" as number of EMIR trade reports filed this week, using reporting_timestamp as the business event time.
-- "This week" is resolved using reporting_timestamp >= date trunc to current week (Monday).
-- Each report involves two counterparties; we union both sides to count activity per counterparty.

SELECT
    counterparty,
    COUNT(*) AS report_count,
    SUM(notional) AS total_notional,
    MIN(reporting_timestamp) AS first_report,
    MAX(reporting_timestamp) AS last_report
FROM (
    SELECT counterparty_1 AS counterparty, notional, reporting_timestamp
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= DATEADD(DAY, -(DAYOFWEEK(CURRENT_TIMESTAMP) - 2), CAST(CURRENT_DATE AS TIMESTAMP))
      AND reporting_timestamp <= CURRENT_TIMESTAMP

    UNION ALL

    SELECT counterparty_2 AS counterparty, notional, reporting_timestamp
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= DATEADD(DAY, -(DAYOFWEEK(CURRENT_TIMESTAMP) - 2), CAST(CURRENT_DATE AS TIMESTAMP))
      AND reporting_timestamp <= CURRENT_TIMESTAMP
) AS combined
GROUP BY counterparty
ORDER BY report_count DESC
LIMIT 25;
