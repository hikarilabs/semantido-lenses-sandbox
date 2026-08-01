-- Interpretation: "outstanding" = latest action per UTI is not EROR or TERM.
-- COUNT(DISTINCT uti) is used to count economic trades (not report submissions).
-- "Latest action per UTI" is determined by the most recent reporting_timestamp for that UTI.

SELECT COUNT(DISTINCT uti) AS outstanding_trade_count
FROM (
    SELECT
        uti,
        action_type,
        ROW_NUMBER() OVER (PARTITION BY uti ORDER BY reporting_timestamp DESC) AS rn
    FROM `emir.trade-reports`
) latest
WHERE rn = 1
  AND action_type NOT IN ('EROR', 'TERM');
