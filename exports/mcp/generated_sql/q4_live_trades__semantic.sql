-- Interpretation: "outstanding" = latest action per UTI is not EROR or TERM.
-- COUNT(DISTINCT uti) is used to count economic trades (not report submissions).
-- "Latest action per UTI" is determined by max(reporting_timestamp) per UTI.

SELECT COUNT(DISTINCT uti) AS outstanding_trade_count
FROM `emir.trade-reports`
WHERE (uti, reporting_timestamp) IN (
    SELECT uti, MAX(reporting_timestamp)
    FROM `emir.trade-reports`
    GROUP BY uti
)
AND action_type NOT IN ('EROR', 'TERM');
