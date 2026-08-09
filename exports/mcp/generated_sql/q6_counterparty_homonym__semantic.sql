-- Interpreting "counterparties" as EMIR reporting counterparties (counterparty.emir_reporting, identified by LEI in emir.trade-reports),
-- "trading activity" as number of distinct economic trades (COUNT(DISTINCT uti)) where each UTI is counted once,
-- and "this week" as the current ISO calendar week (Monday–today) based on reporting_timestamp.

SELECT
    counterparty_lei,
    COUNT(DISTINCT uti) AS economic_trade_count
FROM (
    SELECT counterparty_1 AS counterparty_lei, uti, reporting_timestamp
    FROM `emir.trade-reports`
    UNION ALL
    SELECT counterparty_2 AS counterparty_lei, uti, reporting_timestamp
    FROM `emir.trade-reports`
) combined
WHERE
    reporting_timestamp >= CAST(DATE_TRUNC('week', CURRENT_TIMESTAMP) AS TIMESTAMP)
    AND reporting_timestamp < CURRENT_TIMESTAMP
    AND action_type NOT IN ('EROR', 'TERM')
GROUP BY
    counterparty_lei
ORDER BY
    economic_trade_count DESC
LIMIT 20;
