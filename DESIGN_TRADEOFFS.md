# Design Trade-offs

## Overview

This project implements three loading strategies for a DuckDB-based analytics
pipeline: Full Refresh, Incremental Merge, and Partition Replacement.

The strategies prioritize correctness, safe reruns, recoverability, and
understandable behavior. Performance results are recorded separately in
`output/benchmark.md`.

## Strategy Comparison

| Strategy | Approach | Advantages | Trade-offs |
|---|---|---|---|
| Full Refresh | Load into staging tables, then atomically replace target tables | Simple to reason about; produces a clean snapshot; staging and swap protect existing targets from partial loads | Reprocesses the complete dataset; runtime and resource usage grow with total input size |
| Incremental Merge | Process new files and upsert records only when incoming `updated_at` is newer | Avoids rewriting unchanged records; suitable for frequent small batches | Requires file tracking, deduplication, update rules, and transactional handling of data and metadata |
| Partition Replacement | Rebuild affected date partitions from the complete source data for those partitions | Keeps partition contents consistent and avoids rewriting unaffected partitions | Requires complete source data for each affected partition; work depends on partition size and distribution |

## Correctness and Recovery Decisions

- **Latest record wins within a batch:** duplicate `order_id` values are reduced
  using the greatest `updated_at`; the last row wins when timestamps tie.
- **Updates are timestamp-guarded:** an existing order is updated only when
  the incoming `updated_at` is strictly newer.
- **Invalid rows are rejected:** validation checks required fields, positive
  amounts, allowed statuses, valid nonfuture dates, and customer existence.
- **Reruns are safe:** processed-file tracking and transactional writes prevent
  successful files from being applied repeatedly by incremental strategies.
- **Full Refresh uses staging and an atomic replacement:** a failed load should
  not leave a partially replaced target.
- **Partition Replacement rebuilds affected partitions:** it requires the
  complete source data for those partitions, rather than only the incoming
  delta.
- **Crash testing is supported:** the failure-injection option allows recovery
  behavior to be tested without relying on an actual infrastructure failure.

## Benchmark Evidence

The recorded measurements are in `output/benchmark.md`. They are observations
from this challenge environment, not universal performance guarantees.

### Small dataset

| Strategy | Recorded runtime | Result |
|---|---:|---|
| Full Refresh | 0.708 s | SUCCESS |
| Incremental Merge | 0.951 s setup + 2.429 s strategy | SUCCESS |
| Partition Replacement | 0.729 s setup + 1.497 s strategy | SUCCESS |

The small-dataset measurements show that incremental strategies have setup and
tracking overhead. For small inputs, Full Refresh can be simpler and faster.

### Large dataset

| Strategy | Recorded runtime | Result |
|---|---:|---|
| Full Refresh | 249.192 s | SUCCESS |
| Incremental Merge | Setup approximately 230 s; strategy run interrupted after more than 10 minutes | INTERRUPTED |
| Partition Replacement | Not run | NOT RUN |

The large Incremental Merge run did not complete, so no exact strategy runtime
or final output count is claimed. The large Partition Replacement strategy was
not benchmarked. These results are intentionally reported as incomplete rather
than estimated.

### Separate small-batch incremental check

A separate test started with a target containing 100,000 records and processed
a 10-row batch in 0.310 s, adding 10 records and ending with 100,011 records.
This demonstrates the small-batch path, but it is not a controlled,
same-environment comparison against all three strategies.

## Limitations and Future Work

- Complete large-dataset measurements for Incremental Merge and Partition
  Replacement are still needed.
- A controlled before/after optimization benchmark was not completed, so no
  optimization speedup is claimed.
- Benchmark results depend on the local machine, DuckDB version, filesystem,
  and dataset shape.
- The reconciliation test initializes strategy targets in a shared test
  workflow. This can cause reject counts to differ because invalid rows may be
  encountered during initialization and strategy execution. Business-table
  equivalence is evaluated separately from operational metadata.
- A production deployment would also need operational scheduling, alerting,
  retention policies, access controls, and workload-specific capacity testing.

## Decision Summary

Full Refresh is the simplest baseline and is useful when a complete snapshot is
required. Incremental Merge is designed for recurring deltas and avoids
rewriting unchanged records, at the cost of additional state and recovery
logic. Partition Replacement is useful when complete affected partitions are
available and can be rebuilt independently.

The implementation favors explicit correctness and recoverability over
claiming performance improvements that have not been measured.
