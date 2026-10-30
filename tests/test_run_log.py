
import logging

import pytest

from src.run_log import (
    configure_logging,
    create_connection,
    finish_run,
    start_run,
)


@pytest.fixture
def connection(tmp_path):
    database_path = tmp_path / "test_pipeline.duckdb"
    con = create_connection(str(database_path))

    yield con

    con.close()


def test_run_log_table_is_created(connection):
    columns = connection.execute(
        "DESCRIBE run_log"
    ).fetchall()

    column_names = [column[0] for column in columns]

    assert column_names == [
        "run_id",
        "strategy",
        "start_time",
        "end_time",
        "input_count",
        "output_count",
        "rejected_count",
        "status",
        "failure_reason",
    ]


def test_successful_run_is_recorded(connection):
    run_id = start_run(connection, "full_refresh")

    finish_run(
        connection,
        run_id,
        input_count=216,
        output_count=201,
        rejected_count=8,
    )

    result = connection.execute(
        """
        SELECT strategy, input_count, output_count,
               rejected_count, status, failure_reason
        FROM run_log
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchone()

    assert result == (
        "full_refresh",
        216,
        201,
        8,
        "SUCCESS",
        None,
    )


def test_failed_run_records_failure_reason(connection):
    run_id = start_run(connection, "incremental_merge")

    finish_run(
        connection,
        run_id,
        input_count=100,
        output_count=0,
        rejected_count=0,
        failure_reason="Simulated database failure",
    )

    result = connection.execute(
        """
        SELECT status, failure_reason
        FROM run_log
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchone()

    assert result == (
        "FAILED",
        "Simulated database failure",
    )


def test_new_run_starts_with_running_status(connection):
    run_id = start_run(connection, "full_refresh")

    result = connection.execute(
        """
        SELECT status, end_time
        FROM run_log
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchone()

    assert result == ("RUNNING", None)


def test_python_logging_writes_to_file(tmp_path):
    log_file = tmp_path / "pipeline.log"

    logger = configure_logging(str(log_file))
    logger.info("Phase 4 logging test")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file.exists()
    assert "Phase 4 logging test" in log_file.read_text(
        encoding="utf-8"
    )
