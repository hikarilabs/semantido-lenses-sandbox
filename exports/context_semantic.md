# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (5 tables)

### emir.trade-reports
- **Full Name**: emir.trade-reports
- **Primary Key**: report_id
- **Description**: EMIR trade reports, one row per report side per lifecycle action. Dual-sided: in-scope trades appear twice (one per reporting counterparty).
- **Concept**: `emir_trade_report`
- **Application Context**: Latest action per UTI is the trade state; count distinct UTIs for trade counts, never report rows.
- **Time Dimension**: reporting_timestamp — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `reporting_counterparty`

#### Columns
- **report_id** (VARCHAR)
  - Column: report_id
  - *Concept*: `emir_trade_report`
- **uti** (VARCHAR)
  - Unique Trade Identifier — the trade-level key.
- **counterparty_lei** (VARCHAR)
  - Reporting counterparty LEI (entity), NOT a clearing member code.
  - *Concept*: `reporting_counterparty`
- **action_type** (VARCHAR)
  - Column: action_type
  - *Examples*: NEWT, MODI, EROR
- **reporting_timestamp** (TIMESTAMP)
  - Column: reporting_timestamp
  - *Time grain*: second
  - *Secondary time dimension*

---

### etd.clearing-events
- **Full Name**: etd.clearing-events
- **Primary Key**: event_id
- **Description**: Clearing lifecycle events (novation, give-up, netting runs) keyed by clearing membership.
- **Concept**: `clearing_member`
- **Time Dimension**: event_time — primary time axis; use for any per-day/month/quarter aggregation

#### Columns
- **event_id** (VARCHAR)
  - Column: event_id
- **member_code** (VARCHAR)
  - CCP membership code — NOT an LEI.
  - *Concept*: `clearing_member`
- **event_type** (VARCHAR)
  - Column: event_type
  - *Examples*: NOVATION, GIVE_UP, NETTING
- **event_time** (TIMESTAMP)
  - Column: event_time
  - *Time grain*: second
  - *Secondary time dimension*

---

### etd.executions
- **Full Name**: etd.executions
- **Primary Key**: exec_id
- **Description**: Exchange executions (fills). One order fans out to one or more rows here — counting rows counts fills, not orders.
- **Concept**: `execution`
- **Application Context**: side is BUY/SELL aggressor convention; never infer LONG/SHORT from it (see position_snapshot).
- **Time Dimension**: exec_time — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `order`, `clearing_member`

#### Columns
- **exec_id** (VARCHAR)
  - Column: exec_id
  - *Concept*: `execution`
- **order_id** (VARCHAR)
  - Parent order (fan-out join key).
  - *Concept*: `order`
- **member_code** (VARCHAR)
  - Executing clearing membership code.
  - *Concept*: `clearing_member`
- **side** (VARCHAR)
  - Column: side
  - *Examples*: BUY, SELL
- **exec_qty** (INTEGER)
  - Column: exec_qty
- **exec_price** (DECIMAL)
  - Column: exec_price
- **exec_time** (TIMESTAMP)
  - Business event time; `_meta.timestamp` is Kafka ingestion time and must not be used for trade-date logic.
  - *Time grain*: second
  - *Secondary time dimension*

---

### etd.orders
- **Full Name**: etd.orders
- **Primary Key**: order_id
- **Description**: Client orders as submitted. One row per order event.
- **Concept**: `order`
- **Time Dimension**: submitted_at — primary time axis; use for any per-day/month/quarter aggregation

#### Columns
- **order_id** (VARCHAR)
  - Column: order_id
  - *Concept*: `order`
- **account** (VARCHAR)
  - Column: account
- **contract** (VARCHAR)
  - Column: contract
- **quantity** (INTEGER)
  - Ordered quantity; fills may sum to less (partials).
- **submitted_at** (TIMESTAMP)
  - Business event time, NOT the Kafka timestamp.
  - *Time grain*: second
  - *Secondary time dimension*

---

### etd.positions
- **Full Name**: etd.positions
- **Primary Key**: position_key
- **Description**: COMPACTED state topic: netted positions per (member, account, contract). Records supersede by key; browsing shows multiple records per key until compaction.
- **Concept**: `position_snapshot`
- **Application Context**: COMPACTED topic: the only valid aggregate is over latest-per-key state — a Lenses-dialect concern (_meta.offset), deliberately NOT a sql_filter because it is not SQL over this schema. In Lenses SQL, group by key and take the max-offset record, or query the table projection.
- **Time Dimension**: as_of — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `clearing_member`

#### Columns
- **position_key** (VARCHAR)
  - Column: position_key
  - *Concept*: `position_snapshot`
- **member_code** (VARCHAR)
  - Column: member_code
  - *Concept*: `clearing_member`
- **account** (VARCHAR)
  - Column: account
- **contract** (VARCHAR)
  - Column: contract
- **net_quantity** (INTEGER)
  - Signed: positive LONG, negative SHORT. This — not execution side — is direction.
- **as_of** (TIMESTAMP)
  - Column: as_of
  - *Time grain*: second
  - *Secondary time dimension*

---

## Relationships (1 connections)

### etd.executions → etd.orders
- **Type**: many-to-one
- **Join**: "etd.executions".order_id = "etd.orders".order_id
- **Description**: Fill fan-out: many executions per order.

## Summary
- **Total Tables**: 5
- **Total Columns**: 27
- **Total Relationships**: 1

## Concepts (6 in scope)

Business concepts realized by this schema. The concept id is the authoritative reference; labels may collide (see Disambiguation).

### `clearing_member` — clearing member
- **Definition**: A CCP clearing membership, identified by member code. One legal entity can hold several memberships; a member code is not an LEI and must never be joined to one.
- **Grain**: clearing_membership
- **Synonyms**: counterparty, member
- **Realized by**: etd.clearing-events, etd.clearing-events.member_code, etd.executions.member_code, etd.positions.member_code
- **Relation**: distinct from → `reporting_counterparty`

### `emir_trade_report` — emir trade report
- **Definition**: One side of an EMIR trade report. Dual-sided reporting means two reports per trade when both counterparties are in scope: COUNT(reports) is not COUNT(trades). Lifecycle action types (NEWT/MODI/EROR) mean the latest state per UTI is authoritative.
- **Grain**: report
- **Realized by**: emir.trade-reports, emir.trade-reports.report_id
- **External**: exact match → `emir:trade-report` [emir@refit-2024]

### `execution` — execution
- **Definition**: An exchange fill event. Side is BUY/SELL from the aggressor's perspective and says nothing about the resulting net position direction.
- **Grain**: execution
- **Synonyms**: fill, trade
- **Realized by**: etd.executions, etd.executions.exec_id
- **Relation**: distinct from → `position_snapshot`

### `order` — order
- **Definition**: A client order as submitted to the exchange. One order fills into one or more executions — counting executions counts fills, not orders.
- **Grain**: order
- **Realized by**: etd.executions.order_id, etd.orders, etd.orders.order_id

### `position_snapshot` — position snapshot
- **Definition**: The netted position state for one (member, account, contract) key at a point in time, published to a COMPACTED topic. Each record supersedes the previous one for its key: only latest-per-key is a position; any aggregate over full history double-counts. net_quantity carries the direction sign (positive LONG, negative SHORT).
- **Grain**: position_snapshot
- **Synonyms**: position, net position
- **Realized by**: etd.positions, etd.positions.position_key
- **Relation**: distinct from → `execution`

### `reporting_counterparty` — reporting counterparty
- **Definition**: The legal entity with the EMIR Art. 9 reporting obligation, identified by LEI. An entity-level identity that exists independently of any clearing arrangement.
- **Grain**: legal_entity
- **Synonyms**: counterparty, reporting party
- **Realized by**: emir.trade-reports.counterparty_lei
- **External**: exact match → `gleif:lei` [gleif@2026]
- **Relation**: distinct from → `clearing_member`

## Disambiguation

The surface forms below are claimed by more than one distinct concept. Always resolve by concept id, never by label.

### "counterparty" — 2 distinct concepts
- `clearing_member` (etd.clearing-events, etd.clearing-events.member_code, etd.executions.member_code, etd.positions.member_code): A CCP clearing membership, identified by member code. One legal entity can hold several memberships; a member code is not an LEI and must never be joined to one.
- `reporting_counterparty` (emir.trade-reports.counterparty_lei): The legal entity with the EMIR Art. 9 reporting obligation, identified by LEI. An entity-level identity that exists independently of any clearing arrangement.

Do not treat these as equivalent; do not join or compare their columns as if they carried the same meaning.
