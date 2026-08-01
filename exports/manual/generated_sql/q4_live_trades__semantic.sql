-- Interpretation: "currently outstanding" = latest action_type per UTI is not EROR (error/cancel).
-- Counting distinct UTIs (not report rows) where the most recent action_type != 'EROR'.
-- MODI and NEWT are treated as active; EROR is treated as cancelled/withdrawn.

SELECT COUNT(*) AS outstanding_trade_count
FROM (
  SELECT uti
  FROM `emir.trade-reports`
  GROUP BY uti
  HAVING LATEST(action_type) != 'EROR'
)
