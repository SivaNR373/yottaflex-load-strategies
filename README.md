# Load Strategy Comparison

Compares full refresh, incremental merge, and partition replacement on a small orders dataset, and checks that all three give the same result.

## Architecture

CSV files → Data Generator → Validation → Data Loading → Reconciliation

The project compares three loading strategies:

- **Full Refresh:** Reload all available data.
- **Incremental Merge:** Load new records and update existing records when newer data arrives.
- **Partition Replacement:** Reload only the affected order dates.

Finally, the results of all three strategies are compared to check whether they produce the same data.

## Assumptions
- Data is synthetic and created by my generator with a fixed seed
- Orders arrive as daily CSV files; an order can appear again later with a new status
- The newest updated_at wins; older late rows never overwrite newer data
- Raw files are never edited, so every strategy can rebuild from them
- One customer file; customers are loaded before orders
- Everything runs locally with Python, DuckDB and pytest

## Failure Recovery and Backfill

### Transactional failure recovery

Each loader runs its database changes inside a transaction. If a run fails, its data changes and processed-file tracking are rolled back together.

To retry after a failure, rerun the same strategy against the same database. Successfully committed data is retained, while the failed transaction can be attempted again.

The `--fail-after N` option is available to simulate a failure after processing N fact rows. Use it to test rollback and retry behavior.

### Recovery commands

Run these from the repository root.

**Full Refresh — simulate failure:**
```powershell
python -m src.loaders --strategy full_refresh --database-path data/phase6_crash_test.duckdb --fail-after 1