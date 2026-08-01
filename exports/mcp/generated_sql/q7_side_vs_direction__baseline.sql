SELECT member_code, account, net_quantity
FROM etd.positions
WHERE contract = 'FDAX-2026-09'
  AND net_quantity < 0
ORDER BY net_quantity ASC
