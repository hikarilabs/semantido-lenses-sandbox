-- Interpretation: "trades" = distinct UTIs (not report rows); latest action per UTI is authoritative state.
-- Counting distinct UTIs excludes dual-sided double-counting and multi-row lifecycles.
SELECT COUNT(DISTINCT uti) AS trade_count
FROM `emir.trade-reports`
