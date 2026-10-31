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



def test_full_refresh_rolls_back_and_retries_after_failure(
    source_data,
    database_path,
    monkeypatch,
):
    from src import loaders

    # First, create a valid production baseline.
    initial_result = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert initial_result["status"] == "SUCCESS"

    # Capture a production record before simulating the failure.
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

    original_swap = loaders.swap_staging_tables

    def swap_then_fail(connection):
        # Complete the table swap, then simulate a failure before COMMIT.
        original_swap(connection)
        raise RuntimeError("Simulated failure after table swap")

    # Inject the failure after the production tables have been swapped.
    with monkeypatch.context() as patch:
        patch.setattr(
            loaders,
            "swap_staging_tables",
            swap_then_fail,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated failure after table swap",
        ):
            full_refresh(
                input_folder=str(source_data),
                database_path=database_path,
            )

    # The failed transaction must restore the original production tables.
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

        assert connection.execute(
            "SELECT COUNT(*) FROM dim_customers"
        ).fetchone()[0] == 30

        assert connection.execute(
            "SELECT COUNT(*) FROM fact_orders"
        ).fetchone()[0] == 201

        assert connection.execute(
            "SELECT COUNT(*) FROM order_status_history"
        ).fetchone()[0] == 215

        assert connection.execute(
            "SELECT COUNT(*) FROM rejects"
        ).fetchone()[0] == 8

        assert connection.execute(
            "SELECT COUNT(*) FROM processed_files"
        ).fetchone()[0] == 5

        failed_run_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM run_log
            WHERE strategy = 'full_refresh'
              AND status = 'FAILED'
              AND failure_reason LIKE '%Simulated failure after table swap%'
            """
        ).fetchone()[0]

        assert failed_run_count == 1

    finally:
        connection.close()

    # Retry the same full refresh. It should complete successfully.
    retry_result = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert retry_result["status"] == "SUCCESS"
    assert retry_result["output_count"] == 201

    assert get_table_count(database_path, "fact_orders") == 201
    assert get_table_count(database_path, "order_status_history") == 215
    assert get_table_count(database_path, "rejects") == 8
    assert get_table_count(database_path, "processed_files") == 5


def test_partition_replace_rolls_back_and_retries_after_failure(
    source_data,
    database_path,
    monkeypatch,
):
    from src import loaders

    # Initialize the warehouse and register the original source files.
    full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    initial_result = partition_replace(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert initial_result["status"] == "SUCCESS"
    assert initial_result["processed_files"] == 5

    # Add a newer event for an existing order in an affected partition.
    new_event = {
        "order_id": "ORD-000001",
        "customer_id": "CUST-0001",
        "order_date": "2026-10-25",
        "amount": "444.00",
        "status": "shipped",
        "updated_at": "2026-11-01T10:00:00",
    }

    new_file = source_data / "orders_2026-11-01.csv"

    with open(new_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(new_event.keys()))
        writer.writeheader()
        writer.writerow(new_event)

    # Capture the existing production state before the failure.
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

        baseline_fact_count = connection.execute(
            "SELECT COUNT(*) FROM fact_orders"
        ).fetchone()[0]

        baseline_history_count = connection.execute(
            "SELECT COUNT(*) FROM order_status_history"
        ).fetchone()[0]

        baseline_reject_count = connection.execute(
            "SELECT COUNT(*) FROM rejects"
        ).fetchone()[0]

    finally:
        connection.close()

    original_insert_history_rows = loaders.insert_history_rows

    def insert_history_then_fail(connection, history_rows):
        # The fact partition has already been replaced at this point.
        original_insert_history_rows(connection, history_rows)
        raise RuntimeError("Simulated failure after partition replacement")

    # Inject a failure inside the transaction after fact records are written.
    with monkeypatch.context() as patch:
        patch.setattr(
            loaders,
            "insert_history_rows",
            insert_history_then_fail,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated failure after partition replacement",
        ):
            partition_replace(
                input_folder=str(source_data),
                database_path=database_path,
            )

    # Verify that the failed transaction restored the original warehouse.
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

        assert connection.execute(
            "SELECT COUNT(*) FROM fact_orders"
        ).fetchone()[0] == baseline_fact_count

        assert connection.execute(
            "SELECT COUNT(*) FROM order_status_history"
        ).fetchone()[0] == baseline_history_count

        assert connection.execute(
            "SELECT COUNT(*) FROM rejects"
        ).fetchone()[0] == baseline_reject_count

        processed_file_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM processed_files_partition_replace
            WHERE file_name = ?
            """,
            [new_file.name],
        ).fetchone()[0]

        assert processed_file_count == 0

        failed_run_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM run_log
            WHERE strategy = 'partition_replace'
              AND status = 'FAILED'
              AND failure_reason LIKE
                  '%Simulated failure after partition replacement%'
            """
        ).fetchone()[0]

        assert failed_run_count == 1

    finally:
        connection.close()

    # Retry the same file. It should now be processed successfully.
    retry_result = partition_replace(
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

        assert retried_order[0] == pytest.approx(444.00)
        assert retried_order[1] == "shipped"
        assert str(retried_order[2]) == "2026-11-01 10:00:00"

        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM processed_files_partition_replace
            WHERE file_name = ?
            """,
            [new_file.name],
        ).fetchone()[0] == 1

        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM order_status_history
            WHERE order_id = ?
              AND updated_at = ?
            """,
            ["ORD-000001", "2026-11-01 10:00:00"],
        ).fetchone()[0] == 1

    finally:
        connection.close()

def test_full_refresh_with_no_order_files_preserves_existing_data(
    source_data,
    database_path,
):
    # Load valid data first.
    first_result = full_refresh(
        input_folder=str(source_data),
        database_path=database_path,
    )

    assert first_result["status"] == "SUCCESS"
    assert get_table_count(database_path, "fact_orders") == 201

    # Create a folder containing customers.csv but no daily order files.
    empty_folder = source_data.parent / "empty_raw"
    empty_folder.mkdir()

    customers_file = source_data / "customers.csv"
    (empty_folder / "customers.csv").write_bytes(
        customers_file.read_bytes()
    )

    # An empty full refresh should fail safely.
    with pytest.raises(ValueError, match="No order files found"):
        full_refresh(
            input_folder=str(empty_folder),
            database_path=database_path,
        )

    # Existing warehouse data must remain unchanged.
    assert get_table_count(database_path, "fact_orders") == 201

def test_all_loading_strategies_produce_equivalent_business_data(
    source_data,
    tmp_path,
):
    strategies = {
        "full_refresh": full_refresh,
        "incremental_merge": incremental_merge,
        "partition_replace": partition_replace,
    }

    business_columns = {
        "dim_customers": [
            "customer_id",
            "customer_name",
            "country",
            "created_at",
        ],
        "fact_orders": [
            "order_id",
            "customer_id",
            "order_date",
            "amount",
            "status",
            "updated_at",
        ],
        "order_status_history": [
            "order_id",
            "status",
            "updated_at",
        ],
    }

    results = {}

    for strategy_name, loader in strategies.items():
        database_path = tmp_path / f"{strategy_name}.duckdb"

        # Initialize the database schema and customer dimension.
        full_refresh(
            input_folder=source_data,
            database_path=database_path,
        )

        # Run the selected strategy against the same source dataset.
        if strategy_name != "full_refresh":
            loader(
                input_folder=source_data,
                database_path=database_path,
            )

        connection = duckdb.connect(str(database_path), read_only=True)

        results[strategy_name] = {}

        for table_name, columns in business_columns.items():
            selected_columns = ", ".join(columns)

            rows = connection.execute(
                f"""
                SELECT {selected_columns}
                FROM {table_name}
                ORDER BY ALL
                """
            ).fetchall()

            results[strategy_name][table_name] = rows

        connection.close()

    # Compare business data, excluding run-specific metadata.
    full_refresh_results = results["full_refresh"]

    for strategy_name in ["incremental_merge", "partition_replace"]:
        for table_name in business_columns:
            assert (
                full_refresh_results[table_name]
                == results[strategy_name][table_name]
            ), (
                f"{strategy_name} produced different business data "
                f"for table {table_name}"
            )
    strategies = {
        "full_refresh": full_refresh,
        "incremental_merge": incremental_merge,
        "partition_replace": partition_replace,
    }

    business_tables = [
        "dim_customers",
        "fact_orders",
        "order_status_history",
    ]

    results = {}

    # Run each strategy and collect its results.
    for strategy_name, loader in strategies.items():
        database_path = str(tmp_path / f"{strategy_name}.duckdb")

        # Full Refresh initializes the warehouse tables.
        full_refresh(
            input_folder=str(source_data),
            database_path=database_path,
        )

        # Run the selected strategy for incremental and partition tests.
        if strategy_name != "full_refresh":
            loader(
                input_folder=str(source_data),
                database_path=database_path,
            )

        connection = duckdb.connect(database_path, read_only=True)

        try:
            strategy_results = {}

            for table_name in business_tables:
                rows = connection.execute(
                    f"SELECT * FROM {table_name} ORDER BY ALL"
                ).fetchall()

                strategy_results[table_name] = rows

            results[strategy_name] = strategy_results

        finally:
            connection.close()

    # Compare results only after all three strategies have finished.
        # Compare business data while excluding execution-specific metadata.
    comparison_columns = {
        "dim_customers": [
            "customer_id",
            # Add the remaining business columns from dim_customers here.
        ],
        "fact_orders": [
            "order_id",
            "customer_id",
            "order_date",
            "amount",
            "status",
            "updated_at",
        ],
        "order_status_history": [
            # We'll inspect this table's schema before defining its columns.
        ],
    }