# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (5 tables)

### emir.trade-reports
- **Full Name**: emir.trade-reports
- **Primary Key**: report_id

#### Columns
- **report_id** (VARCHAR)
- **uti** (VARCHAR)
- **counterparty_lei** (VARCHAR)
- **action_type** (VARCHAR)
- **reporting_timestamp** (TIMESTAMP)

---

### etd.clearing-events
- **Full Name**: etd.clearing-events
- **Primary Key**: event_id

#### Columns
- **event_id** (VARCHAR)
- **member_code** (VARCHAR)
- **event_type** (VARCHAR)
- **event_time** (TIMESTAMP)

---

### etd.executions
- **Full Name**: etd.executions
- **Primary Key**: exec_id

#### Columns
- **exec_id** (VARCHAR)
- **order_id** (VARCHAR)
- **member_code** (VARCHAR)
- **side** (VARCHAR)
- **exec_qty** (INTEGER)
- **exec_price** (DECIMAL)
- **exec_time** (TIMESTAMP)

---

### etd.orders
- **Full Name**: etd.orders
- **Primary Key**: order_id

#### Columns
- **order_id** (VARCHAR)
- **account** (VARCHAR)
- **contract** (VARCHAR)
- **quantity** (INTEGER)
- **submitted_at** (TIMESTAMP)

---

### etd.positions
- **Full Name**: etd.positions
- **Primary Key**: position_key

#### Columns
- **position_key** (VARCHAR)
- **member_code** (VARCHAR)
- **account** (VARCHAR)
- **contract** (VARCHAR)
- **net_quantity** (INTEGER)
- **as_of** (TIMESTAMP)

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