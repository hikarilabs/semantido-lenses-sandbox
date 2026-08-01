SELECT
    contract,
    SUM(ABS(net_quantity)) AS total_abs_net_position
FROM `etd.positions`
GROUP BY contract
ORDER BY total_abs_net_position DESC
