COUNT(DISTINCT uti) per the schema rule: each economic trade appears twice (one report per counterparty), so COUNT(*) would double-count.
SELECT COUNT(DISTINCT uti) AS economic_trade_count
FROM `emir.trade-reports`;
