
"""Benchmark the three loading strategies on small and large datasets.

Incremental Merge and Partition Replace require target tables to exist.
For those strategies, Full Refresh initializes a fresh benchmark database;
initialization time is reported separately from strategy runtime.

The report is updated after each strategy so completed results survive
an interruption.
"""

import time
from pathlib import Path

from src.loaders import (
    full_refresh,
    incremental_merge,
    partition_replace,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORT_PATH = OUTPUT_DIR / "benchmark.md"

DATASETS = {
    "small": PROJECT_ROOT / "data" / "raw",
    "large": PROJECT_ROOT / "data" / "large",
}

STRATEGIES = {
    "full_refresh": full_refresh,
    "incremental_merge": incremental_merge,
    "partition_replace": partition_replace,
}


def format_seconds(seconds):
    return f"{seconds:.3f}"


def write_report(results):
    """Write the current benchmark results to Markdown."""

    lines = [
        "# Loading Strategy Benchmark",
        "",
        "## Method",
        "",
        "- Each strategy and dataset combination uses a separate DuckDB database.",
        "- Timing uses Python `time.perf_counter()`.",
        "- Full Refresh is timed as a complete load.",
        "- Incremental Merge and Partition Replace require existing target tables.",
        "- For those strategies, Full Refresh initializes the database before the",
        "  timed strategy run. Initialization time is reported separately.",
        "- These are single-run measurements, not statistical averages.",
        "- The report is updated after each strategy completes or is interrupted.",
        "",
        "## Results",
        "",
        "| Dataset | Strategy | Setup (s) | Strategy runtime (s) | Status | Input rows | Output rows | Rejected rows |",
        "|---|---|---:|---:|---|---:|---:|---:|",
    ]

    for result in results:
        lines.append(
            f"| {result['dataset']} "
            f"| {result['strategy']} "
            f"| {format_seconds(result['setup_seconds'])} "
            f"| {format_seconds(result['strategy_seconds'])} "
            f"| {result['status']} "
            f"| {result['input_count']} "
            f"| {result['output_count']} "
            f"| {result['rejected_count']} |"
        )

    lines.extend(
        [
            "",
            "## Benchmark databases",
            "",
        ]
    )

    for result in results:
        lines.append(
            f"- `{result['database_path']}` - "
            f"{result['dataset']} / {result['strategy']}"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Compare strategy runtime across strategies for the same dataset.",
            "For Incremental Merge and Partition Replace, include setup time when",
            "estimating the cost of a completely fresh database load:",
            "",
            "`total fresh-load time = setup time + strategy runtime`",
            "",
            "Results are environment-specific and should be interpreted as",
            "observed measurements, not universal performance guarantees.",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_strategy(strategy_name, loader, dataset_name, input_folder):
    """Run one strategy against its own isolated DuckDB database."""

    database_path = (
        OUTPUT_DIR
        / "benchmarks"
        / f"{dataset_name}_{strategy_name}.duckdb"
    )

    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove an earlier benchmark database so this run starts clean.
    if database_path.exists():
        database_path.unlink()

    setup_seconds = 0.0

    if strategy_name in {"incremental_merge", "partition_replace"}:
        setup_start = time.perf_counter()

        full_refresh(
            input_folder=str(input_folder),
            database_path=str(database_path),
        )

        setup_seconds = time.perf_counter() - setup_start

    strategy_start = time.perf_counter()

    result = loader(
        input_folder=str(input_folder),
        database_path=str(database_path),
    )

    strategy_seconds = time.perf_counter() - strategy_start

    return {
        "dataset": dataset_name,
        "strategy": strategy_name,
        "setup_seconds": setup_seconds,
        "strategy_seconds": strategy_seconds,
        "status": result.get("status", "UNKNOWN"),
        "input_count": result.get("input_count", 0),
        "output_count": result.get("output_count", 0),
        "rejected_count": result.get("rejected_count", 0),
        "database_path": str(database_path.relative_to(PROJECT_ROOT)),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for dataset_name, input_folder in DATASETS.items():
        if not input_folder.exists():
            print(f"Skipping missing dataset: {input_folder}")
            continue

        order_files = sorted(input_folder.glob("orders_*.csv"))

        if not order_files:
            print(f"Skipping dataset with no order files: {input_folder}")
            continue

        print(f"\nBenchmarking dataset: {dataset_name}")
        print(f"Input folder: {input_folder}")
        print(f"Order files: {len(order_files)}")

        for strategy_name, loader in STRATEGIES.items():
            print(f"  Running {strategy_name}...")

            try:
                result = run_strategy(
                    strategy_name=strategy_name,
                    loader=loader,
                    dataset_name=dataset_name,
                    input_folder=input_folder,
                )

            except KeyboardInterrupt:
                result = {
                    "dataset": dataset_name,
                    "strategy": strategy_name,
                    "setup_seconds": 0.0,
                    "strategy_seconds": 0.0,
                    "status": "INTERRUPTED",
                    "input_count": 0,
                    "output_count": 0,
                    "rejected_count": 0,
                    "database_path": (
                        f"output/benchmarks/"
                        f"{dataset_name}_{strategy_name}.duckdb"
                    ),
                }

                results.append(result)
                write_report(results)

                print("\nBenchmark interrupted by user.")
                print(f"Partial report saved to: {REPORT_PATH}")
                return

            except Exception as error:
                result = {
                    "dataset": dataset_name,
                    "strategy": strategy_name,
                    "setup_seconds": 0.0,
                    "strategy_seconds": 0.0,
                    "status": f"ERROR: {type(error).__name__}",
                    "input_count": 0,
                    "output_count": 0,
                    "rejected_count": 0,
                    "database_path": (
                        f"output/benchmarks/"
                        f"{dataset_name}_{strategy_name}.duckdb"
                    ),
                }

                print(f"    Error: {error}")

            results.append(result)
            write_report(results)

            print(
                f"    status={result['status']}, "
                f"strategy_time={format_seconds(result['strategy_seconds'])}s, "
                f"setup_time={format_seconds(result['setup_seconds'])}s"
            )
            print(f"    Updated report: {REPORT_PATH}")

    print(f"\nBenchmark completed. Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
