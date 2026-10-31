import argparse
import csv
import logging
from datetime import date, datetime
from pathlib import Path

from src.run_log import (
    configure_logging,
    create_connection,
    finish_run,
    start_run,
)
from src.validate import validate_dataset


# ---------------------------------------------------------
# TABLE CREATION
# ---------------------------------------------------------

def create_staging_tables(connection):
    """Create staging tables used by the full-refresh strategy."""

    # Staging keeps the current target tables untouched until the new
    # dataset has been loaded and is ready to replace them.
    connection.execute("""
        CREATE TABLE dim_customers_staging (
            customer_id VARCHAR PRIMARY KEY,
            customer_name VARCHAR,
            country VARCHAR,
            created_at TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE fact_orders_staging (
            order_id VARCHAR PRIMARY KEY,
            customer_id VARCHAR,
            order_date DATE,
            amount DECIMAL(12, 2),
            status VARCHAR,
            updated_at TIMESTAMP,
            run_id VARCHAR,
            source_file VARCHAR
        )
    """)

    connection.execute("""
        CREATE TABLE order_status_history_staging (
            order_id VARCHAR,
            status VARCHAR,
            updated_at TIMESTAMP,
            run_id VARCHAR,
            source_file VARCHAR,
            PRIMARY KEY (order_id, updated_at)
        )
    """)

    connection.execute("""
        CREATE TABLE rejects_staging (
            run_id VARCHAR,
            source_file VARCHAR,
            row_number INTEGER,
            reject_reason VARCHAR,
            raw_record VARCHAR
        )
    """)


def create_processed_files_table(
    connection,
    table_name="processed_files",
):
    """Create a file-tracking table for a loading strategy."""

    # Keep strategy tracking separate so one strategy does not prevent
    # another strategy from evaluating the same source files.
    allowed_tables = {
        "processed_files",
        "processed_files_incremental_merge",
        "processed_files_partition_replace",
    }

    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported tracking table: {table_name}")

    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            file_name VARCHAR PRIMARY KEY,
            processed_at TIMESTAMP,
            run_id VARCHAR,
            row_count INTEGER
        )
    """)


def record_processed_files(
    connection,
    files,
    valid_records,
    rejected_records,
    run_id,
    table_name="processed_files",
):
    """Record source files in the selected tracking table."""

    allowed_tables = {
        "processed_files",
        "processed_files_incremental_merge",
        "processed_files_partition_replace",
    }

    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported tracking table: {table_name}")

    processed_at = datetime.now()

    for file_path in files:
        # Count source rows retained by validation or sent to quarantine.
        row_count = sum(
            1
            for row in valid_records
            if row["source_file"] == file_path.name
        ) + sum(
            1
            for row in rejected_records
            if row["source_file"] == file_path.name
        )

        connection.execute(
            f"""
            INSERT INTO {table_name}
            (file_name, processed_at, run_id, row_count)
            VALUES (?, ?, ?, ?)
            """,
            [file_path.name, processed_at, run_id, row_count],
        )


# ---------------------------------------------------------
# SHARED LOADING HELPERS
# ---------------------------------------------------------

def load_customers(connection, customers_file, run_id):
    """Load customer master data into the full-refresh staging table."""

    with open(customers_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        customer_rows = [
            (
                row["customer_id"],
                row["customer_name"],
                row["country"],
                datetime.fromisoformat(row["created_at"]),
            )
            for row in reader
        ]

    if customer_rows:
        connection.executemany(
            """
            INSERT INTO dim_customers_staging
            (customer_id, customer_name, country, created_at)
            VALUES (?, ?, ?, ?)
            """,
            customer_rows,
        )

    logging.info(
        "Customer staging completed: run_id=%s, customers=%s",
        run_id,
        len(customer_rows),
    )

    return len(customer_rows)


def build_latest_orders(valid_records):
    """Return the newest record per order and all distinct history events."""

    latest_orders = {}
    history_records = {}

    for row in valid_records:
        order_id = row["order_id"]
        updated_at = datetime.fromisoformat(row["updated_at"])

        # History is keyed by order and timestamp so separate updates survive.
        history_records[(order_id, updated_at)] = row

        existing = latest_orders.get(order_id)

        if existing is None:
            latest_orders[order_id] = row
            continue

        existing_time = datetime.fromisoformat(existing["updated_at"])

        # A later row wins when timestamps tie, matching the validation rule.
        if updated_at >= existing_time:
            latest_orders[order_id] = row

    return latest_orders, history_records


def make_fact_rows(records, run_id):
    """Convert validated records into rows for fact_orders."""

    return [
        (
            row["order_id"],
            row["customer_id"],
            date.fromisoformat(row["order_date"]),
            row["amount"],
            row["status"],
            datetime.fromisoformat(row["updated_at"]),
            run_id,
            row["source_file"],
        )
        for row in records
    ]


def get_fact_rows_for_run(fact_rows, fail_after=None):
    """Limit inserted rows when deliberately simulating a failure."""

    if fail_after is None:
        return fact_rows

    if fail_after < 1:
        raise ValueError("fail_after must be greater than zero")

    if fail_after > len(fact_rows):
        raise ValueError(
            f"fail_after ({fail_after}) exceeds the number of fact rows "
            f"available for this run ({len(fact_rows)})"
        )

    return fact_rows[:fail_after]


def simulate_failure_after_insert(fact_rows, fail_after=None):
    """Raise an error after the requested number of fact rows are inserted."""

    if fail_after is not None and len(fact_rows) >= fail_after:
        raise RuntimeError(
            f"Simulated failure after inserting {fail_after} fact rows"
        )

def make_history_rows(records, run_id):
    """Convert validated records into rows for order_status_history."""

    return [
        (
            row["order_id"],
            row["status"],
            datetime.fromisoformat(row["updated_at"]),
            run_id,
            row["source_file"],
        )
        for row in records
    ]


def make_reject_rows(rejected_records, run_id):
    """Add run metadata to rejected source records."""

    return [
        (
            run_id,
            row["source_file"],
            row["row_number"],
            row["reject_reason"],
            row["raw_record"],
        )
        for row in rejected_records
    ]


def insert_history_rows(connection, history_rows):
    """Insert distinct order events without duplicating existing history."""

    if history_rows:
        connection.executemany(
            """
            INSERT INTO order_status_history
            (order_id, status, updated_at, run_id, source_file)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (order_id, updated_at) DO NOTHING
            """,
            history_rows,
        )


def insert_reject_rows(connection, reject_rows):
    """Persist rejected rows with their source file and row number."""

    if reject_rows:
        connection.executemany(
            """
            INSERT INTO rejects
            (run_id, source_file, row_number, reject_reason, raw_record)
            VALUES (?, ?, ?, ?, ?)
            """,
            reject_rows,
        )


def swap_staging_tables(connection):
    """Atomically replace target tables with the completed staging tables."""

    # The caller runs this inside a transaction, so the replacement is
    # all-or-nothing if any table operation fails.
    target_tables = [
        "dim_customers",
        "fact_orders",
        "order_status_history",
        "rejects",
    ]

    for table_name in target_tables:
        connection.execute(f"DROP TABLE IF EXISTS {table_name}")

    for table_name in target_tables:
        connection.execute(
            f"ALTER TABLE {table_name}_staging RENAME TO {table_name}"
        )


# ---------------------------------------------------------
# FULL REFRESH
# ---------------------------------------------------------

def full_refresh(
    input_folder="data/raw",
    database_path="data/pipeline.duckdb",
    fail_after=None,
):
    """Rebuild all target tables from every available daily source file."""

    logger = configure_logging()
    input_folder = Path(input_folder)
    connection = create_connection(database_path)
    run_id = start_run(connection, "full_refresh")

    input_count = 0
    output_count = 0
    rejected_count = 0
    transaction_started = False

    try:
        valid_records, rejected_records, duplicate_records = validate_dataset(
            input_folder,
            "output",
        )

        input_count = (
            len(valid_records)
            + len(rejected_records)
            + len(duplicate_records)
        )
        rejected_count = len(rejected_records)

        all_files = sorted(input_folder.glob("orders_*.csv"))

        connection.execute("BEGIN TRANSACTION")
        transaction_started = True

        create_staging_tables(connection)
        create_processed_files_table(connection, "processed_files")

        load_customers(
            connection,
            input_folder / "customers.csv",
            run_id,
        )

        latest_orders, history_records = build_latest_orders(valid_records)

        fact_rows = make_fact_rows(latest_orders.values(), run_id)
        history_rows = make_history_rows(history_records.values(), run_id)
        reject_rows = make_reject_rows(rejected_records, run_id)

        rows_to_insert = get_fact_rows_for_run(fact_rows, fail_after)

        if rows_to_insert:
            connection.executemany(
                """
                INSERT INTO fact_orders_staging
                (
                    order_id, customer_id, order_date, amount,
                    status, updated_at, run_id, source_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )

        simulate_failure_after_insert(rows_to_insert, fail_after)

        if history_rows:
            connection.executemany(
                """
                INSERT INTO order_status_history_staging
                (order_id, status, updated_at, run_id, source_file)
                VALUES (?, ?, ?, ?, ?)
                """,
                history_rows,
            )

        if reject_rows:
            connection.executemany(
                """
                INSERT INTO rejects_staging
                (run_id, source_file, row_number, reject_reason, raw_record)
                VALUES (?, ?, ?, ?, ?)
                """,
                reject_rows,
            )

        # Swap only after every staging table has been populated successfully.
        swap_staging_tables(connection)

        # Full Refresh resets its own file markers to match the files just read.
        connection.execute("DELETE FROM processed_files")

        record_processed_files(
            connection,
            all_files,
            valid_records,
            rejected_records,
            run_id,
            table_name="processed_files",
        )

        connection.execute("COMMIT")
        transaction_started = False

        output_count = len(fact_rows)

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
        )

        logger.info(
            "Full refresh successful: run_id=%s, orders=%s, history=%s",
            run_id,
            output_count,
            len(history_rows),
        )

        return {
            "run_id": run_id,
            "input_count": input_count,
            "output_count": output_count,
            "rejected_count": rejected_count,
            "history_count": len(history_rows),
            "status": "SUCCESS",
        }

    except Exception as error:
        if transaction_started:
            connection.execute("ROLLBACK")

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
            failure_reason=str(error),
        )

        logger.exception("Full refresh failed: run_id=%s", run_id)
        raise

    finally:
        connection.close()


# ---------------------------------------------------------
# INCREMENTAL MERGE
# ---------------------------------------------------------

def incremental_merge(
    input_folder="data/raw",
    database_path="data/pipeline.duckdb",
    fail_after=None,
):
    """Process unprocessed files and merge newer order versions."""

    logger = configure_logging()
    input_folder = Path(input_folder)
    connection = create_connection(database_path)
    run_id = start_run(connection, "incremental_merge")

    input_count = 0
    output_count = 0
    rejected_count = 0
    transaction_started = False

    try:
        create_processed_files_table(connection, "processed_files_incremental_merge")

        all_files = sorted(input_folder.glob("orders_*.csv"))

        processed_files = {
            row[0]
            for row in connection.execute(
                "SELECT file_name FROM processed_files_incremental_merge"
            ).fetchall()
        }

        new_files = [
            file_path
            for file_path in all_files
            if file_path.name not in processed_files
        ]

        logger.info(
            "Incremental files discovered: total=%s, new=%s",
            len(all_files),
            len(new_files),
        )

        if not new_files:
            finish_run(connection, run_id, 0, 0, 0)

            return {
                "run_id": run_id,
                "input_count": 0,
                "output_count": 0,
                "rejected_count": 0,
                "processed_files": 0,
                "status": "SUCCESS",
            }

        valid_records, rejected_records, duplicate_records = validate_dataset(
            input_folder,
            "output",
            order_files=new_files,
        )

        input_count = (
            len(valid_records)
            + len(rejected_records)
            + len(duplicate_records)
        )
        output_count = len(valid_records)
        rejected_count = len(rejected_records)

        connection.execute("BEGIN TRANSACTION")
        transaction_started = True

        history_rows = make_history_rows(valid_records, run_id)
        insert_history_rows(connection, history_rows)

        fact_rows = make_fact_rows(valid_records, run_id)

        rows_to_insert = get_fact_rows_for_run(fact_rows, fail_after)

        if rows_to_insert:
            connection.executemany(
                """
                INSERT INTO fact_orders
                (
                    order_id, customer_id, order_date, amount,
                    status, updated_at, run_id, source_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (order_id) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    order_date = excluded.order_date,
                    amount = excluded.amount,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    run_id = excluded.run_id,
                    source_file = excluded.source_file
                WHERE excluded.updated_at > fact_orders.updated_at
                """,
                rows_to_insert,
            )

        simulate_failure_after_insert(rows_to_insert, fail_after)

        reject_rows = make_reject_rows(rejected_records, run_id)
        insert_reject_rows(connection, reject_rows)

        # File markers commit with the data, so a failed load can be retried.
        record_processed_files(
            connection,
            new_files,
            valid_records,
            rejected_records,
            run_id,
            table_name="processed_files_incremental_merge",
        )

        connection.execute("COMMIT")
        transaction_started = False

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
        )

        logger.info(
            "Incremental merge successful: run_id=%s, files=%s, records=%s",
            run_id,
            len(new_files),
            output_count,
        )

        return {
            "run_id": run_id,
            "input_count": input_count,
            "output_count": output_count,
            "rejected_count": rejected_count,
            "processed_files": len(new_files),
            "status": "SUCCESS",
        }

    except Exception as error:
        if transaction_started:
            connection.execute("ROLLBACK")

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
            failure_reason=str(error),
        )

        logger.exception("Incremental merge failed: run_id=%s", run_id)
        raise

    finally:
        connection.close()


# ---------------------------------------------------------
# PARTITION REPLACEMENT
# ---------------------------------------------------------

def partition_replace(
    input_folder="data/raw",
    database_path="data/pipeline.duckdb",
    fail_after=None,
):
    """Rebuild only affected order-date partitions from complete source data."""

    logger = configure_logging()
    input_folder = Path(input_folder)
    connection = create_connection(database_path)
    run_id = start_run(connection, "partition_replace")

    input_count = 0
    output_count = 0
    rejected_count = 0
    transaction_started = False

    tracking_table = "processed_files_partition_replace"

    try:
        # Partition replacement has its own file history, independent of
        # Full Refresh and Incremental Merge.
        create_processed_files_table(connection, tracking_table)

        all_files = sorted(input_folder.glob("orders_*.csv"))

        processed_files = {
            row[0]
            for row in connection.execute(
                f"SELECT file_name FROM {tracking_table}"
            ).fetchall()
        }

        new_files = [
            file_path
            for file_path in all_files
            if file_path.name not in processed_files
        ]

        logger.info(
            "Partition replacement files discovered: total=%s, new=%s",
            len(all_files),
            len(new_files),
        )

        if not new_files:
            finish_run(connection, run_id, 0, 0, 0)

            return {
                "run_id": run_id,
                "input_count": 0,
                "output_count": 0,
                "rejected_count": 0,
                "replaced_partitions": 0,
                "processed_files": 0,
                "status": "SUCCESS",
            }

        # Validate new files to identify affected dates and quarantine their
        # rejected rows. The full source set is read separately for rebuilding.
        new_valid_records, rejected_records, duplicate_records = validate_dataset(
            input_folder,
            "output",
            order_files=new_files,
        )

        input_count = (
            len(new_valid_records)
            + len(rejected_records)
            + len(duplicate_records)
        )
        rejected_count = len(rejected_records)

        affected_dates = {
            date.fromisoformat(row["order_date"])
            for row in new_valid_records
        }

        affected_order_ids = {
            row["order_id"]
            for row in new_valid_records
        }

        # A partition must be rebuilt from all source files, not just the
        # new file, otherwise older orders in that date would be lost.
        all_valid_records, _, _ = validate_dataset(
            input_folder,
            "output",
            order_files=all_files,
        )

        # Include complete affected dates and any incoming order whose date
        # changed, so its old fact-table location is also removed.
        replacement_records = [
            row
            for row in all_valid_records
            if (
                date.fromisoformat(row["order_date"]) in affected_dates
                or row["order_id"] in affected_order_ids
            )
        ]


        latest_orders, history_records = build_latest_orders(
            replacement_records
        )

        fact_rows = make_fact_rows(latest_orders.values(), run_id)
        history_rows = make_history_rows(history_records.values(), run_id)
        reject_rows = make_reject_rows(rejected_records, run_id)

        connection.execute("BEGIN TRANSACTION")
        transaction_started = True

        # Delete only affected date partitions and incoming order IDs.
        # All other order dates remain unchanged.
        delete_conditions = []
        delete_parameters = []

        if affected_dates:
            date_placeholders = ", ".join("?" for _ in affected_dates)
            delete_conditions.append(
                f"order_date IN ({date_placeholders})"
            )
            delete_parameters.extend(sorted(affected_dates))

        if affected_order_ids:
            order_placeholders = ", ".join(
                "?" for _ in affected_order_ids
            )
            delete_conditions.append(
                f"order_id IN ({order_placeholders})"
            )
            delete_parameters.extend(sorted(affected_order_ids))

        if delete_conditions:
            connection.execute(
                "DELETE FROM fact_orders WHERE "
                + " OR ".join(delete_conditions),
                delete_parameters,
            )

        rows_to_insert = get_fact_rows_for_run(fact_rows, fail_after)

        if rows_to_insert:
            connection.executemany(
                """
                INSERT INTO fact_orders
                (
                    order_id, customer_id, order_date, amount,
                    status, updated_at, run_id, source_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )

        simulate_failure_after_insert(rows_to_insert, fail_after)

        # History is append-only. Existing events remain, and only missing
        # order/timestamp combinations are inserted.
        insert_history_rows(connection, history_rows)
        insert_reject_rows(connection, reject_rows)

        record_processed_files(
            connection,
            new_files,
            new_valid_records,
            rejected_records,
            run_id,
            table_name=tracking_table,
        )

        connection.execute("COMMIT")
        transaction_started = False

        output_count = len(fact_rows)

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
        )

        logger.info(
            "Partition replacement successful: run_id=%s, dates=%s, orders=%s",
            run_id,
            len(affected_dates),
            output_count,
        )

        return {
            "run_id": run_id,
            "input_count": input_count,
            "output_count": output_count,
            "rejected_count": rejected_count,
            "replaced_partitions": len(affected_dates),
            "processed_files": len(new_files),
            "status": "SUCCESS",
        }

    except Exception as error:
        if transaction_started:
            connection.execute("ROLLBACK")

        finish_run(
            connection,
            run_id,
            input_count,
            output_count,
            rejected_count,
            failure_reason=str(error),
        )

        logger.exception("Partition replacement failed: run_id=%s", run_id)
        raise

    finally:
        connection.close()


# ---------------------------------------------------------
# COMMAND-LINE ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run one of the three data loading strategies."
    )

    parser.add_argument(
        "--strategy",
        choices=[
            "full_refresh",
            "incremental_merge",
            "partition_replace",
        ],
        default="full_refresh",
        help="Choose the loading strategy.",
    )

    parser.add_argument(
        "--database-path",
        default="data/pipeline.duckdb",
        help="Path to the DuckDB database file (default: data/pipeline.duckdb).",
    )

    parser.add_argument(
        "--fail-after",
        type=int,
        default=None,
        help="Simulate a failure after inserting this many fact rows; use a positive integer.",
    )

    args = parser.parse_args()

    # Select a loader from the command line without editing this file.
    if args.strategy == "full_refresh":
        result = full_refresh(
            database_path=args.database_path,
            fail_after=args.fail_after,
        )
    elif args.strategy == "incremental_merge":
        result = incremental_merge(
            database_path=args.database_path,
            fail_after=args.fail_after,
        )
    else:
        result = partition_replace(
            database_path=args.database_path,
            fail_after=args.fail_after,
        )

    print("\nPipeline result")
    for key, value in result.items():
        print(f"{key}: {value}")