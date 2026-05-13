# Incident Reports: Fraud Risk Streaming

This file summarizes the four failure scenarios used to validate the system's operational maturity.

## Incident 1: Label Delay Spike

Severity: HIGH

Trigger: An upstream label source delays a large share of fraud confirmations by 14+ days.

Symptoms: Mature label rate drops, the training set shrinks, and recall falls because recent fraud is missing from the training window.

Detection: Label delay monitoring and maturity analysis show the p95 delay and mature-label rate moving outside the expected range.

Mitigation: Wait for labels to arrive or retrain on the smaller mature subset while increasing manual review capacity.

Prevention: Monitor label arrival rate, p95 delay, and dependency health for the label provider.

## Incident 2: Feature Lag

Severity: MEDIUM

Trigger: A feature job lags behind the event stream and leaves recent transactions with stale or zeroed features.

Symptoms: Velocity features flatten to zero, recent transactions receive low scores, and fraud in the newest slice is under-detected.

Detection: Feature freshness checks show that feature timestamps trail transaction timestamps by days.

Mitigation: Backfill the missing feature window and re-score the affected transactions.

Prevention: Alert on feature lag, automate retries, and keep backfill logic in the pipeline.

## Incident 3: False Positive Burst

Severity: HIGH

Trigger: A seasonal or holiday-driven distribution shift pushes amounts far above the model's training distribution.

Symptoms: High scores flood the review queue, false positives spike, and reviewers get overwhelmed.

Detection: PSI and queue-size monitoring show the amount-sensitive features drifting hard.

Mitigation: Temporarily raise thresholds, expand review capacity, and retrain on recent data.

Prevention: Monitor feature distributions, retrain seasonally, and review capacity assumptions ahead of spikes.

## Incident 4: Leakage Bug

Severity: CRITICAL

Trigger: A feature accidentally captures future fraud information from the same user.

Symptoms: Offline validation looks unrealistically strong, but production performance collapses.

Detection: Leakage checks and production monitoring disagree sharply on model quality.

Mitigation: Remove the leaky feature, retrain the model, and audit all temporal joins.

Prevention: Enforce event-time correctness, automate leakage checks in CI, and review every feature against the transaction timestamp.

## Summary

The scenarios above cover the main production failure modes for fraud systems: delayed labels, stale features, distribution shift, and leakage. Together they show whether the pipeline can survive the kinds of issues that appear in real streaming systems.