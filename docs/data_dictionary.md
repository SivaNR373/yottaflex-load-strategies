# Data Dictionary

## Naming rules
- Tables and columns use snake_case
- Timestamps use ISO-8601, for example 2026-10-30T14:05:00
- IDs are fixed-format text: CUST-0001, ORD-000001
- Every loaded row carries run_id and source_file

## Source files

### customers.csv (one row per customer)
| Column | Type | Required | Notes |
|---|---|---|---|
| customer_id | text | yes | Unique key, like CUST-0001 |
| customer_name | text | yes | |
| country | text | yes | Two-letter code, like IN |
| created_at | timestamp | yes | ISO-8601 |

### orders_YYYY-MM-DD.csv (one file per day, one row per order event)
| Column | Type | Required | Notes |
|---|---|---|---|
| order_id | text | yes | Like ORD-000001 |
| customer_id | text | yes | Must exist in customers |
| order_date | date | yes | ISO date, not in the future |
| amount | decimal | yes | Greater than 0 |
| status | text | yes | created, paid, shipped, delivered, cancelled |
| updated_at | timestamp | yes | When this version of the order was written |

The same order_id can appear in many files (status updates, late rows).

## Target tables

### dim_customers
Grain: one row per customer. Key: customer_id.

### fact_orders (one copy per strategy)
Grain: one row per order (latest version only). Key: order_id.
Columns: order_id, customer_id, order_date, amount, status, updated_at, run_id, source_file.
Partition key: order_date.

### order_status_history
Grain: one row per order and updated_at. Key: (order_id, updated_at).
Columns: order_id, status, updated_at, run_id, source_file.
Purpose: keeps every status change, nothing is silently overwritten.

### rejects
Grain: one row per rejected record.
Columns: run_id, source_file, row_number, reject_reason, raw_record.
Purpose: every bad row stays traceable to its file and line.

### run_log
Grain: one row per run.
Columns: run_id, strategy, start_time, end_time, input_count, output_count, rejected_count, status, failure_reason.

## Validation rules
1. Required fields must not be empty
2. amount must be a number greater than 0
3. status must be one of the five allowed values
4. order_date must be a valid date and not in the future
5. customer_id must exist in dim_customers (otherwise reject)
6. Duplicate order_id in one batch: keep the latest updated_at (tie: last row)
7. A stored order is replaced only by a row with a newer updated_at

## Target table keys and data types

- dim_customers: customer_id is the primary key.
- fact_orders: order_id is the primary key; customer_id references dim_customers.
- order_status_history: order_id and updated_at form the composite key.
- run_log: run_id is the primary key.
- rejects stores invalid records with their source file and reason.

IDs use text (VARCHAR), amount uses DECIMAL, dates use DATE and timestamps use TIMESTAMP.

## Order history rule

Different order updates are preserved in order_status_history.
In fact_orders, only the newest updated_at value is kept.