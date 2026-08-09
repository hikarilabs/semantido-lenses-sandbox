SELECT
  COUNT(*) AS fill_count
FROM `etd.executions`
WHERE exec_time >= TIMESTAMP('2026-07-21 00:00:00')
  AND exec_time <  TIMESTAMP('2026-07-22 00:00:00');
