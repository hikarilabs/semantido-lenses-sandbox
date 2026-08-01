-- Interpretation: "current" = latest record per (clearing_member_id, account, contract_series) key,
-- resolved via max _meta.offset per partition and key, before summing ABS(net_quantity).
-- Total open interest per series = SUM(ABS(net_quantity)) / 2 over latest snapshots
-- (each economic position appears on both sides of the CCP book).

SELECT
    contract_series,
    SUM(ABS(net_quantity)) / 2 AS total_abs_net_position
FROM (
    SELECT
        contract_series,
        net_quantity,
        ROW_NUMBER() OVER (
            PARTITION BY clearing_member_id, account, contract_series, _meta.partition
            ORDER BY _meta.offset DESC
        ) AS rn
    FROM `etd.positions`
) latest
WHERE rn = 1
GROUP BY contract_series
ORDER BY total_abs_net_position DESC
LIMIT 500;
