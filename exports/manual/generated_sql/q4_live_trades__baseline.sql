SELECT COUNT(*) AS outstanding_trades
FROM `emir.trade-reports`
WHERE action_type <> 'CANCEL'
