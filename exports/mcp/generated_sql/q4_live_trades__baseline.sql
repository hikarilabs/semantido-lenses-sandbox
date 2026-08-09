SELECT
    COUNT(*) AS outstanding_trade_count
FROM `emir.trade-reports`
WHERE action_type <> 'CANCEL';
