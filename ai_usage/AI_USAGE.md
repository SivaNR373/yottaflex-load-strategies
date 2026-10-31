# AI Usage Disclosure

**Author:** Siva (Adaka Sivanagaraju)
**Build start:** Fri 30 Oct 2026

## 1. How AI was used

I used AI assistants as development support during this individual project. AI helped me understand requirements, review designs, draft code and tests, troubleshoot errors, and interpret test and benchmark results.

I remained responsible for choosing the project approach, running the code locally, reviewing the implementation, checking results, and deciding what to include in the repository.

## 2. What I personally did and validated

### Phase 0 - Setup
I created the GitHub repository, virtual environment, project folders, and `.gitignore`, then checked the project structure.

### Phase 1 - Documentation and design
I created the data dictionary, architecture flow, and project assumptions. I used AI to review the documentation and suggest improvements, then checked the changes against the challenge requirements.

### Phase 2 - Data generator
AI helped me structure the Python generator, create reproducible small and large datasets, add invalid records and edge cases, and troubleshoot a CSV field-name error.

I ran the generator locally for both dataset sizes, checked the generated CSV files and expected results, reviewed the Git changes, and committed the completed work.

### Phase 3 - Validation and quarantine
AI helped draft the validation module and pytest cases for required fields, data types, business rules, customer foreign keys, date validation, malformed CSV rows, and duplicate handling.

I created and integrated the files, ran the validation and tests locally, reviewed the reject and duplicate results, and confirmed that the initial validation test suite passed all 17 tests.

### Phase 4 - Run logging and observability
AI helped develop the DuckDB `run_log` table, run tracking functions, Python logging configuration, and related tests.

I integrated the implementation, ran manual verification, reviewed the results, and confirmed that all 22 project tests passed.

### Phase 5 - Loading strategies
AI helped me implement and debug the three loading strategies:

- Full Refresh
- Incremental Merge
- Partition Replacement

I reviewed how each strategy handles target data, processed-file tracking, order updates, history, rejects, and transactions. I ran the loaders and tests locally and checked that the strategies produced equivalent business data in reconciliation tests.

### Phase 6 - Idempotency and failure recovery
AI helped implement simulated loader failures using `--fail-after`, isolated database testing using `--database-path`, and recovery tests. AI-assisted debugging helped correct a syntax issue in partition replacement record selection.

I reviewed and ran the implementation locally, including failure and retry scenarios, and confirmed that the test suite passed.

### Phase 7 - Edge-case testing
AI helped identify and implement additional edge-case tests, including empty input handling, rerun behavior, and equivalence checks across strategies.

I ran the tests locally, reviewed the results, and confirmed that all 34 project tests passed.

### Phase 8 - Reconciliation and benchmarking
AI helped develop the reconciliation and benchmark tools and interpret their results.

I ran reconciliation against isolated databases and checked business row counts, totals, history counts, and hashes. I also ran the small benchmark and the large Full Refresh benchmark.

The large Incremental Merge benchmark did not finish within the available time, and the large Partition Replacement benchmark was not run. I documented these limitations rather than presenting incomplete results as successful benchmarks.

### Phase 9 - Documentation
AI helped draft and improve the README, including setup instructions, loading strategy explanations, recovery commands, reconciliation, benchmark findings, and known limitations.

I reviewed the documentation against the repository and challenge requirements.

### Phase 10 - Final checks
I will run the final test suite, check the Git diff, review the staged changes, and verify that the public repository contains the intended submission files before completing the submission.

## 3. What I reviewed and learned

I reviewed the core loading logic, validation rules, transaction boundaries, processed-file tracking, failure recovery behavior, and tests. I also reviewed the trade-offs between full refresh, incremental merge, and partition replacement.

I am responsible for explaining the implementation, assumptions, limitations, and test results during a project walkthrough.

## 4. Limitations and transparency

AI assistance was used throughout development. I did not treat AI-generated code or explanations as verified merely because they were produced. I ran the project locally and used tests, manual checks, reconciliation, and benchmark results to evaluate the implementation.

The benchmark results have limitations: the large Incremental Merge run was interrupted, and the large Partition Replacement benchmark was not completed. These limitations are documented in the project README.
