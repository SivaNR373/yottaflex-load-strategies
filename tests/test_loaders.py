import csv

import duckdb
import pytest

from src.generator import generate_data
from src.loaders import (
    full_refresh,
    incremental_merge,
    partition_replace,
)


@pytest.fixture
def source_data(tmp_path):
    """Generate a fresh, predictable dataset for each test."""

    raw_folder = tmp_path / "raw"

    generate_data(
        size="small",
        output_folder=str(raw_folder),
        seed=42,
    )

    return raw_folder


@pytest.fixture
def database_path(tmp_path):
    """Give each test its own isolated DuckDB database."""

    return str(tmp_path / "test_pipeline.duckdb")


def get_table_count(database_path, table_name):
    """Read a table count without changing the database."""

    connection = duckdb.connect(database_path, read_only=True)

    try:
        return connection.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
    finally:
        connection.close()


def test_full_refresh_loads_expected_data(source_data, database_path):
    result = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["output_count"] == 201
    assert result["rejected_count"] == 8

    assert get_table_count(database_path, "dim_customers") == 30
    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215
    assert get_table_count(database_path, "rejects") == 8
    assert get_table_count(database_path, "processed_files") == 5


def test_full_refresh_can_run_again(source_data, database_path):
    # A full refresh should rebuild the tables, not append duplicates.
    first_run = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    second_run = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert first_run["status"] == "SUCCESS"
    assert second_run["status"] == "SUCCESS"

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215
    assert get_table_count(database_path, "rejects") == 8


def test_incremental_merge_processes_new_files(source_data, database_path):
    # Initialize the warehouse before running the incremental strategy.
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    result = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["processed_files"] == 5

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215


def test_incremental_merge_skips_processed_files(source_data, database_path):
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    first_run = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    second_run = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert first_run["status"] == "SUCCESS"
    assert second_run["status"] == "SUCCESS"
    assert second_run["processed_files"] == 0

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215


def test_partition_replace_rebuilds_affected_partitions(
    source_data,
    database_path,
):
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    result = partition_replace(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["processed_files"] == 5
    assert result["replaced_partitions"] == 4

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215


def test_partition_replace_skips_processed_files(source_data, database_path):
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    first_run = partition_replace(
        input_folder=str(source_data),
        database_path=database_path,
    )

    second_run = partition_replace(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert first_run["status"] == "SUCCESS"
    assert second_run["status"] == "SUCCESS"
    assert second_run["processed_files"] == 0
    assert second_run["replaced_partitions"] == 0

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215
    assert get_table_count(database_path, "rejects") == 16


def test_incremental_merge_updated_at_guard_and_history(
    source_data,
    database_path,
):
    # Create the target tables and load the original dataset.
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    # Incremental Merge has its own file tracker. Register the original
    # five files first so the two test events are processed separately.
    initial_result = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert initial_result["status"] == "SUCCESS"
    assert initial_result["processed_files"] == 5

    newer_event = {
        "order_id": "ORD-000001",
        "customer_id": "CUST-0001",
        "order_date": "2026-10-25",
        "amount": "222.00",
        "status": "shipped",
        "updated_at": "2026-10-30T23:59:00",
    }

    older_event = {
        "order_id": "ORD-000001",
        "customer_id": "CUST-0001",
        "order_date": "2026-10-25",
        "amount": "150.00",
        "status": "paid",
        "updated_at": "2026-10-30T23:58:00",
    }

    # Separate files let us process each event independently.
    events = [
        ("orders_2026-10-30.csv", newer_event),
        ("orders_2026-10-31.csv", older_event),
    ]

    for filename, event in events:
        file_path = source_data / filename

        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(event.keys()),
            )
            writer.writeheader()
            writer.writerow(event)

        result = incremental_merge(
            input_folder=str(source_data),
            database_path=database_path,
        )

        assert result["status"] == "SUCCESS"
        assert result["processed_files"] == 1

    connection = duckdb.connect(database_path, read_only=True)

    try:
        current_order = connection.execute(
            """
            SELECT amount, status, updated_at
            FROM fact_orders
            WHERE order_id = ?
            """,
            ["ORD-000001"],
        ).fetchone()

        # The older event must not overwrite the newer event.
        assert current_order[0] == pytest.approx(222.00)
        assert current_order[1] == "shipped"
        assert str(current_order[2]) == "2026-10-30 23:59:00"

        history = connection.execute(
            """
            SELECT status, updated_at
            FROM order_status_history
            WHERE order_id = ?
            ORDER BY updated_at
            """,
            ["ORD-000001"],
        ).fetchall()

        history_events = {
            (status, str(updated_at))
            for status, updated_at in history
        }

        # Both distinct events should remain in the audit history.
        assert (
            "shipped",
            "2026-10-30 23:59:00",
        ) in history_events

        assert (
            "paid",
            "2026-10-30 23:58:00",
        ) in history_events

    finally:
        connection.close()


def test_incremental_merge_rolls_back_and_retries_after_failure(
    source_data,
    database_path,
    monkeypatch,
):
    import src.loaders as loaders

    # Load the original data and register its files.
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    initial_result = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert initial_result["status"] == "SUCCESS"
    assert initial_result["processed_files"] == 5

    # Create a new order event that we will use to simulate a failure.
    new_event = {
        "order_id": "ORD-000001",
        "customer_id": "CUST-0001",
        "order_date": "2026-10-25",
        "amount": "333.00",
        "status": "delivered",
        "updated_at": "2026-10-30T23:59:30",
    }

    new_file = source_data / "orders_2026-11-01.csv"

    with open(new_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(new_event.keys()))
        writer.writeheader()
        writer.writerow(new_event)

    # Capture the original order so we can verify rollback.
    connection = duckdb.connect(database_path, read_only=True)
    try:
        baseline_order = connection.execute(
            """
            SELECT amount, status, updated_at
            FROM fact_orders
            WHERE order_id = ?
            """,
            ["ORD-000001"],
        ).fetchone()
    finally:
        connection.close()

    original_insert_history_rows = loaders.insert_history_rows

    def insert_history_then_fail(connection, history_rows):
        # Insert history, then deliberately fail inside the transaction.
        original_insert_history_rows(connection, history_rows)
        raise RuntimeError("Simulated failure after history insert")

    # Inject the failure after a database write has occurred.
    with monkeypatch.context() as patch:
        patch.setattr(
            loaders,
            "insert_history_rows",
            insert_history_then_fail,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated failure after history insert",
        ):
            incremental_merge(
                input_folder=str(source_data),
                database_path=database_path,
            )

    # Verify that the failed transaction left no partial changes.
    connection = duckdb.connect(database_path, read_only=True)

    try:
        current_order = connection.execute(
            """
            SELECT amount, status, updated_at
            FROM fact_orders
            WHERE order_id = ?
            """,
            ["ORD-000001"],
        ).fetchone()

        assert current_order == baseline_order

        failed_event_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM order_status_history
            WHERE order_id = ?
              AND updated_at = ?
            """,
            ["ORD-000001", "2026-10-30 23:59:30"],
        ).fetchone()[0]

        assert failed_event_count == 0

        processed_file_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM processed_files_incremental_merge
            WHERE file_name = ?
            """,
            [new_file.name],
        ).fetchone()[0]

        assert processed_file_count == 0

        failed_run_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM run_log
            WHERE strategy = 'incremental_merge'
              AND status = 'FAILED'
              AND failure_reason LIKE '%Simulated failure after history insert%'
            """
        ).fetchone()[0]

        assert failed_run_count == 1

    finally:
        connection.close()

    # Retry the same file. It should now process successfully.
    retry_result = incremental_merge(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert retry_result["status"] == "SUCCESS"
    assert retry_result["processed_files"] == 1

    connection = duckdb.connect(database_path, read_only=True)

    try:
        retried_order = connection.execute(
            """
            SELECT amount, status, updated_at
            FROM fact_orders
            WHERE order_id = ?
            """,
            ["ORD-000001"],
        ).fetchone()

        assert retried_order[0] == pytest.approx(333.00)
        assert retried_order[1] == "delivered"
        assert str(retried_order[2]) == "2026-10-30 23:59:30"

        retried_history_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM order_status_history
            WHERE order_id = ?
              AND updated_at = ?
            """,
            ["ORD-000001", "2026-10-30 23:59:30"],
        ).fetchone()[0]

        assert retried_history_count == 1

        processed_file_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM processed_files_incremental_merge
            WHERE file_name = ?
            """,
            [new_file.name],
        ).fetchone()[0]

        assert processed_file_count == 1

    finally:
        connection.close()
