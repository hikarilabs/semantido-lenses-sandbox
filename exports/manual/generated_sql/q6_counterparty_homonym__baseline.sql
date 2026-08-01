-- Interpreting "most trading activity" as highest count of EMIR trade reports (by counterparty_lei) this week, since no direct link exists between emir.trade-reports and etd execution volume.

SELECT
    counterparty_lei,
    COUNT(*) AS report_count
FROM `emir.trade-reports`
WHERE reporting_timestamp >= TIMESTAMP(DATEADD(DAY, -DAYOFWEEK(CURRENT_TIMESTAMP) + 2, CAST(CURRENT_TIMESTAMP AS DATE)))
  AND reporting_timestamp < CURRENT_TIMESTAMP
GROUP BY counterparty_lei
ORDER BY report_count DESC
LIMIT 20
