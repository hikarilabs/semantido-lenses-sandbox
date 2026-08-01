-- Interpretation: "trades" means distinct UTIs (not report rows, not sides). Latest action per UTI is authoritative, but for a count of distinct trades ever reported, COUNT(DISTINCT uti) is the correct measure regardless of lifecycle action.
SELECT COUNT(DISTINCT uti) AS distinct_trade_count
FROM `emir.trade-reports`
