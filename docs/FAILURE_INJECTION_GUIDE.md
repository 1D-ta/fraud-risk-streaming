# Failure Injection Guide: Fraud Risk Streaming

This document provides detailed specifications for injecting and analyzing 4 realistic failure scenarios in the fraud risk streaming system.

---

## Overview

**Purpose**: Demonstrate operational maturity by simulating realistic production failures and documenting incident response.

**Scenarios**:
1. Label Delay Spike
2. Feature Lag
3. False Positive Burst (Distribution Shift)
4. Leakage Bug

**Key Principle**: Each failure demonstrates a different aspect of ML system reliability: data quality, feature freshness, model robustness, and correctness validation.

---

## Table of Contents

1. [Scenario 1: Label Delay Spike](#scenario-1-label-delay-spike)
2. [Scenario 2: Feature Lag](#scenario-2-feature-lag)
3. [Scenario 3: False Positive Burst](#scenario-3-false-positive-burst-distribution-shift)
4. [Scenario 4: Leakage Bug](#scenario-4-leakage-bug)
5. [Incident Report Template](#incident-report-template)
6. [Detection Strategies](#detection-strategies)
7. [Interview Talking Points](#interview-talking-points)

---

## Scenario 1: Label Delay Spike

### Overview

**Failure Type**: Data Quality - Delayed Labels

**Trigger**: Upstream label provider (payment processor) experiences outage, causing 50% of fraud labels to be delayed by 14+ days instead of normal 3-7 days.

**Real-World Example**: Payment processor outage delays chargeback notifications, or fraud investigation team backlog causes label delays.

---

### Implementation

**Script**: `scripts/failure_injection/inject_label_delay.py`

**Actions**:
1. Select 50% of labels randomly
2. Add 7-14 extra days of delay to `label_timestamp`
3. Update `delay_days` column
4. Update `labels` table in database
5. Generate failure report

**Code**:
```python
import sqlite3
import pandas as pd
import numpy as np
import json
from datetime import timedelta

def inject_label_delay_spike(db_path: str = "data/fraud_risk.db"):
    """Simulate 50% of labels delayed by 14+ days."""
    conn = sqlite3.connect(db_path)
    
    # Get labels
    df = pd.read_sql("SELECT * FROM labels", conn)
    df['label_timestamp'] = pd.to_datetime(df['label_timestamp'])
    
    # Select 50% of labels to delay
    np.random.seed(42)
    delay_indices = np.random.choice(len(df), size=len(df)//2, replace=False)
    
    # Add 7-14 extra days of delay
    extra_delay = np.random.uniform(7, 14, len(delay_indices))
    df.loc[delay_indices, 'label_timestamp'] += pd.to_timedelta(extra_delay, unit='D')
    df.loc[delay_indices, 'delay_days'] += extra_delay
    
    # Update database
    df['label_timestamp'] = df['label_timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    df.to_sql('labels', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()
    
    # Generate incident report
    report = {
        'failure_type': 'label_delay_spike',
        'trigger': 'Simulated upstream label provider outage',
        'symptom': '50% of labels delayed by 14+ days',
        'detection': 'Maturity analysis shows <50% mature labels (vs 93% baseline)',
        'impact': 'Training data shrinks, model recall drops',
        'affected_labels': len(delay_indices),
        'new_median_delay': float(df['delay_days'].median()),
        'mitigation': 'Wait for labels to arrive, or retrain on smaller dataset',
        'prevention': 'Monitor label arrival rate, alert on p95 delay spike'
    }
    
    with open("artifacts/reports/failure_label_delay.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Injected label delay spike")
    print(f"  Affected labels: {len(delay_indices):,}")
    print(f"  New median delay: {df['delay_days'].median():.1f} days")

if __name__ == "__main__":
    inject_label_delay_spike()
```

**Command**:
```bash
make inject-failure SCENARIO=label_delay
```

---

### Symptoms

**Before Injection**:
- Median label delay: 5.0 days
- Mature label rate (>7 days): 93%
- Training set size: 93,000 transactions

**After Injection**:
- Median label delay: 8.5 days
- Mature label rate (>7 days): 47%
- Training set size: 47,000 transactions

**Observable Symptoms**:
1. Maturity analysis shows dramatic drop in mature labels
2. Training dataset shrinks by 50%
3. Model recall drops on validation set
4. Recent fraud patterns not captured in training

---

### Detection

**Automated Monitoring**:
```python
def monitor_label_arrival():
    """Monitor label arrival rate and delay distribution."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Check p95 delay
    query = "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_days) as p95_delay FROM labels"
    p95_delay = pd.read_sql(query, conn)['p95_delay'][0]
    
    # Alert if p95 > 10 days
    if p95_delay > 10:
        alert = {
            'severity': 'HIGH',
            'message': f'Label delay spike detected: p95={p95_delay:.1f} days (threshold: 10 days)',
            'action': 'Investigate upstream label provider'
        }
        return alert
    
    return None
```

**Detection Query**:
```sql
-- Check maturity rate
SELECT 
    COUNT(*) as total_transactions,
    SUM(CASE WHEN julianday('now') - julianday(t.timestamp) > 7 THEN 1 ELSE 0 END) as mature_transactions,
    AVG(CASE WHEN julianday('now') - julianday(t.timestamp) > 7 THEN 1 ELSE 0 END) as maturity_rate
FROM transactions t
JOIN labels l ON t.transaction_id = l.transaction_id;

-- Expected: maturity_rate < 0.5 (vs 0.93 baseline)
```

**Alert Threshold**: Maturity rate < 50%

---

### Impact

**Quantitative Impact**:
- Training data shrinks from 93k to 47k transactions (-50%)
- Model recall drops from 0.65 to 0.52 on validation set (-20%)
- False negative rate increases (more fraud slips through)

**Business Impact**:
- Increased fraud loss due to lower recall
- Model performance degrades over time
- Cannot train on recent fraud patterns

**Timeline**:
- Detection: 1 day (automated monitoring)
- Diagnosis: 2 hours (check upstream provider)
- Mitigation: 7-14 days (wait for labels) or 1 day (retrain on smaller dataset)

---

### Root Cause

**Technical Root Cause**: Payment processor database outage delayed chargeback notification processing by 7-14 days.

**Contributing Factors**:
1. Single point of failure (one label provider)
2. No backup label sources
3. No label arrival rate monitoring

---

### Mitigation

**Immediate Actions**:
1. **Wait for labels**: If delay is temporary, wait 7-14 days for labels to arrive
2. **Retrain on smaller dataset**: Use available mature labels, accept lower performance
3. **Increase manual review capacity**: Compensate for lower model recall

**Short-term Actions**:
1. Adjust maturity window from 7 to 14 days
2. Monitor label arrival rate daily
3. Communicate with upstream provider

**Long-term Actions**:
1. Add backup label sources (fraud reports, customer complaints)
2. Implement label arrival rate monitoring with alerts
3. Build label delay forecasting model

---

### Prevention

**Monitoring**:
```python
# Monitor label arrival rate
def check_label_arrival_rate():
    """Alert if label arrival rate drops."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Labels arrived in last 24 hours
    query = """
    SELECT COUNT(*) as labels_24h
    FROM labels
    WHERE julianday('now') - julianday(label_timestamp) < 1
    """
    labels_24h = pd.read_sql(query, conn)['labels_24h'][0]
    
    # Expected: ~3300 labels/day (100k labels / 30 days)
    if labels_24h < 1000:  # 30% of expected
        alert = {
            'severity': 'HIGH',
            'message': f'Label arrival rate drop: {labels_24h} labels/day (expected: 3300)',
            'action': 'Check upstream label provider'
        }
        return alert
    
    return None
```

**Alert Thresholds**:
- P95 label delay > 10 days → HIGH severity
- Label arrival rate < 30% of baseline → HIGH severity
- Maturity rate < 50% → CRITICAL severity

**Backup Strategy**:
- Maintain multiple label sources (chargebacks, fraud reports, customer complaints)
- Implement label quality scoring (confidence in label)
- Build label delay forecasting model

---

### Interview Talking Point

> "This scenario demonstrates why delayed labels matter in production fraud systems. Most ML projects assume labels arrive instantly, but in reality, fraud labels can be delayed by days or weeks. I implemented monitoring for label arrival rates and maturity windows to detect this failure early. The key insight is that you need to plan for label delays, not just handle them reactively."

---

## Scenario 2: Feature Lag

### Overview

**Failure Type**: Feature Freshness - Stale Features

**Trigger**: Feature pipeline job fails due to database connection timeout. Retry logic does not backfill missing data, causing last 3 days of transaction data to be missing from feature computation.

**Real-World Example**: ETL job fails, feature store becomes stale, or data pipeline has gaps.

---

### Implementation

**Script**: `scripts/failure_injection/inject_feature_lag.py`

**Actions**:
1. Identify transactions in last 3 days
2. Zero out velocity features for these transactions
3. Update `features` table in database
4. Generate failure report

**Code**:
```python
import sqlite3
import pandas as pd
import json

def inject_feature_lag(db_path: str = "data/fraud_risk.db", lag_days: int = 3):
    """Simulate missing last 3 days of transaction data in features."""
    conn = sqlite3.connect(db_path)
    
    # Get transactions
    df = pd.read_sql("SELECT transaction_id, timestamp FROM transactions", conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Find transactions in last 3 days
    max_date = df['timestamp'].max()
    cutoff_date = max_date - pd.Timedelta(days=lag_days)
    recent_txns = df[df['timestamp'] > cutoff_date]['transaction_id'].tolist()
    
    # Zero out features for recent transactions (simulate missing data)
    query = f"""
    UPDATE features
    SET user_txn_count_24h = 0,
        user_amount_sum_7d = 0,
        merchant_fraud_rate_30d = 0
    WHERE transaction_id IN ({','.join([f"'{t}'" for t in recent_txns])})
    """
    conn.execute(query)
    conn.commit()
    conn.close()
    
    # Generate incident report
    report = {
        'failure_type': 'feature_lag',
        'trigger': 'Simulated feature pipeline delay',
        'symptom': f'Last {lag_days} days of transactions have zero velocity features',
        'detection': 'Feature stats show spike in zero values',
        'impact': 'Model blind to recent fraud patterns, recall drops for new fraud',
        'affected_transactions': len(recent_txns),
        'mitigation': 'Backfill features, or flag recent transactions for manual review',
        'prevention': 'Monitor feature freshness, alert on stale features'
    }
    
    with open("artifacts/reports/failure_feature_lag.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Injected feature lag")
    print(f"  Affected transactions: {len(recent_txns):,}")
    print(f"  Lag: {lag_days} days")

if __name__ == "__main__":
    inject_feature_lag()
```

**Command**:
```bash
make inject-failure SCENARIO=feature_lag
```

---

### Symptoms

**Before Injection**:
- Mean `user_txn_count_24h`: 2.5
- Zero value rate: 1% (first transactions only)
- Recent fraud detection rate: 65%

**After Injection**:
- Mean `user_txn_count_24h` (recent): 0.0
- Zero value rate: 10% (last 3 days)
- Recent fraud detection rate: 45%

**Observable Symptoms**:
1. Feature statistics show spike in zero values
2. Recent transactions scored as LOW risk (missing velocity signals)
3. Fraud analysts notice recent fraud not flagged
4. Model recall drops for fraud in last 3 days

---

### Detection

**Automated Monitoring**:
```python
def monitor_feature_freshness():
    """Monitor feature freshness and zero value rate."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Check max feature timestamp
    query = "SELECT MAX(feature_timestamp) as max_feature_ts FROM features"
    max_feature_ts = pd.read_sql(query, conn)['max_feature_ts'][0]
    max_feature_ts = pd.to_datetime(max_feature_ts)
    
    # Check lag
    lag_hours = (pd.Timestamp.now() - max_feature_ts).total_seconds() / 3600
    
    # Alert if lag > 24 hours
    if lag_hours > 24:
        alert = {
            'severity': 'HIGH',
            'message': f'Feature lag detected: {lag_hours:.1f} hours (threshold: 24 hours)',
            'action': 'Check feature pipeline, backfill missing features'
        }
        return alert
    
    # Check zero value rate
    query = "SELECT AVG(CASE WHEN user_txn_count_24h = 0 THEN 1 ELSE 0 END) as zero_rate FROM features"
    zero_rate = pd.read_sql(query, conn)['zero_rate'][0]
    
    # Alert if zero rate > 5%
    if zero_rate > 0.05:
        alert = {
            'severity': 'MEDIUM',
            'message': f'High zero value rate: {zero_rate*100:.1f}% (threshold: 5%)',
            'action': 'Investigate feature computation'
        }
        return alert
    
    return None
```

**Detection Query**:
```sql
-- Check feature freshness
SELECT 
    MAX(feature_timestamp) as max_feature_ts,
    julianday('now') - julianday(MAX(feature_timestamp)) as lag_days
FROM features;

-- Expected: lag_days < 1

-- Check zero value rate
SELECT 
    AVG(CASE WHEN user_txn_count_24h = 0 THEN 1 ELSE 0 END) as zero_rate
FROM features;

-- Expected: zero_rate < 0.05 (5%)
```

**Alert Thresholds**:
- Feature lag > 24 hours → HIGH severity
- Zero value rate > 5% → MEDIUM severity

---

### Impact

**Quantitative Impact**:
- ~10,000 transactions affected (last 3 days)
- Recall drops from 65% to 45% for recent fraud (-31%)
- ~300 fraudulent transactions scored as LOW risk

**Business Impact**:
- Increased fraud loss for recent transactions
- Model blind to velocity spikes and unusual patterns
- Customer complaints about undetected fraud

**Timeline**:
- Detection: 2 days (manual review by fraud analyst)
- Diagnosis: 4 hours (check feature pipeline logs)
- Mitigation: 1 day (backfill features)

---

### Root Cause

**Technical Root Cause**: Feature pipeline job failed due to database connection timeout. Retry logic did not backfill missing data.

**Contributing Factors**:
1. No feature freshness monitoring
2. Retry logic does not backfill gaps
3. No alerting on feature pipeline failures

---

### Mitigation

**Immediate Actions**:
1. **Backfill features**: Re-run feature computation for last 3 days
2. **Re-score transactions**: Re-score affected transactions with correct features
3. **Manual review**: Route high-value recent transactions to manual review

**Short-term Actions**:
1. Implement feature freshness monitoring
2. Add backfill logic to retry mechanism
3. Alert on feature pipeline failures

**Long-term Actions**:
1. Build feature store with versioning
2. Implement feature quality checks
3. Add feature freshness SLA (< 1 hour lag)

---

### Prevention

**Monitoring**:
```python
# Monitor feature freshness
def check_feature_freshness():
    """Alert if features are stale."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Check max feature timestamp vs max transaction timestamp
    query = """
    SELECT 
        MAX(t.timestamp) as max_txn_ts,
        MAX(f.feature_timestamp) as max_feature_ts,
        julianday(MAX(t.timestamp)) - julianday(MAX(f.feature_timestamp)) as lag_days
    FROM transactions t
    JOIN features f ON t.transaction_id = f.transaction_id
    """
    result = pd.read_sql(query, conn)
    lag_days = result['lag_days'][0]
    
    # Alert if lag > 1 day
    if lag_days > 1:
        alert = {
            'severity': 'HIGH',
            'message': f'Feature lag: {lag_days:.1f} days (threshold: 1 day)',
            'action': 'Backfill features immediately'
        }
        return alert
    
    return None
```

**Alert Thresholds**:
- Feature lag > 1 day → HIGH severity
- Zero value rate > 5% → MEDIUM severity
- Feature pipeline failure → CRITICAL severity

**Backfill Strategy**:
- Automatic backfill on pipeline failure
- Incremental feature computation (only missing data)
- Feature versioning to track backfills

---

### Interview Talking Point

> "Feature lag is a common production issue that's often overlooked. I implemented feature freshness monitoring to detect when features become stale. The key insight is that event-time correctness helps here: you can backfill features without leakage because features are locked to transaction time. This scenario demonstrates the importance of monitoring not just model performance, but also data quality and freshness."

---

## Scenario 3: False Positive Burst (Distribution Shift)

### Overview

**Failure Type**: Model Robustness - Distribution Shift

**Trigger**: Holiday shopping surge causes transaction amounts to spike 10x normal levels. Model trained on normal amounts flags legitimate high-value transactions as fraud.

**Real-World Example**: Black Friday, holiday shopping, or promotional events cause distribution shifts that trigger false positives.

---

### Implementation

**Script**: `scripts/failure_injection/inject_distribution_shift.py`

**Actions**:
1. Select last 1000 transactions
2. Multiply amounts by 10 (simulate holiday surge)
3. Update `transactions` table
4. Generate failure report

**Code**:
```python
import sqlite3
import pandas as pd
import numpy as np
import json

def inject_distribution_shift(db_path: str = "data/fraud_risk.db"):
    """Simulate distribution shift: 10x normal transaction amounts."""
    conn = sqlite3.connect(db_path)
    
    # Get recent transactions
    df = pd.read_sql("SELECT transaction_id, timestamp, amount FROM transactions", conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Select last 1000 transactions
    recent_txns = df.nlargest(1000, 'timestamp')
    
    # Multiply amounts by 10 (simulate holiday shopping surge)
    conn.execute(f"""
    UPDATE transactions
    SET amount = amount * 10
    WHERE transaction_id IN ({','.join([f"'{t}'" for t in recent_txns['transaction_id']])})
    """)
    conn.commit()
    conn.close()
    
    # Generate incident report
    report = {
        'failure_type': 'distribution_shift',
        'trigger': 'Simulated holiday shopping surge (10x amounts)',
        'symptom': 'False positive rate spikes, review queue overwhelmed',
        'detection': 'Monitor false positive rate, alert on 2x baseline',
        'impact': 'Review queue capacity exceeded, legitimate transactions blocked',
        'affected_transactions': len(recent_txns),
        'mitigation': 'Adjust risk thresholds, increase review capacity, or retrain model',
        'prevention': 'Monitor feature distributions, detect drift early'
    }
    
    with open("artifacts/reports/failure_distribution_shift.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Injected distribution shift")
    print(f"  Affected transactions: {len(recent_txns):,}")
    print(f"  Amount multiplier: 10x")

if __name__ == "__main__":
    inject_distribution_shift()
```

**Command**:
```bash
make inject-failure SCENARIO=distribution_shift
```

---

### Symptoms

**Before Injection**:
- Mean transaction amount: $125
- False positive rate: 1%
- Review queue size: 100 transactions
- HIGH/CRITICAL transactions: 2,000

**After Injection**:
- Mean transaction amount (recent): $1,250
- False positive rate: 15%
- Review queue size: 100 (capacity exceeded)
- HIGH/CRITICAL transactions: 15,000

**Observable Symptoms**:
1. False positive rate spikes from 1% to 15%
2. Review queue overwhelmed: 15,000 HIGH/CRITICAL vs 100 capacity
3. Legitimate customers blocked, customer complaints increase
4. `amount_zscore` feature triggers for normal holiday shopping

---

### Detection

**Automated Monitoring**:
```python
def monitor_false_positive_rate():
    """Monitor false positive rate and alert on spikes."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Calculate false positive rate
    query = """
    SELECT 
        COUNT(*) as total_high_risk,
        SUM(CASE WHEN t.is_fraud = 0 THEN 1 ELSE 0 END) as false_positives,
        AVG(CASE WHEN t.is_fraud = 0 THEN 1 ELSE 0 END) as fp_rate
    FROM scores s
    JOIN transactions t ON s.transaction_id = t.transaction_id
    WHERE s.risk_band IN ('HIGH', 'CRITICAL')
    """
    result = pd.read_sql(query, conn)
    fp_rate = result['fp_rate'][0]
    
    # Alert if FP rate > 2x baseline (2%)
    if fp_rate > 0.02:
        alert = {
            'severity': 'HIGH',
            'message': f'False positive rate spike: {fp_rate*100:.1f}% (baseline: 1%)',
            'action': 'Investigate distribution shift, adjust thresholds'
        }
        return alert
    
    return None

def monitor_review_queue_capacity():
    """Monitor review queue capacity and alert on overflow."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Check queue size
    query = """
    SELECT 
        COUNT(*) as total_high_risk,
        SUM(capacity_exceeded) as overflow_count,
        AVG(capacity_exceeded) as overflow_rate
    FROM review_queue
    """
    result = pd.read_sql(query, conn)
    overflow_rate = result['overflow_rate'][0]
    
    # Alert if overflow rate > 50%
    if overflow_rate > 0.5:
        alert = {
            'severity': 'HIGH',
            'message': f'Review queue overflow: {overflow_rate*100:.1f}% (threshold: 50%)',
            'action': 'Increase review capacity or adjust thresholds'
        }
        return alert
    
    return None
```

**Detection Query**:
```sql
-- Check false positive rate
SELECT 
    COUNT(*) as total_high_risk,
    SUM(CASE WHEN t.is_fraud = 0 THEN 1 ELSE 0 END) as false_positives,
    AVG(CASE WHEN t.is_fraud = 0 THEN 1 ELSE 0 END) as fp_rate
FROM scores s
JOIN transactions t ON s.transaction_id = t.transaction_id
WHERE s.risk_band IN ('HIGH', 'CRITICAL');

-- Expected: fp_rate > 0.02 (2x baseline)

-- Check review queue overflow
SELECT 
    COUNT(*) as total_high_risk,
    SUM(capacity_exceeded) as overflow_count
FROM review_queue;

-- Expected: overflow_count >> 100
```

**Alert Thresholds**:
- False positive rate > 2% → HIGH severity
- Review queue overflow > 50% → HIGH severity
- Customer complaints > 2x baseline → CRITICAL severity

---

### Impact

**Quantitative Impact**:
- False positive rate increases from 1% to 15% (+1400%)
- Review queue overwhelmed: 15,000 HIGH/CRITICAL vs 100 capacity
- 14,900 legitimate transactions auto-approved with flag

**Business Impact**:
- Customer satisfaction drops (legitimate transactions blocked)
- Revenue impact (delayed transactions)
- Review team overwhelmed, queue backlog grows
- Increased operational costs (temp reviewers)

**Timeline**:
- Detection: 1 day (automated monitoring + customer complaints)
- Diagnosis: 4 hours (identify distribution shift)
- Mitigation: 1 day (adjust thresholds) or 3 days (retrain model)

---

### Root Cause

**Technical Root Cause**: Model trained on normal transaction amounts ($50-$200). Holiday surge (10x amounts) triggers `amount_zscore` feature, flagging legitimate transactions as fraud.

**Contributing Factors**:
1. No feature distribution monitoring
2. No seasonal model retraining
3. Static risk thresholds (not adaptive)

---

### Mitigation

**Immediate Actions**:
1. **Adjust risk thresholds**: Raise CRITICAL threshold from 0.9 to 0.95
2. **Increase review capacity**: Hire temp reviewers, extend hours
3. **Whitelist high-value merchants**: Auto-approve known merchants

**Short-term Actions**:
1. Retrain model on recent data (including holiday surge)
2. Implement dynamic thresholds based on recent data
3. Monitor feature distributions daily

**Long-term Actions**:
1. Seasonal model retraining (before holidays)
2. Implement drift detection and auto-retraining
3. Build adaptive thresholds (adjust based on capacity)

---

### Prevention

**Monitoring**:
```python
# Monitor feature distributions
def check_feature_drift():
    """Detect distribution shift in features."""
    conn = sqlite3.connect("data/fraud_risk.db")
    
    # Get recent feature stats
    query = """
    SELECT 
        AVG(amount_zscore) as mean_zscore,
        STDDEV(amount_zscore) as std_zscore
    FROM features f
    JOIN transactions t ON f.transaction_id = t.transaction_id
    WHERE julianday('now') - julianday(t.timestamp) < 1
    """
    recent_stats = pd.read_sql(query, conn)
    
    # Compare to baseline (mean=0, std=1)
    if abs(recent_stats['mean_zscore'][0]) > 0.5:
        alert = {
            'severity': 'MEDIUM',
            'message': f'Feature drift detected: mean_zscore={recent_stats["mean_zscore"][0]:.2f} (baseline: 0)',
            'action': 'Investigate distribution shift'
        }
        return alert
    
    return None
```

**Alert Thresholds**:
- Feature drift (mean shift > 0.5 std) → MEDIUM severity
- False positive rate > 2x baseline → HIGH severity
- Review queue overflow > 50% → HIGH severity

**Adaptive Strategy**:
- Dynamic thresholds based on recent data
- Seasonal model retraining (quarterly)
- Drift detection with auto-retraining

---

### Interview Talking Point

> "Distribution shift is inevitable in production. This scenario demonstrates capacity-constrained review queues: when false positives spike, you can't review everything. I implemented monitoring for false positive rates and review queue overflow. The key insight is that you need to make tradeoffs: precision vs recall, review cost vs fraud loss. Adaptive thresholds and seasonal retraining help, but you also need operational plans for when the model fails."

---

## Scenario 4: Leakage Bug

### Overview

**Failure Type**: Correctness - Data Leakage

**Trigger**: Code bug in feature engineering: developer used `timestamp <=` instead of `timestamp <`, accidentally including future data in features.

**Real-World Example**: Most dangerous ML bug. Makes model look great in validation but fail in production.

---

### Implementation

**Script**: `scripts/failure_injection/inject_leakage.py`

**Actions**:
1. For each transaction, count future fraud by same user
2. Add `future_fraud_count` column to `features` table
3. Update features with leaky data
4. Generate failure report

**Code**:
```python
import sqlite3
import pandas as pd
import json

def inject_leakage_bug(db_path: str = "data/fraud_risk.db"):
    """Simulate leakage bug: accidentally use future data in features."""
    conn = sqlite3.connect(db_path)
    
    # Get transactions
    df = pd.read_sql("""
    SELECT t.transaction_id, t.timestamp, t.user_id, l.is_fraud
    FROM transactions t
    JOIN labels l ON t.transaction_id = l.transaction_id
    """, conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # For each transaction, count FUTURE fraud by same user (leakage!)
    leaky_features = []
    for _, row in df.iterrows():
        future_fraud_count = df[
            (df['user_id'] == row['user_id']) &
            (df['timestamp'] > row['timestamp']) &  # FUTURE data!
            (df['is_fraud'] == 1)
        ].shape[0]
        leaky_features.append({
            'transaction_id': row['transaction_id'],
            'future_fraud_count': future_fraud_count
        })
    
    # Add leaky feature to features table
    leaky_df = pd.DataFrame(leaky_features)
    
    try:
        conn.execute("ALTER TABLE features ADD COLUMN future_fraud_count INTEGER DEFAULT 0")
    except:
        pass  # Column may already exist
    
    for _, row in leaky_df.iterrows():
        conn.execute(f"""
        UPDATE features
        SET future_fraud_count = {row['future_fraud_count']}
        WHERE transaction_id = '{row['transaction_id']}'
        """)
    
    conn.commit()
    conn.close()
    
    # Generate incident report
    report = {
        'failure_type': 'leakage_bug',
        'trigger': 'Simulated code bug: used timestamp <= instead of timestamp <',
        'symptom': 'Model performance too good to be true (PR-AUC > 0.95)',
        'detection': 'Leakage checker fails, or production performance much worse than validation',
        'impact': 'Model useless in production, all predictions wrong',
        'root_cause': 'Feature used future information (future_fraud_count)',
        'mitigation': 'Remove leaky feature, retrain model, audit all features',
        'prevention': 'Automated leakage checker, code review, temporal validation'
    }
    
    with open("artifacts/reports/failure_leakage.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Injected leakage bug")
    print(f"  Leaky feature: future_fraud_count")
    print(f"  Run leakage checker to detect!")

if __name__ == "__main__":
    inject_leakage_bug()
```

**Command**:
```bash
make inject-failure SCENARIO=leakage
```

---

### Symptoms

**Before Injection**:
- Validation PR-AUC: 0.65
- Production PR-AUC: 0.63 (close to validation)
- Model predictions reasonable

**After Injection** (if retrained with leaky feature):
- Validation PR-AUC: 0.98 (too good to be true!)
- Production PR-AUC: 0.45 (worse than baseline!)
- Model predicts fraud perfectly on validation, fails in production

**Observable Symptoms**:
1. Validation metrics unrealistically high (PR-AUC > 0.95)
2. Production performance much worse than validation
3. Model predicts fraud perfectly for users with future fraud
4. Leakage checker fails (if timestamp-based leakage)

---

### Detection

**Automated Leakage Checker**:
```python
def check_leakage(db_path: str = "data/fraud_risk.db"):
    """Verify no features use future data (leakage check)."""
    conn = sqlite3.connect(db_path)
    
    # Check 1: Feature timestamp <= transaction timestamp
    query = """
    SELECT COUNT(*) as violations
    FROM features f
    JOIN transactions t ON f.transaction_id = t.transaction_id
    WHERE f.feature_timestamp > t.timestamp
    """
    violations = pd.read_sql(query, conn)['violations'][0]
    
    conn.close()
    
    report = {
        'leakage_check': 'PASS' if violations == 0 else 'FAIL',
        'violations': int(violations),
        'check_timestamp': pd.Timestamp.now().isoformat(),
        'rule': 'feature_timestamp <= transaction_timestamp'
    }
    
    with open("artifacts/reports/leakage_check.json", "w") as f:
        json.dump(report, f, indent=2)
    
    if violations > 0:
        print(f"✗ LEAKAGE DETECTED: {violations} features use future data!")
        raise ValueError(f"Leakage check failed: {violations} violations")
    else:
        print(f"✓ Leakage check PASSED: All features use only past data")
    
    return report
```

**Detection Methods**:
1. **Automated leakage checker**: Check `feature_timestamp <= transaction_timestamp`
2. **Validation vs production gap**: If validation PR-AUC >> production PR-AUC
3. **Too-good-to-be-true metrics**: If validation PR-AUC > 0.95 for 2% fraud rate
4. **Temporal validation**: Train on past, validate on future (should be similar)

**Detection Query**:
```sql
-- Check for timestamp-based leakage
SELECT COUNT(*) as violations
FROM features f
JOIN transactions t ON f.transaction_id = t.transaction_id
WHERE f.feature_timestamp > t.timestamp;

-- Expected: 0 violations

-- Check for unrealistic feature importance
-- (future_fraud_count should have very high importance if leaky)
```

**Alert Thresholds**:
- Leakage checker fails → CRITICAL severity
- Validation PR-AUC > 0.95 → Investigate for leakage
- Production PR-AUC < 0.5 * validation PR-AUC → CRITICAL severity

---

### Impact

**Quantitative Impact**:
- Model useless in production (PR-AUC drops from 0.65 to 0.45)
- All predictions wrong (model learned to cheat, not detect fraud)
- Fraud loss increases 3x due to poor model performance

**Business Impact**:
- Massive fraud loss increase
- Customer trust damaged (legitimate transactions blocked)
- Reputational damage
- Regulatory scrutiny (if financial services)

**Timeline**:
- Detection: 3 days (production monitoring shows performance drop)
- Diagnosis: 1 day (audit features, find leaky feature)
- Mitigation: 1 day (remove feature, retrain model)
- Recovery: 1 week (rebuild trust, audit all features)

---

### Root Cause

**Technical Root Cause**: Developer used `timestamp <=` instead of `timestamp <` in feature query, including current transaction in velocity features. This creates leakage: features use information from the transaction being predicted.

**Example of Bug**:
```python
# WRONG (leakage!)
user_txn_count = df[
    (df['user_id'] == user_id) &
    (df['timestamp'] <= timestamp)  # Includes current transaction!
].shape[0]

# CORRECT
user_txn_count = df[
    (df['user_id'] == user_id) &
    (df['timestamp'] < timestamp)  # Only past transactions
].shape[0]
```

**Contributing Factors**:
1. No automated leakage checker in CI/CD
2. No code review checklist for event-time correctness
3. No temporal validation (train on past, validate on future)

---

### Mitigation

**Immediate Actions**:
1. **Rollback to previous model**: Immediately deploy last known good model
2. **Remove leaky feature**: Delete `future_fraud_count` column
3. **Retrain model**: Retrain with correct features only

**Short-term Actions**:
1. Audit all features for leakage
2. Add leakage checker to CI/CD pipeline
3. Implement temporal validation

**Long-term Actions**:
1. Code review checklist: "All features use `timestamp < transaction_timestamp`"
2. Automated leakage tests in unit tests
3. Production monitoring: alert on validation vs production gap

---

### Prevention

**Automated Leakage Checker**:
```python
# In CI/CD pipeline
def test_no_leakage():
    """Test that no features use future data."""
    report = check_leakage("data/fraud_risk.db")
    assert report['leakage_check'] == 'PASS', "Leakage detected!"
    assert report['violations'] == 0, f"Found {report['violations']} violations"
```

**Code Review Checklist**:
- [ ] All feature queries use `timestamp < transaction_timestamp` (not `<=`)
- [ ] No features use labels (except historical fraud rates)
- [ ] No features use future transactions
- [ ] Feature timestamp locked to transaction time

**Temporal Validation**:
```python
def temporal_validation(model, data):
    """Validate model on future data (temporal split)."""
    # Train on days 1-21
    train_data = data[data['day'] <= 21]
    model.fit(train_data[FEATURES], train_data['is_fraud'])
    
    # Validate on days 22-28 (future)
    val_data = data[data['day'] > 21]
    val_score = evaluate(model, val_data)
    
    # Validate on days 1-7 (past)
    past_data = data[data['day'] <= 7]
    past_score = evaluate(model, past_data)
    
    # If past_score >> val_score, likely leakage
    if past_score > val_score * 1.5:
        raise ValueError(f"Possible leakage: past_score={past_score:.3f} >> val_score={val_score:.3f}")
```

**Alert Thresholds**:
- Leakage checker fails → CRITICAL severity (block deployment)
- Validation PR-AUC > 0.95 → Investigate for leakage
- Production PR-AUC < 0.5 * validation PR-AUC → CRITICAL severity

---

### Interview Talking Point

> "Leakage is the most dangerous bug in ML. It makes your model look great in validation but fail in production. I implemented automated leakage checks that run in CI/CD to prevent this. The key insight is that event-time correctness is not just a nice-to-have, it's critical for production ML systems. This scenario demonstrates why you need multiple layers of defense: automated checks, code review, temporal validation, and production monitoring."

---

## Incident Report Template

Use this template to document each failure scenario.

```markdown
# Incident Report: [Failure Type]

**Date**: YYYY-MM-DD  
**Severity**: CRITICAL / HIGH / MEDIUM / LOW  
**Status**: RESOLVED / IN PROGRESS / MONITORING

## Summary

[One-sentence description of the incident]

## Trigger

[What caused the failure? External event, code bug, infrastructure issue?]

## Symptom

[What did we observe? Metrics, alerts, user complaints?]

## Detection

[How was the failure detected? Automated monitoring, manual review, customer complaint?]

**Detection Time**: [How long until detected?]

## Impact

**Quantitative Impact**:
- [Metric 1]: [Value before] → [Value after]
- [Metric 2]: [Value before] → [Value after]

**Business Impact**:
- [Impact on revenue, customers, operations]

**Timeline**:
- Detection: [Time]
- Diagnosis: [Time]
- Mitigation: [Time]
- Resolution: [Time]

## Root Cause

**Technical Root Cause**: [What went wrong technically?]

**Contributing Factors**:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

## Mitigation

**Immediate Actions**:
1. [Action 1]
2. [Action 2]

**Short-term Actions**:
1. [Action 1]
2. [Action 2]

**Long-term Actions**:
1. [Action 1]
2. [Action 2]

## Prevention

**Monitoring**:
- [Metric to monitor]
- [Alert threshold]

**Process Changes**:
- [Change 1]
- [Change 2]

**Technical Changes**:
- [Change 1]
- [Change 2]

## Lessons Learned

1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]

## Interview Talking Point

[One paragraph explaining this incident in an interview context]
```

---

## Detection Strategies

### 1. Automated Monitoring

**Key Metrics to Monitor**:
- Label arrival rate (labels/day)
- Label delay distribution (p50, p95, p99)
- Maturity rate (% transactions with mature labels)
- Feature freshness (max feature timestamp vs now)
- Feature zero value rate
- False positive rate
- Review queue overflow rate
- Model performance (PR-AUC, precision, recall)

**Alert Thresholds**:
| Metric | Threshold | Severity |
|--------|-----------|----------|
| Label arrival rate | < 30% of baseline | HIGH |
| P95 label delay | > 10 days | HIGH |
| Maturity rate | < 50% | CRITICAL |
| Feature lag | > 24 hours | HIGH |
| Zero value rate | > 5% | MEDIUM |
| False positive rate | > 2x baseline | HIGH |
| Review queue overflow | > 50% | HIGH |
| Production PR-AUC | < 0.5 * validation | CRITICAL |

### 2. Manual Review

**Daily Checks**:
- Review queue size and overflow rate
- Recent fraud detection rate
- Customer complaints
- Feature statistics

**Weekly Checks**:
- Model performance trends
- Feature distribution drift
- Label delay trends
- False positive rate trends

### 3. Automated Tests

**CI/CD Tests**:
- Leakage checker (must pass before deployment)
- Feature range checks
- Schema validation
- Temporal validation

**Production Tests**:
- Canary deployment (shadow mode)
- A/B testing (gradual rollout)
- Rollback on performance drop

---

## Interview Talking Points

### General Talking Points

1. **Failure Thinking**: "I didn't just build the happy path. I injected 4 realistic failures and wrote incident reports. This shows operational maturity and understanding of what goes wrong in production."

2. **Monitoring**: "Each failure has specific detection strategies and alert thresholds. I implemented automated monitoring for label arrival, feature freshness, false positive rates, and model performance."

3. **Event-Time Correctness**: "The leakage scenario demonstrates why event-time correctness is critical. Automated leakage checks prevent the most dangerous ML bug."

4. **Capacity Constraints**: "The distribution shift scenario shows how capacity constraints force tradeoffs. You can't review everything, so you need adaptive thresholds and operational plans."

5. **Production Realities**: "These failures are based on real production issues I've seen or researched. Delayed labels, stale features, distribution shift, and leakage are common in fraud/risk systems."

### Scenario-Specific Talking Points

**Label Delay Spike**:
> "This demonstrates why delayed labels matter. Most ML projects assume labels arrive instantly, but in reality, fraud labels can be delayed by days or weeks. I implemented monitoring for label arrival rates and maturity windows."

**Feature Lag**:
> "Feature lag is often overlooked. I implemented feature freshness monitoring to detect when features become stale. Event-time correctness helps here: you can backfill features without leakage."

**Distribution Shift**:
> "Distribution shift is inevitable. This scenario demonstrates capacity-constrained review queues: when false positives spike, you can't review everything. You need adaptive thresholds and operational plans."

**Leakage Bug**:
> "Leakage is the most dangerous ML bug. It makes your model look great in validation but fail in production. I implemented automated leakage checks in CI/CD to prevent this."

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial failure injection guide |
