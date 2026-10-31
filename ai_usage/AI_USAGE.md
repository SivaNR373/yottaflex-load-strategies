# AI Usage Disclosure

**Author:** Siva (Adaka Sivanagaraju)
**Build start:** Fri 30 Oct 2026

## 4. What I did, changed and validated myself
(updated after each phase)

- **Phase 0:** I created the repo, virtual environment, folders and
  .gitignore myself, and checked the structure with `dir`.

- **Phase 1:** Used AI to review the data model and architecture documentation. I checked the suggestions against the challenge requirements and reviewed the final changes.


## Phase 2 – Data Generator

AI assistance was used to help design and implement the Python data generator.

AI helped with:
- Structuring the generator.
- Creating reproducible small and large datasets.
- Adding invalid records and edge cases.
- Debugging a CSV field-name error.
- Reviewing generated files and Git staging.

My involvement:
- Created and ran the generator locally.
- Fixed the reported error.
- Executed both small and large dataset generation.
- Checked the generated CSV files and expected results.
- Reviewed Git changes and committed the completed work.

## Phase 3 – Validation and Quarantine

AI assistance was used to draft the initial validation module.

AI helped with:
- Required-field validation.
- Data type and business-rule checks.
- Customer foreign-key validation.
- Duplicate handling.
- Reject logging with source filename and row number.

My involvement:
- Created the Python file.
- Ran the validation module locally.
- Reviewed the generated reject and duplicate logs.
- Will verify and test the implementation before considering this phase complete.

All AI-generated code will be reviewed, understood, tested, and corrected by me before submission.


### Phase 3 – Validation Testing

AI assistance:
- Helped create pytest test cases for the validation module.
- Suggested parameterized tests for required fields and invalid amounts.
- Helped test malformed CSV handling and duplicate selection.
- Assisted with interpreting pytest results and verifying the complete test suite.

Candidate contribution:
- Created the test file and integrated the tests into the project.
- Executed the tests locally.
- Reviewed the test results and confirmed all 17 tests passed.
- Verified expected and actual rejected records matched.

All AI-assisted code was reviewed and tested by the candidate.

### Phase 4 — Run Logging and Observability

AI assistance was used to develop the DuckDB run_log table,
Python logging configuration, pipeline execution tracking
functions, and automated tests.

I created and integrated the implementation, executed the
manual verification commands, reviewed the results, and
confirmed that all 22 project tests passed.

## Phase 6 — Recovery and Failure Testing

AI assistance was used to support implementation and debugging of failure simulation, isolated database testing, and recovery tests for the three loading strategies.

All generated or suggested code was reviewed and executed locally. The final test suite and manual failure/retry scenarios were run by the project author.