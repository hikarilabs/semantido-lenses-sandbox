-- Interpretation: "current" = latest compacted record per (clearing_member_id, account, contract_series) key,
-- identified by max _meta.offset per partition and _key. Then SUM(ABS(net_quantity)) per contract_series.
-- Per schema rule: total open interest per series = SUM(ABS(net_quantity))/2 is for open interest;
-- the question asks for total absolute net position (not open interest), so we SUM(ABS(net_quantity)) directly
-- without halving, representing the sum of absolute exposures across all members/accounts per series.

SELECT
    contract_series,
    SUM(ABS(net_quantity)) AS total_abs_net_position
FROM (
    SELECT
        contract_series,
        net_quantity,
        ROW_NUMBER() OVER (
            PARTITION BY _key, _meta.partition
            ORDER BY _meta.offset DESC
        ) AS rn
    FROM `etd.positions`
) latest
WHERE rn = 1
GROUP BY contract_series
ORDER BY total_abs_net_position DESC
LIMIT 100;
