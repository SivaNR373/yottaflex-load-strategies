# Load Strategy Comparison

Compares full refresh, incremental merge, and partition replacement on a small orders dataset, and checks that all three give the same result.

(Setup, run steps and results will be added as I build.)

## Assumptions
- Data is synthetic and created by my generator with a fixed seed
- Orders arrive as daily CSV files; an order can appear again later with a new status
- The newest updated_at wins; older late rows never overwrite newer data
- Raw files are never edited, so every strategy can rebuild from them
- One customer file; customers are loaded before orders
- Everything runs locally with Python, DuckDB and pytest