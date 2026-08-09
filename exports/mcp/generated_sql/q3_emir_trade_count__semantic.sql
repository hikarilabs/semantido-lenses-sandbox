COUNT(DISTINCT uti) to count economic trades, not COUNT(*) which would double-count due to dual-sided reporting.
SELECT COUNT(DISTINCT uti) AS economic_trade_count
FROM `emir.trade-reports`;
