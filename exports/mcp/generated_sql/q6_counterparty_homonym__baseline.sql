-- Interpreting "counterparties" as counterparty_lei in emir.trade-reports and "most trading activity" as highest count of trade reports submitted this week (no execution-level counterparty data available in schema)
SELECT
    counterparty_lei,
    COUNT(report_id) AS trade_report_count
FROM `emir.trade-reports`
WHERE reporting_timestamp >= DATEADD(DAY, -7, NOW())
GROUP BY counterparty_lei
ORDER BY trade_report_count DESC
