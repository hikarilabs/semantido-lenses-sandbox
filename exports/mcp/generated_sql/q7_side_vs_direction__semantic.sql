-- Interpreting "currently short" as the latest-per-key position snapshot (max _meta.offset per position_key) where net_quantity < 0 and contract = 'FDAX-2026-09'.
-- "Clearing members" resolved to concept `clearing_member` (member_code in etd.positions), not reporting_counterparty/LEI.

SELECT member_code, account, contract, net_quantity
FROM etd.positions
WHERE contract = 'FDAX-2026-09'
  AND net_quantity < 0
GROUP BY position_key, member_code, account, contract, net_quantity
HAVING net_quantity = MIN(net_quantity)
