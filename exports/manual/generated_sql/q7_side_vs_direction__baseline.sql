SELECT
    clearing_member_id,
    account,
    net_quantity,
    as_of_time
FROM `etd.positions`
WHERE contract_series = 'FDAX-2026-09'
  AND net_quantity < 0
ORDER BY net_quantity ASC;
