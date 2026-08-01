-- Interpretation: "counterparty" resolved as counterparty.emir_reporting (LEI-identified legal counterparties in emir.trade-reports),
-- since the question is about trading activity (economic trades), not clearing membership.
-- "Most trading activity" = highest count of distinct economic trades (COUNT(DISTINCT uti)) where counterparty appears as either CP1 or CP2.
-- "This week" = current calendar week (Monday–now), using reporting_timestamp as the time axis.
-- Each UTI is counted once per counterparty LEI (union of CP1 and CP2 appearances).

SELECT
    counterparty_lei,
    COUNT(DISTINCT uti) AS economic_trade_count
FROM (
    SELECT counterparty_1 AS counterparty_lei, uti, reporting_timestamp
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= CAST(DATE_TRUNC('week', CURRENT_TIMESTAMP) AS TIMESTAMP)

    UNION ALL

    SELECT counterparty_2 AS counterparty_lei, uti, reporting_timestamp
    FROM `emir.trade-reports`
    WHERE reporting_timestamp >= CAST(DATE_TRUNC('week', CURRENT_TIMESTAMP) AS TIMESTAMP)
) all_sides
GROUP BY counterparty_lei
ORDER BY economic_trade_count DESC
LIMIT 25;
