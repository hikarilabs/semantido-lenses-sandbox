# Topic schemas

## `emir.trade-reports`
- report_id: VARCHAR
- uti: VARCHAR
- counterparty_1: VARCHAR
- counterparty_2: VARCHAR
- exec_id: VARCHAR
- action_type: VARCHAR
- notional: DECIMAL
- notional_currency: VARCHAR
- reporting_timestamp: TIMESTAMP

## `etd.clearing-events`
- event_id: VARCHAR
- event_type: VARCHAR
- exec_id: VARCHAR
- clearing_member_id: VARCHAR
- account: VARCHAR
- event_time: TIMESTAMP

## `etd.executions`
- exec_id: VARCHAR
- order_id: VARCHAR
- contract_series: VARCHAR
- side: VARCHAR
- quantity: DECIMAL
- price: DECIMAL
- executing_member: VARCHAR
- exec_time: TIMESTAMP

## `etd.positions`
- position_key: VARCHAR
- clearing_member_id: VARCHAR
- account: VARCHAR
- contract_series: VARCHAR
- net_quantity: DECIMAL
- as_of_time: TIMESTAMP

## `refdata.contracts`
- contract_series: VARCHAR
- product_type: VARCHAR
- underlying: VARCHAR
- contract_multiplier: DECIMAL
- expiry_date: TIMESTAMP

## Lenses SQL usage notes (applies to all queries)

- Engine: SQL Snapshot (point-in-time queries over topic data).
- Topic names contain dots/dashes: always backtick them,
  e.g. SELECT * FROM `etd.executions` LIMIT 10;
- Record metadata is available under _meta (e.g. _meta.offset,
  _meta.partition, _meta.timestamp) and the message key under _key.
- _meta.timestamp is Kafka ingestion time, not business event time.
- Always end statements with a semicolon and add LIMIT to exploratory
  queries.
