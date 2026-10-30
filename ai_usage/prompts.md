# Prompt History

Prompts I sent to AI tools while building this project. Responses left out (optional per the brief).

## Tech stack choice
Python + DuckDB + pytest. I'm strong in Python and SQL, and DuckDB runs locally with no setup.

## Phase 0: Setup
**My work:** I created the GitHub repo, virtual environment, folders and .gitignore myself, and checked the structure.

## Phase 1: Docs
**My work:** Created the data dictionary, architecture flow and project assumptions. Used AI to review the documentation and suggest improvements.

**Claude prompts:**
- "phase 1"
- "1.2" (I sent a screenshot because Notepad asked to create architecture.md)
- "once again step 1.5 how to addd em"


## Phase 2 – Data Generator

- Asked AI to resume the YottaFlex challenge from the previous progress.
- Asked AI to continue Phase 2 while keeping implementation aligned with the problem statement and avoiding unnecessary complexity.
- Asked AI for help creating and implementing the Python data generator.
- Asked AI to debug the generator after a field-name error occurred.
- Asked AI to verify small and large dataset generation.
- Asked AI to verify Git tracking and prepare the Phase 2 commit.

## Phase 3 – Validation and Quarantine

- Asked AI to continue from Phase 2 and begin Phase 3.
- Asked AI to inspect the existing project structure, dependencies, and sample CSV columns before implementation.
- Asked AI to create a simple validation module based on the challenge requirements.
- Asked AI for help recovering after accidentally entering Python code into PowerShell.
- Asked AI to interpret validation results and explain the valid, rejected, and duplicate record counts.
- Asked AI to verify the reject records and duplicate log.
- Asked AI to ensure prompt history and AI usage documentation are maintained throughout the challenge.


### Phase 3 – Validation Testing

- Asked AI to create pytest tests for the data validation module.
- Asked AI to cover required fields, data types, business rules, customer foreign keys and date validation.
- Asked AI to test malformed CSV rows and duplicate handling.
- Asked AI to help troubleshoot and verify test execution.
- Asked AI to verify the complete pytest suite.


## Phase 4 — Run Log and Logging

- Implemented DuckDB database connection and run_log table.
- Added unique run IDs and pipeline execution tracking.
- Implemented start_run() and finish_run() functions.
- Recorded execution timestamps, strategy, input count,
  output count, rejected count, status, and failure reason.
- Configured Python logging to write to the console and log file.
- Added pytest tests for table creation, successful runs,
  failed runs, RUNNING status, and file logging.
- Verified all 22 project tests pass.

## Phase 5: The 3 loaders
(add when done)

## Phase 6: Idempotency and failure recovery
(add when done)

## Phase 7: Tests
(add when done)

## Phase 8: Reconcile and benchmark
(add when done)

## Phase 9: Docs and trade-offs
(add when done)

## Phase 10: Final checks
(add when done)