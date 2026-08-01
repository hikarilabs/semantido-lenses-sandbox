-- Interpreting "most trading activity" as highest count of EMIR trade reports and highest total notional,
-- and "this week" as based on reporting_timestamp (business event time) rather than Kafka ingestion time.
-- Counterparty activity is counted from both counterparty_1 and counterparty_2 perspectives (unioned).

SELECT
    counterparty,
    COUNT(*) AS report_count,
    SUM(notional) AS total_notional,
    COUNT(DISTINCT notional_currency) AS currencies_used
FROM (
    SELECT counterparty_1 AS counterparty, notional, notional_currency
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
      AND action_type != 'CANCEL'

    UNION ALL

    SELECT counterparty_2 AS counterparty, notional, notional_currency
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
      AND action_type != 'CANCEL'
) combined
GROUP BY counterparty
ORDER BY report_count DESC, total_notional DESC
LIMIT 25;
