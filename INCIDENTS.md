# Incident Reports: Fraud Risk Streaming

These incidents are simulated through the failure-injection scripts. They document failure modes the code can actually reproduce.

## Incident 1: Label Delay Spike (Simulated)

**Severity:** HIGH  
**Date:** 2026-05-13

### Symptom
Roughly half of the labels moved beyond the 7-day maturity window, and the mature-label set shrank enough to weaken recency coverage in training.

### Detection
The label maturity report used in the injection path showed the delay distribution shifting into the multi-week range and the mature-label rate dropping.

### Impact
`training/evaluate_model.py` filtered out more recent rows, so the model trained on a smaller and older sample. That reduces how quickly new fraud patterns can be learned.

### Mitigation
Wait for the delayed labels to arrive, or retrain on the mature subset once the backlog clears.

### Prevention
Track mature-label coverage and p95 label delay before each training run.

## Incident 2: Feature Lag (Simulated)

**Severity:** MEDIUM  
**Date:** 2026-05-13

### Symptom
Newest transactions have zeroed velocity features because the feature pipeline lagged behind the event stream.

### Detection
Feature freshness monitoring shows old feature timestamps. Affected transactions lack recent aggregates.

### Impact
Recent fraud is under-scored because velocity-based signals are stale. Model recall drops on newest transactions.

### Mitigation
Backfill the missing feature window and re-score affected transactions.

### Prevention
Implement automated lag detection and backfill triggers. Monitor feature freshness continuously.

## Incident 3: Distribution Shift (Simulated)

**Severity:** HIGH  
**Date:** 2026-05-13

### Symptom
Recent transaction amounts moved about 10x above the baseline distribution, which pushed more transactions into the high-risk tail.

### Detection
`monitoring/drift_detection.py` reports PSI on feature columns and scores, so the amount-sensitive features showed a clear drift spike.

### Impact
`review.build_queue.py` filled the 500-case manual review cap more quickly and overflowed the lower-scored tail. That increases false positives in the queue.

### Mitigation
Temporarily raise the threshold, review the shifted window manually, and retrain on more recent data.

### Prevention
Keep PSI monitoring in the pipeline and retrain on recent seasonal data before expected volume changes.

## Incident 4: Label Leakage (Simulated)

**Severity:** CRITICAL  
**Date:** 2026-05-13

### Symptom
Some feature timestamps were later than the transaction timestamps, which can make offline validation look better than the model can perform live.

### Detection
`features/check_leakage.py` fails when it finds any row where `feature_timestamp > transaction_timestamp`.

### Impact
The affected dataset is invalid for training and scoring. Any model trained on it would overstate offline quality and underperform in production.

### Mitigation
Regenerate the features, rerun the leakage check, and retrain before release.

### Prevention
Keep the leakage check in the pipeline and fail the build on timestamp violations.