SELECT
    contract,
    SUM(ABS(net_quantity)) AS total_abs_net_position
FROM (
    SELECT
        position_key,
        contract,
        net_quantity,
        _meta.offset AS _offset,
        ROW_NUMBER() OVER (PARTITION BY position_key ORDER BY _meta.offset DESC) AS rn
    FROM `etd.positions`
) latest
WHERE rn = 1
GROUP BY contract
ORDER BY total_abs_net_position DESC
