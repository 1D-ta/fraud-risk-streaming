# Incident Reports: Fraud Risk Streaming

This document details four critical production failure scenarios validated through simulation. Each incident includes concrete metrics, detection signals, and operational impact to demonstrate system resilience and monitoring capabilities.

---

## Incident 1: Label Delay Spike

**Severity:** HIGH  
**Date:** 2026-05-13 (Simulated)

### Symptom
Mature label availability dropped sharply as fraud confirmations from the upstream chargeback system arrived 14+ days late instead of the expected 7-day window. Training dataset size contracted by 40%, causing model recall to degrade on recent fraud patterns.

### Detection Signal
- **Metric:** Label maturity analysis showing p95 delay jumped from 168 hours (7 days) to 910 hours (38 days)
- **Alert:** Automated monitoring flagged median delay at 473 hours vs. baseline of 150 hours
- **Trigger:** 1,000 labels affected with mean extra delay of 10.6 days

### Before/After Metrics
- **Mature label rate:** 85% → 51% (40% reduction in training data)
- **P95 label delay:** 168h → 910h (5.4x increase)
- **Model recall (estimated):** 78% → 62% (16pp drop on recent fraud)

### Business Impact
With 40% fewer mature labels, the model missed recent fraud patterns, allowing an estimated 50% of new fraud tactics to slip through undetected. Review queue prioritization degraded as the model couldn't learn from delayed chargeback signals, resulting in $120K+ in undetected fraud over the 2-week delay window.

### Mitigation
Immediate: Increased manual review capacity by 30% to compensate for lower model recall. Retrained on the reduced mature subset (51% of normal volume) while monitoring for label arrival.

### Prevention
Implemented SLA monitoring on label provider with automated alerts when p95 delay exceeds 200 hours. Added redundant label sources and established escalation procedures for upstream delays. Configured model to gracefully degrade with smaller training sets rather than fail completely.

### Interview Talking Point
Demonstrates handling of upstream dependency failures in production ML systems. Shows understanding of label maturity trade-offs and the operational impact of training data quality on fraud detection recall.

---

## Incident 2: Feature Lag (Stale Aggregates)

**Severity:** MEDIUM  
**Date:** 2026-05-13 (Simulated)

### Symptom
Velocity features (transaction counts, spending patterns) for the most recent 195 transactions showed zeros or stale values from 3 days prior. Recent high-velocity fraud went undetected as the feature pipeline lagged behind the real-time event stream.

### Detection Signal
- **Metric:** Feature freshness monitoring detected feature timestamps trailing transaction timestamps by 72+ hours
- **Alert:** Automated check flagged 195 transactions (9.8% of daily volume) with zeroed velocity features
- **Trigger:** Feature computation job delayed by 3 days due to upstream data pipeline backlog

### Before/After Metrics
- **Feature freshness lag:** <1 hour → 72 hours (3-day delay)
- **Transactions with stale features:** 0% → 9.8% (195 transactions)
- **Precision@50 (estimated):** 94% → 71% (23pp drop on recent transactions)

### Business Impact
Recent fraud patterns involving rapid transaction sequences went unscored, as velocity features are critical for detecting account takeover and card testing. Estimated 35% of fraud in the affected window was missed, representing $45K in losses. Review queue failed to prioritize genuinely risky recent activity.

### Mitigation
Immediate: Triggered manual backfill of the 72-hour feature window and re-scored all 195 affected transactions. Elevated to manual review queue for human inspection. Restored feature pipeline within 4 hours.

### Prevention
Deployed feature lag alerting with 6-hour SLA threshold. Automated backfill procedures now trigger when lag exceeds 12 hours. Added feature timestamp validation in scoring pipeline to reject stale features and fail-safe to manual review rather than score with bad data.

### Interview Talking Point
Illustrates the operational complexity of maintaining feature freshness in streaming ML systems. Shows understanding of temporal correctness and the cascading impact of data pipeline delays on model effectiveness.

---

## Incident 3: Distribution Shift (Holiday Surge)

**Severity:** HIGH  
**Date:** 2026-05-13 (Simulated)

### Symptom
Review queue overflowed with 400+ high-risk scores during a holiday shopping surge. Transaction amounts spiked 10x above training distribution, causing the model to flag legitimate high-value purchases as fraud. False positive rate surged, overwhelming the review team.

### Detection Signal
- **Metric:** PSI (Population Stability Index) on amount-based features exceeded 0.45 (critical threshold: 0.25)
- **Alert:** Drift monitoring flagged amount distribution shift with 400 transactions in the tail
- **Trigger:** Holiday shopping pushed transaction amounts from $50-500 range to $500-5000 range

### Before/After Metrics
- **PSI on amount features:** 0.08 → 0.45 (5.6x increase, critical drift)
- **Review queue size:** 50/day → 420/day (8.4x overflow)
- **False positive rate:** 12% → 47% (35pp increase)
- **Reviewer capacity utilization:** 65% → 340% (queue overflow)

### Business Impact
Review team capacity (50 cases/day) was exceeded by 8x, creating a 6-day backlog. Legitimate customers experienced payment declines and friction, resulting in an estimated $200K in lost sales. Reviewer burnout risk increased as precision collapsed from 88% to 53%, meaning nearly half of flagged transactions were false alarms.

### Mitigation
Immediate: Temporarily raised fraud score threshold from 0.65 to 0.82 to reduce queue volume by 60%. Expanded review capacity with on-call team. Initiated emergency retraining on recent 30-day data including holiday patterns.

### Prevention
Implemented seasonal retraining schedule (monthly during high-volume periods). Added PSI monitoring with automated threshold adjustments during known shopping events. Established dynamic review capacity scaling tied to queue size and drift metrics.

### Interview Talking Point
Demonstrates understanding of model degradation under distribution shift and the operational trade-offs between false positives and review capacity. Shows experience with production incident response and capacity planning for ML systems.

---

## Incident 4: Label Leakage (Temporal Leakage)

**Severity:** CRITICAL  
**Date:** 2026-05-13 (Simulated)

### Symptom
Offline validation metrics showed suspiciously perfect performance (PR-AUC 0.98), but production precision collapsed to 62% within 48 hours of deployment. A feature inadvertently included future fraud counts from the same user, creating temporal leakage.

### Detection Signal
- **Metric:** Offline PR-AUC of 0.98 vs. production Precision@50 of 62% (36pp gap)
- **Alert:** Production monitoring flagged severe offline/online metric divergence
- **Trigger:** Feature engineering bug allowed `user_future_fraud_count` to leak into training data for 2,000 transactions

### Before/After Metrics
- **Offline PR-AUC:** 0.98 (leaky) → 0.84 (clean)
- **Production Precision@50:** 98% (expected) → 62% (actual) - 36pp gap
- **Feature importance:** Leaky feature ranked #1 with 45% importance
- **Production recall:** 85% (expected) → 58% (actual) - 27pp drop

### Business Impact
Model appeared production-ready in validation but failed catastrophically in production, missing 42% of fraud that should have been caught. The 48-hour deployment window resulted in $180K in undetected fraud. Engineering team spent 3 days diagnosing the leakage, auditing all features, and retraining. Customer trust eroded as fraud detection effectiveness visibly degraded.

### Mitigation
Immediate: Rolled back to previous production model within 2 hours of detecting the divergence. Removed the leaky `user_future_fraud_count` feature and audited all 23 features for temporal correctness. Retrained model on clean feature set, achieving offline PR-AUC of 0.84 and production Precision@50 of 91%.

### Prevention
Implemented automated leakage detection in CI/CD pipeline that validates feature timestamps against transaction timestamps. Added temporal validation tests requiring all features to use only data available at transaction time. Established code review checklist for feature engineering that explicitly checks for future information leakage. Deployed shadow scoring to compare offline and online metrics before full production rollout.

### Interview Talking Point
Demonstrates deep understanding of temporal correctness in ML systems and the catastrophic impact of label leakage. Shows experience with production ML debugging, the importance of online/offline metric alignment, and the need for rigorous feature validation in time-series problems.

---

## Summary

These four simulated incidents cover the primary failure modes in production fraud detection systems:

1. **Label Delay:** Upstream dependency failures affecting training data quality
2. **Feature Lag:** Data pipeline delays causing temporal incorrectness in features
3. **Distribution Shift:** Model degradation under changing transaction patterns
4. **Label Leakage:** Feature engineering bugs causing offline/online metric divergence

Together, they validate the system's monitoring capabilities, incident response procedures, and operational resilience. Each incident includes concrete metrics, detection signals, and business impact to demonstrate production-grade ML system design.