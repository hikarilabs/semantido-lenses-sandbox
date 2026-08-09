SELECT
    clearing_member_id,
    account,
    net_quantity
FROM (
    SELECT
        clearing_member_id,
        account,
        contract_series,
        net_quantity,
        ROW_NUMBER() OVER (
            PARTITION BY clearing_member_id, account, contract_series
            ORDER BY _meta.offset DESC
        ) AS rn
    FROM `etd.positions`
    WHERE contract_series = 'FDAX-2026-09'
) latest
WHERE rn = 1
  AND net_quantity < 0
ORDER BY net_quantity ASC;
