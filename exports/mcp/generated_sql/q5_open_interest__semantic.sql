SELECT
  contract,
  SUM(ABS(net_quantity)) AS total_abs_net_position
FROM (
  SELECT
    position_key,
    contract,
    net_quantity,
    MAX(_meta.offset) OVER (PARTITION BY position_key) AS max_offset,
    _meta.offset AS record_offset
  FROM `etd.positions`
) latest
WHERE record_offset = max_offset
GROUP BY contract
ORDER BY total_abs_net_position DESC
