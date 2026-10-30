# Architecture

## Flow
```text
generator -> data/raw/*.csv (daily files, never edited)
                 |
          read + validate -----> rejects (bad rows + reason)
                 |
          clean, deduped rows
        +--------+--------+
        |        |        |
   full_refresh  merge  partition_replace
        +--------+--------+
                 |
   3 target tables + order_status_history
                 |
   reconcile + run_log + benchmark
```

## The three strategies
- **Full refresh:** rebuild the table from all raw files, then swap it in one transaction.
- **Incremental merge:** apply only the new files. Insert new orders, update existing ones only if updated_at is newer.
- **Partition replace:** find which order_dates the new files touch, delete those dates, and rebuild them from raw.

## Safety
- Each load runs inside a transaction (all or nothing).
- Raw files are append-only, so any strategy can be re-run.
- Every run writes one row to run_log.