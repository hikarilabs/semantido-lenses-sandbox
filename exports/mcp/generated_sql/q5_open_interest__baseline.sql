SELECT
    contract_series,
    SUM(ABS(net_quantity)) AS total_abs_net_position
FROM `etd.positions`
GROUP BY contract_series
ORDER BY total_abs_net_position DESC;
