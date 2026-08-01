SELECT COUNT(*) AS fill_count
FROM `etd.executions`
WHERE exec_time >= '2026-07-21T00:00:00.000Z'
  AND exec_time <  '2026-07-22T00:00:00.000Z'
