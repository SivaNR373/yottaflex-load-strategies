import argparse
import hashlib
import json
from pathlib import Path

import duckdb


DEFAULT_DATABASES = {
    "full_refresh": "output/reconcile_full_refresh.duckdb",
    "incremental_merge": "output/reconcile_incremental_merge.duckdb",
    "partition_replace": "output/reconcile_partition_replace.duckdb",
}

ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "order_date",
    "amount",
    "status",
    "updated_at",
]

HISTORY_COLUMNS = [
    "order_id",
    "status",
    "updated_at",
]


def fetch_business_rows(connection, table_name, columns):
    """Fetch business columns in a stable order for comparison."""

    selected_columns = ", ".join(columns)

    return connection.execute(
        f"""
        SELECT {selected_columns}
        FROM {table_name}
        ORDER BY {selected_columns}
        """
    ).fetchall()


def canonical_hash(rows):
    """Create a stable SHA-256 hash from business rows."""

    serialized = json.dumps(
        rows,
        default=str,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_database_metrics(database_path):
    """Read business metrics from one strategy database."""

    if not Path(database_path).exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}"
        )

    connection = duckdb.connect(
        str(database_path),
        read_only=True,
    )

    try:
        order_count = connection.execute(
            "SELECT COUNT(*) FROM fact_orders"
        ).fetchone()[0]

        total_amount = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM fact_orders"
        ).fetchone()[0]

        status_rows = connection.execute(
            """
            SELECT status, COUNT(*)
            FROM fact_orders
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()

        order_rows = fetch_business_rows(
            connection,
            "fact_orders",
            ORDER_COLUMNS,
        )

        history_rows = fetch_business_rows(
            connection,
            "order_status_history",
            HISTORY_COLUMNS,
        )

        reject_count = connection.execute(
            "SELECT COUNT(*) FROM rejects"
        ).fetchone()[0]

        return {
            "database_path": database_path,
            "order_count": order_count,
            "total_amount": total_amount,
            "status_counts": status_rows,
            "order_hash": canonical_hash(order_rows),
            "history_count": len(history_rows),
            "history_hash": canonical_hash(history_rows),
            "reject_count": reject_count,
        }

    finally:
        connection.close()


def write_report(results, output_path):
    """Write a Markdown reconciliation report."""

    strategy_names = list(results.keys())
    baseline_name = strategy_names[0]
    baseline = results[baseline_name]

    all_orders_match = all(
        result["order_hash"] == baseline["order_hash"]
        for result in results.values()
    )

    all_history_match = all(
        result["history_hash"] == baseline["history_hash"]
        for result in results.values()
    )

    all_reject_counts_match = all(
        result["reject_count"] == baseline["reject_count"]
        for result in results.values()
    )

    lines = [
        "# Reconciliation Report",
        "",
        "## Summary",
        "",
        f"- Business order data equivalent: **{all_orders_match}**",
        f"- Order status history equivalent: **{all_history_match}**",
        f"- Reject counts equivalent: **{all_reject_counts_match}**",
        "",
        "## Strategy Metrics",
        "",
        "| Strategy | Final orders | Total amount | Rejects | History rows |",
        "|---|---:|---:|---:|---:|",
    ]

    for strategy, result in results.items():
        lines.append(
            f"| {strategy} "
            f"| {result['order_count']} "
            f"| {result['total_amount']} "
            f"| {result['reject_count']} "
            f"| {result['history_count']} |"
        )

    lines.extend([
        "",
        "## Status Counts",
        "",
        "| Strategy | Status | Count |",
        "|---|---|---:|",
    ])

    for strategy, result in results.items():
        for status, count in result["status_counts"]:
            lines.append(
                f"| {strategy} | {status} | {count} |"
            )

    lines.extend([
        "",
        "## Business Data Hashes",
        "",
        "| Strategy | Orders SHA-256 | History SHA-256 |",
        "|---|---|---|",
    ])

    for strategy, result in results.items():
        lines.append(
            f"| {strategy} "
            f"| `{result['order_hash']}` "
            f"| `{result['history_hash']}` |"
        )

    lines.extend([
        "",
        "## Database Locations",
        "",
    ])

    for strategy, result in results.items():
        lines.append(
            f"- **{strategy}:** `{result['database_path']}`"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Hashes exclude run-specific metadata such as `run_id` and `source_file`.",
        "- Order hashes compare the final business columns in `fact_orders`.",
        "- History hashes compare `order_id`, `status`, and `updated_at`.",
        "- Reject counts are compared, but reject contents are not yet hashed.",
        "- `run_log.output_count` is not used as the final target order count.",
        "",
    ])

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare final business data across loading strategies."
    )

    parser.add_argument(
        "--full-refresh",
        default=DEFAULT_DATABASES["full_refresh"],
    )

    parser.add_argument(
        "--incremental-merge",
        default=DEFAULT_DATABASES["incremental_merge"],
    )

    parser.add_argument(
        "--partition-replace",
        default=DEFAULT_DATABASES["partition_replace"],
    )

    parser.add_argument(
        "--output",
        default="output/reconciliation_report.md",
    )

    args = parser.parse_args()

    database_paths = {
        "full_refresh": args.full_refresh,
        "incremental_merge": args.incremental_merge,
        "partition_replace": args.partition_replace,
    }

    results = {}

    for strategy, database_path in database_paths.items():
        print(f"Reconciling {strategy}...")

        results[strategy] = get_database_metrics(
            database_path
        )

    write_report(results, args.output)

    print("\nReconciliation results")
    print("-----------------------------------")

    for strategy, result in results.items():
        print(f"{strategy}:")
        print(f"  Final orders: {result['order_count']}")
        print(f"  Total amount: {result['total_amount']}")
        print(f"  Rejects: {result['reject_count']}")
        print(f"  History rows: {result['history_count']}")

    baseline = results["full_refresh"]

    orders_match = all(
        result["order_hash"] == baseline["order_hash"]
        for result in results.values()
    )

    history_match = all(
        result["history_hash"] == baseline["history_hash"]
        for result in results.values()
    )

    print("-----------------------------------")
    print(f"Order data equivalent: {orders_match}")
    print(f"History equivalent: {history_match}")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()