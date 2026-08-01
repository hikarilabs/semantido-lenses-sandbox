-- Interpretation: "currently outstanding" = UTIs whose latest action_type is not EROR (error/cancellation).
-- NEWT/MODI are live states; EROR voids the report. Counting distinct UTIs (not report rows) per schema guidance.
-- "Not cancelled" resolved as: latest action_type per UTI is not 'EROR'.

SELECT COUNT(*) AS outstanding_trade_count
FROM (
    SELECT uti
    FROM `emir.trade-reports`
    GROUP BY uti
    HAVING LATEST(action_type ORDER BY reporting_timestamp) <> 'EROR'
) latest_states
