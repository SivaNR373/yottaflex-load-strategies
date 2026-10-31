# Prompt History

This file records the prompts and requests I used while working on the YottaFlex AI Data Forward Deployed Engineer challenge.

I first used **Claude AI** to help understand the challenge and create a phased roadmap in Notion. I then followed that roadmap and worked through the implementation with **ChatGPT**.

The prompts below are a **reconstructed summary of my requests from the project workflow**, not a word-for-word export of every conversation. AI responses are not included.

## Initial planning - Claude AI

- "I received this YottaFlex AI data engineering challenge. Can you help me understand what they are expecting me to build?"
- "I am still learning data engineering. Can you break this challenge into small phases so I can complete it within the 72-hour deadline?"
- "Can you create a Notion roadmap for the project with each phase, tasks, and what I should complete before moving to the next phase?"
- "I want to use Python and SQL. What would be a simple local setup for this project?"
- "Can you explain the loading strategies in the challenge in simple terms and what I need to demonstrate for each one?"
- "Can you help me organize the project so I can track my progress phase by phase?"

## Phase 0 - Project setup

- "Let's start the YottaFlex project. Help me create the GitHub repository and set up the folders."
- "How do I create and activate a Python virtual environment in Windows?"
- "What should I put in my `.gitignore` for this project?"
- "Can you help me check whether my project structure is correct?"

## Phase 1 - Understanding the problem and documentation

- "Let's start Phase 1 from our roadmap."
- "Help me understand the data we need and the rules the challenge expects us to follow."
- "Can you help me create a data dictionary for the customers and orders data?"
- "Can you help me document the assumptions I am making for this project?"
- "How should I show the flow from CSV files to validation, loading, and reconciliation?"
- "Please review my documentation and tell me if anything important is missing."

## Phase 2 - Data generator

- "Let's continue with Phase 2. I want to generate sample customer and order data for testing."
- "Can you help me write a Python generator that creates customers.csv and daily order CSV files?"
- "I need both a small dataset and a large dataset so I can test the loading strategies."
- "Can we make the generated data repeatable using a fixed seed?"
- "Please include some bad records and edge cases so I can test validation properly."
- "Can you help me fix this error in the generator?"
- "Help me check whether the generated files and expected results look correct."
- "Can you help me check what should be committed to Git?"

## Phase 3 - Validation and quarantine

- "Let's move to Phase 3. Help me validate the incoming order data before loading it."
- "Can you check the CSV columns and existing project files before we start?"
- "I want to reject bad records and keep a reason for why each record was rejected."
- "Can you help me check required fields, invalid amounts, dates, customer IDs, and order statuses?"
- "How should we handle duplicate orders and order updates?"
- "Can you help me write tests for the validation rules?"
- "I accidentally entered Python code in PowerShell. Help me recover and continue."
- "Can you help me understand the valid records, rejected records, and duplicate results?"
- "Please check whether the validation results match what we expected."

## Phase 4 - Run logging and observability

- "Let's continue with Phase 4. I want to track every pipeline run."
- "Can you help me create a run_log table in DuckDB?"
- "I want to record the run ID, loading strategy, start and end time, status, input count, output count, and errors."
- "Can you help me add logging so I can see what the pipeline is doing?"
- "Please help me test successful runs and failed runs."
- "Can you help me check whether all the tests are passing?"

## Phase 5 - The three loading strategies

- "Let's start Phase 5. I need to implement the three loading strategies from the challenge."
- "Can you help me build the Full Refresh loader first?"
- "Now help me implement Incremental Merge. I want existing orders to update only when the incoming update is newer."
- "Can you help me implement Partition Replacement?"
- "Please explain how each strategy should handle processed files, rejects, and order history."
- "Can you help me make the loading steps safe using transactions?"
- "Please review the loaders and help me test them."
- "How can I check that all three strategies produce the same business data?"

## Phase 6 - Idempotency and failure recovery

- "Let's move to Phase 6. I need to prove that rerunning the pipeline does not create duplicate data."
- "Can you help me add a way to simulate a failure after processing a certain number of files?"
- "I want to use a separate database when testing failures so I don't damage my main data."
- "Can you help me test what happens when a loader fails halfway through?"
- "How should I rerun the pipeline after a failure?"
- "Can you help me write tests for failure and recovery?"
- "I got an error in the Partition Replacement code. Can you help me find and fix it?"
- "Please help me verify that the recovery tests work for all three strategies."

## Phase 7 - Edge cases and final test coverage

- "Let's continue with Phase 7. What important edge cases should I test before finishing?"
- "Can you help me test what happens when there are no input files or an empty file?"
- "I want to check that rerunning a strategy is safe."
- "Can you help me compare the business data produced by all three strategies?"
- "Please help me add tests for these cases without making the code unnecessarily complicated."
- "Can you help me run the complete test suite and understand any failures?"
- "Please help me verify the final test count."

## Phase 8 - Reconciliation and benchmarking

- "Let's start Phase 8. I need to compare the results from the three loading strategies."
- "Can you help me build a reconciliation script that checks whether the business data matches?"
- "I want to compare row counts, totals, order history, and data hashes."
- "Can you help me create a benchmark script for the small and large datasets?"
- "Please help me measure the runtime and record the results."
- "The large Incremental Merge benchmark is taking too long. Help me understand what happened and how to report it honestly."
- "Can you help me check the reconciliation results and explain any differences?"
- "Please help me document which benchmarks completed and which ones did not."

## Phase 9 - README and documentation

- "Let's move to Phase 9. Help me finish the README so another person can run this project."
- "Can you include the setup steps, commands, loading strategies, and recovery instructions?"
- "Please explain the trade-offs between Full Refresh, Incremental Merge, and Partition Replacement in simple terms."
- "Can you help me document the benchmark results and limitations?"
- "Please review the README against the actual project files and commands."
- "Can you help me complete the AI usage disclosure and prompt history?"
- "Please check for unfinished sections and formatting issues."

## Phase 10 - Final checks and submission preparation

- "Let's finish the final phase. Help me check that the documentation and project files are ready."
- "Can you help me check the AI disclosure files?"
- "Please help me find unfinished placeholders in the prompt history."
- "Can you help me clean up whitespace issues in the documentation?"
- "Help me run the final tests and review the Git changes before committing."
- "Please guide me through checking that the repository is up to date before I submit it."

## AI tools used

- **Claude AI:** Used during initial challenge understanding and Notion roadmap planning.
- **ChatGPT:** Used while following the roadmap for implementation guidance, explanations, debugging, test development, result interpretation, and documentation.

## Candidate responsibility

I reviewed the suggested implementation, ran the project locally, checked test and reconciliation results, and documented incomplete benchmarks and limitations. I am responsible for understanding and explaining the final code and design decisions.