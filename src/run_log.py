
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb


def create_connection(database_path="data/pipeline.duckdb"):
    """Create a connection to the DuckDB database."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(database_path)

    create_run_log_table(connection)

    return connection


def create_run_log_table(connection):
    """Create the run_log table if it does not exist."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            run_id VARCHAR PRIMARY KEY,
            strategy VARCHAR,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            input_count INTEGER DEFAULT 0,
            output_count INTEGER DEFAULT 0,
            rejected_count INTEGER DEFAULT 0,
            status VARCHAR,
            failure_reason VARCHAR
        )
    """)


def configure_logging(log_file="output/pipeline.log"):
    """Configure logging to write to both the console and a file."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ],
        force=True
    )

    return logging.getLogger("pipeline")


def start_run(connection, strategy):
    """Create a new pipeline run and record its start time."""
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    connection.execute(
        """
        INSERT INTO run_log (
            run_id, strategy, start_time, status
        )
        VALUES (?, ?, ?, ?)
        """,
        [run_id, strategy, start_time, "RUNNING"]
    )

    logging.info("Pipeline started: run_id=%s, strategy=%s",
                 run_id, strategy)

    return run_id


def finish_run(
    connection,
    run_id,
    input_count,
    output_count,
    rejected_count,
    failure_reason=None
):
    """Record pipeline results and mark the run as completed or failed."""
    end_time = datetime.now(timezone.utc)

    status = "FAILED" if failure_reason else "SUCCESS"

    connection.execute(
        """
        UPDATE run_log
        SET end_time = ?,
            input_count = ?,
            output_count = ?,
            rejected_count = ?,
            status = ?,
            failure_reason = ?
        WHERE run_id = ?
        """,
        [
            end_time,
            input_count,
            output_count,
            rejected_count,
            status,
            failure_reason,
            run_id
        ]
    )

    logging.info(
        "Pipeline finished: run_id=%s, status=%s, input=%s, output=%s, rejected=%s",
        run_id, status, input_count, output_count, rejected_count
    )

    if failure_reason:
        logging.error("Pipeline failure: %s", failure_reason)
