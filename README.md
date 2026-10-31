# YottaFlex Load Strategy Comparison

A Python and DuckDB project that implements and compares three data loading strategies for daily order data:

- **Full Refresh**
- **Incremental Merge**
- **Partition Replacement**

The project evaluates data correctness, validation, idempotency, failure recovery, reconciliation, and runtime performance using synthetic CSV data.

## Project Goals

The challenge is to determine whether different loading strategies can produce equivalent business data while understanding their operational trade-offs.

The project demonstrates:

- CSV ingestion and data validation
- Duplicate handling and late-arriving updates
- Transactional loading and failure recovery
- Idempotent reruns and processed-file tracking
- Data quality rejects
- Reconciliation across loading strategies
- Benchmarking on small and large datasets
- Automated tests using `pytest`

## Architecture

```text
Synthetic CSV Data
        |
        v
   Data Generator
        |
        v
      Validator
        |
        +------> Rejected Records
        |
        v
  Loading Strategy
        |
        +------> Full Refresh
        |
        +------> Incremental Merge
        |
        +------> Partition Replacement
        |
        v
     DuckDB Tables
        |
        v
 Reconciliation & Benchmarking
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Data processing and orchestration |
| DuckDB | Local analytical database |
| CSV | Source data format |
| pytest | Automated testing |
| Git | Version control |

## Repository Structure

```text
yottaflex-load-strategies/
├── ai_usage/
│   ├── prompts.md
│   └── AI_USAGE.md
├── data/
│   ├── raw/
│   └── expected/
├── src/
│   ├── generator.py
│   ├── validate.py
│   ├── loaders.py
│   ├── reconcile.py
│   └── benchmark.py
├── tests/
│   ├── test_loaders.py
│   ├── test_run_log.py
│   └── test_validate.py
├── .gitignore
├── pytest.ini
└── README.md
```

Generated datasets, local DuckDB databases, and benchmark outputs are kept out of version control.

## Data Model

The pipeline uses the following main tables:

| Table | Purpose |
|---|---|
| `dim_customers` | Customer dimension |
| `fact_orders` | Current order state |
| `order_status_history` | Order status history |
| `rejects` | Records rejected during validation |
| `run_log` | Execution and processing metrics |
| `processed_files` | Tracks files processed by Full Refresh |
| `processed_files_incremental_merge` | Tracks Incremental Merge file processing |
| `processed_files_partition_replace` | Tracks Partition Replacement file processing |

Orders are sourced from daily CSV files. An order may appear again in a later file with a newer status or update timestamp.

## Data Quality Rules

The validator checks the following rules:

- Required fields must be present: `order_id`, `customer_id`, `order_date`, `amount`, `status`, and `updated_at`.
- `amount` must be greater than zero.
- `status` must be one of `created`, `paid`, `shipped`, `delivered`, or `cancelled`.
- `order_date` must be a valid ISO date and cannot be in the future.
- `customer_id` must reference an existing customer.
- Duplicate `order_id` values within a batch are resolved using the latest `updated_at`; if timestamps tie, the last row wins.
- An incoming order updates the current record only when its `updated_at` is strictly newer than the stored timestamp.

Invalid records are written to the rejects table rather than silently accepted.

## Loading Strategies

### 1. Full Refresh

Full Refresh reloads the available source data and replaces the target business tables.

**Advantages**
- Simple processing model
- Rebuilds target data from source files
- Useful as a baseline for correctness comparisons

**Trade-offs**
- Reprocesses the full dataset
- Can become expensive as data volume grows
- Replaces the existing target state

**Best suited for:** Small datasets, initial loads, complete rebuilds, and baseline reconciliation.

### 2. Incremental Merge

Incremental Merge processes incoming files and inserts new orders or updates existing orders when the incoming `updated_at` is newer.

**Advantages**
- Avoids rebuilding all existing business records
- Supports new orders and newer updates
- Uses processed-file tracking to support safe reruns

**Trade-offs**
- Requires an existing target table
- Depends on reliable file tracking and update rules
- Performance depends on batch size, target size, and merge implementation

**Best suited for:** Regular ingestion where new and changed records arrive in batches.

### 3. Partition Replacement

Partition Replacement rebuilds affected order-date partitions from the complete source data for those dates.

**Advantages**
- Limits replacement work to affected partitions
- Can handle corrections and late-arriving records within affected dates
- Provides a rebuild-oriented alternative to row-level merge logic

**Trade-offs**
- Requires complete source data for each affected partition
- Can reprocess more data than Incremental Merge when only a few rows change
- Requires an initialized target

**Best suited for:** Date-partitioned datasets where corrections are concentrated in a limited number of partitions.

## Setup

Run commands from the repository root.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Generate Test Data

Generate the small dataset:

```powershell
python -m src.generator --size small --output data/raw --seed 42
```

Generate the large dataset:

```powershell
python -m src.generator --size large --output data/large --seed 42
```

The generator uses a fixed seed to make test data reproducible.

The generated challenge datasets include valid orders, duplicate records, status updates, late-arriving orders, malformed records, an extra-column case, and an empty daily file.

## Run the Loading Strategies

Run each strategy from the repository root.

### Full Refresh

```powershell
python -m src.loaders --strategy full_refresh --database-path data/full_refresh.duckdb
```

### Incremental Merge

```powershell
python -m src.loaders --strategy incremental_merge --database-path data/incremental_merge.duckdb
```

Incremental Merge requires initialized target tables. For a fresh database, initialize it first:

```powershell
python -m src.loaders --strategy full_refresh --database-path data/incremental_merge.duckdb
python -m src.loaders --strategy incremental_merge --database-path data/incremental_merge.duckdb
```

### Partition Replacement

```powershell
python -m src.loaders --strategy partition_replace --database-path data/partition_replace.duckdb
```

Partition Replacement also requires initialized target tables:

```powershell
python -m src.loaders --strategy full_refresh --database-path data/partition_replace.duckdb
python -m src.loaders --strategy partition_replace --database-path data/partition_replace.duckdb
```

### CLI Help

```powershell
python -m src.loaders --help
```

## Idempotency and Failure Recovery

Each loader uses transactions so data changes and processed-file tracking are committed or rolled back together.

If a run fails, rerun the same strategy against the same database. The failed transaction can be attempted again without retaining its partial changes.

The `--fail-after N` option simulates a failure after inserting a specified number of fact rows. Use a separate database to test failure behavior without affecting normal results.

Example:

```powershell
python -m src.loaders --strategy full_refresh --database-path data/phase6_crash_test.duckdb --fail-after 1
```

After the simulated failure, rerun without the failure flag:

```powershell
python -m src.loaders --strategy full_refresh --database-path data/phase6_crash_test.duckdb
```

## Reconciliation

The reconciliation tool compares the final business data produced by the three strategies.

Run it after the strategy databases have been created:

```powershell
python -m src.reconcile
```

The default database paths are:

```text
output/reconcile_full_refresh.duckdb
output/reconcile_incremental_merge.duckdb
output/reconcile_partition_replace.duckdb
```

Custom database paths and report output can be supplied:

```powershell
python -m src.reconcile `
  --full-refresh output/reconcile_full_refresh.duckdb `
  --incremental-merge output/reconcile_incremental_merge.duckdb `
  --partition-replace output/reconcile_partition_replace.duckdb `
  --output output/reconciliation_report.md
```

Reconciliation compares:

- Final order count
- Total order amount
- Status counts
- Order business-column hashes
- Order status-history hashes

Run-specific metadata such as `run_id` and `source_file` is excluded from business-data hashes.

Reject counts are reported, but reject contents are not hashed.

## Benchmarking

The benchmark tool measures the three loading strategies against the small and large datasets:

```powershell
python -m src.benchmark
```

The benchmark uses isolated DuckDB databases and Python's `time.perf_counter()`.

For Incremental Merge and Partition Replacement, Full Refresh initializes the target database. Setup time and strategy runtime are reported separately.

**Important:** The benchmark script deletes an existing benchmark database before starting that strategy/dataset run. Review the output and preserve any benchmark evidence before rerunning it.

### Recorded Benchmark Results

| Dataset | Strategy | Setup time | Strategy runtime | Status |
|---|---|---:|---:|---|
| Small | Full Refresh | N/A | 0.708 s | Success |
| Small | Incremental Merge | 0.951 s | 2.429 s | Success |
| Small | Partition Replacement | 0.729 s | 1.497 s | Success |
| Large | Full Refresh | N/A | 249.192 s | Success |
| Large | Incremental Merge | ~230 s | Interrupted | Incomplete |
| Large | Partition Replacement | N/A | Not run | Incomplete |

A separate Incremental Merge test against a 100k-row target processed a 10-row batch successfully in **0.310 seconds**, resulting in 10 new orders and a final target count of 100,011.

These measurements are environment-specific, single-run observations—not universal performance guarantees. The large Incremental Merge run was interrupted, and the large Partition Replacement run was not completed. Therefore, the project does not claim a complete large-dataset runtime comparison across all three strategies.

See the benchmark report for the detailed methodology and interpretation.

## Run Tests

Run the complete test suite:

```powershell
python -m pytest
```

The completed test suite contains **34 passing tests** covering validation, loading strategies, run logging, and edge cases.

## Key Engineering Decisions

- Raw source files remain unchanged so strategies can rebuild from source data.
- Customers are loaded before orders to support customer-key validation.
- Newer `updated_at` values take precedence over older updates.
- File tracking and business changes are handled transactionally.
- Full Refresh serves as the baseline for reconciliation.
- Incremental Merge and Partition Replacement require initialized targets.
- Synthetic data and fixed seeds support repeatable testing.
- Benchmark limitations are reported explicitly rather than inferred or hidden.

## Known Limitations

- Data is synthetic and processed locally using DuckDB.
- Benchmark measurements are single-run observations.
- The large Incremental Merge benchmark was interrupted.
- The large Partition Replacement benchmark was not run.
- Reconciliation hashes business data and history, but does not hash reject contents.
- Results may differ on other hardware, data distributions, or database configurations.

## AI Usage Disclosure

AI assistance was used during development for explanation, debugging support, test planning, documentation, and review.

The prompts and usage details are documented in:

- `ai_usage/prompts.md`
- `ai_usage/AI_USAGE.md`

AI-generated suggestions were reviewed and tested against the project before being incorporated.

## Project Status

The three loading strategies, validation, transaction-based recovery, idempotency behavior, reconciliation tooling, benchmark tooling, and automated tests are implemented.

The project has **34 passing tests**. Documentation and final submission checks are the remaining completion steps.