# Fraud Risk Streaming: Engineering Design

## Problem Statement

Fraud detection here is constrained by three things the code actually models: labels arrive after transactions, features must be computed at event time, and manual review has a hard capacity limit. The system is built to maximize precision in the highest-risk slice rather than chase unconstrained classification scores.

## Architecture Overview

`simulation/` creates synthetic transactions and delayed labels. `features/` builds event-time-safe aggregates in SQLite. `training/` splits data temporally, filters by label maturity, and selects a production model. `scoring/` scores transactions and writes ranked decisions. `review/` caps the manual queue at `REVIEW_CAPACITY`. `monitoring/` writes drift and performance reports.

The pipeline is intentionally simple: one SQLite database, scikit-learn models, and JSON reports in `artifacts/reports/`. That keeps the temporal semantics explicit and easy to audit.

## Key Design Decisions

- SQLite is the persistence layer because the project needs ACID writes, event-time queries, and a portable local setup.
- The maturity window is 7 days, matching `MATURE_LABEL_AGE_DAYS`.
- The review queue is capacity constrained at 500 cases per batch, and the top-k reporting slice is 100.
- Evaluation reports PR-AUC, ROC-AUC, F1, precision@100, and recall@100; ROC-AUC can look strong on synthetic data and should not be treated as a production benchmark.
- Leakage prevention is enforced by checking that feature timestamps do not exceed transaction timestamps.

## Failure Modes

- Label delay spike: the mature-label set shrinks, which reduces training coverage for recent fraud patterns.
- Feature lag: a simulated failure-injection path can stale out recent velocity features; there is no standalone freshness alert in the current code.
- Distribution shift: PSI spikes in `monitoring/drift_detection.py`, and the review queue can fill to its 500-case cap faster than expected.
- Temporal leakage: `features/check_leakage.py` fails if any feature timestamp is later than its transaction timestamp.

This guide intentionally stops at the implemented monitoring path: drift and performance JSON reports plus the local dashboard artifact. It does not assume external observability services.
