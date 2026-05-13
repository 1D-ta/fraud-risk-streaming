# Product Requirements Document: Fraud Risk Streaming System

## 1. Executive Summary

Build a production-style fraud detection system that demonstrates mastery of **delayed labels**, **event-time feature engineering**, and **capacity-constrained review queues**. This is a portfolio project designed to showcase ML engineering skills critical for fraud/risk systems, not a production deployment.

**Key Differentiator**: Most ML projects ignore the reality that fraud labels arrive days/weeks after transactions. This system treats delayed labels as a first-class constraint, demonstrating how to build features, train models, and score transactions without leaking future information.

---

## 2. Objective

Build a fraud detection system that:
- Generates realistic transaction streams with delayed fraud labels
- Builds event-time-correct features (no future leakage)
- Trains models only on mature labels
- Scores transactions in real-time with risk bands
- Routes high-risk transactions to a capacity-constrained review queue
- Demonstrates 4 realistic failure modes with incident reports

**Success Criteria**: An interviewer can run `make run-full` and see:
1. Transaction stream with delayed labels
2. Feature engineering with leakage prevention
3. Model training on mature data only
4. Scoring with review queue management
5. Failure injection scenarios with detection

---

## 3. Non-Goals

**Explicitly Out of Scope**:
- ❌ Real payment gateway integration
- ❌ Deep learning models (focus on engineering, not model complexity)
- ❌ Distributed infrastructure (Kafka, Spark, Kubernetes)
- ❌ Real-time streaming (batch simulation is sufficient)
- ❌ Production deployment or monitoring dashboards
- ❌ Multi-model ensembles or AutoML

**Why**: This project demonstrates ML engineering principles, not infrastructure or model sophistication. SQLite + Python scripts prove system design skills without infrastructure drag.

---

## 4. Target Users & Use Cases

### 4.1 Primary Users

| User | Role | Key Needs |
|------|------|-----------|
| **Fraud Ops Analyst** | Reviews flagged transactions | Clear risk scores, reason codes, manageable queue |
| **ML Engineer** | Maintains model pipeline | Event-time correctness, leakage prevention, reproducibility |
| **Risk Manager** | Sets review capacity policy | Precision/recall tradeoffs, cost-benefit analysis |

### 4.2 Use Cases

**UC1: Transaction Scoring**
- System receives transaction (amount, merchant, user history)
- Computes event-time features (velocity, patterns)
- Scores with trained model
- Assigns risk band (LOW, MEDIUM, HIGH, CRITICAL)
- Routes HIGH/CRITICAL to review queue if capacity available

**UC2: Delayed Label Arrival**
- Fraud label arrives 3-7 days after transaction
- System backfills label to transaction record
- Features remain unchanged (event-time locked)
- Next training run includes newly mature labels

**UC3: Model Retraining**
- Filter transactions with mature labels (>7 days old)
- Build features using only data available at transaction time
- Train LogisticRegression and GradientBoosting models
- Evaluate on PR-AUC and precision@k metrics
- Deploy best model to scoring pipeline

**UC4: Review Queue Management**
- Analyst capacity: 100 transactions/day
- System scores 10,000 transactions/day
- Top 100 by risk score go to review queue
- Remaining HIGH/CRITICAL transactions auto-approve with monitoring

**UC5: Failure Detection**
- Label delay spike: Training data shrinks, recall drops
- Feature lag: Missing recent transactions, model blind to new patterns
- False positive burst: Distribution shift, review queue overwhelmed
- Leakage bug: Accidentally use future data, metrics too good to be true

---

## 5. Core Requirements

### 5.1 Transaction Stream Simulation

**REQ-1.1**: Generate synthetic transaction stream
- **Spec**: 100,000 transactions over 30 days
- **Attributes**: transaction_id, user_id, merchant_id, amount, timestamp, category
- **Fraud Rate**: 2% base rate (realistic for payment fraud)
- **Patterns**: Velocity spikes, unusual merchants, large amounts
- **Output**: SQLite table `transactions`

**REQ-1.2**: Simulate delayed fraud labels
- **Spec**: Labels arrive 3-7 days after transaction (uniform random)
- **Mechanism**: Separate label generation process
- **Storage**: `labels` table with label_timestamp
- **Constraint**: label_timestamp > transaction_timestamp + 3 days

### 5.2 Event-Time Feature Engineering

**REQ-2.1**: Build velocity features
- **Features**:
  - `user_txn_count_24h`: Transactions by user in last 24 hours
  - `user_amount_sum_7d`: Total amount by user in last 7 days
  - `merchant_fraud_rate_30d`: Fraud rate for merchant in last 30 days
  - `amount_zscore`: Z-score of amount vs user history
- **Hard Constraint**: All features use `WHERE feature_timestamp < transaction_timestamp`
- **Output**: `features` table with feature_timestamp

**REQ-2.2**: Leakage prevention checker
- **Spec**: Automated test that verifies no feature uses future data
- **Method**: For each feature, assert `feature_timestamp <= transaction_timestamp`
- **Failure Mode**: Raise exception if leakage detected
- **Output**: Leakage report in `artifacts/reports/leakage_check.json`

### 5.3 Model Training & Evaluation

**REQ-3.1**: Mature label filtering
- **Spec**: Only train on transactions with labels >7 days old
- **SQL**: `WHERE transaction_timestamp < CURRENT_DATE - 7`
- **Rationale**: Ensures all labels have had time to arrive
- **Metric**: Report % of transactions used for training

**REQ-3.2**: Model training
- **Models**: LogisticRegression (baseline), GradientBoostingClassifier (production)
- **Features**: All event-time features from REQ-2.1
- **Target**: Binary fraud label
- **Validation**: Temporal split (train on days 1-21, validate on days 22-28)
- **Output**: Serialized models in `artifacts/models/`

**REQ-3.3**: Evaluation metrics
- **Primary**: PR-AUC (precision-recall area under curve)
- **Secondary**: Precision@100 (precision of top 100 scored transactions)
- **Rationale**: Imbalanced classes (2% fraud), care about top-ranked predictions
- **Output**: `artifacts/reports/evaluation.json`

### 5.4 Scoring & Review Queue

**REQ-4.1**: Real-time scoring
- **Input**: New transaction with features
- **Process**: Load trained model, compute risk score (0-1)
- **Output**: Risk band assignment
  - CRITICAL: score >= 0.9
  - HIGH: 0.7 <= score < 0.9
  - MEDIUM: 0.3 <= score < 0.7
  - LOW: score < 0.3

**REQ-4.2**: Reason codes
- **Spec**: Top 3 features contributing to score
- **Method**: SHAP values or feature coefficients
- **Output**: JSON with feature names and contributions
- **Example**: `{"user_txn_count_24h": 0.35, "amount_zscore": 0.28, "merchant_fraud_rate_30d": 0.15}`

**REQ-4.3**: Capacity-constrained review queue
- **Policy**: Max 100 transactions/day to review queue
- **Selection**: Top 100 by risk score
- **Overflow**: HIGH/CRITICAL transactions beyond capacity auto-approve with flag
- **Storage**: `review_queue` table with queue_timestamp, capacity_exceeded flag
- **Output**: Daily queue report with precision estimate

### 5.5 Failure Injection & Incident Reports

**REQ-5.1**: Implement 4 failure scenarios
1. **Label Delay Spike**: Simulate 50% of labels delayed by 14+ days
2. **Feature Lag**: Simulate missing last 3 days of transaction data
3. **False Positive Burst**: Inject distribution shift (10x normal amounts)
4. **Leakage Bug**: Accidentally include future data in features

**REQ-5.2**: Incident report template
- **Sections**: Trigger, Symptom, Detection, Impact, Root Cause, Mitigation, Prevention
- **Output**: `INCIDENTS.md` with all 4 scenarios documented
- **Format**: Markdown with code snippets and metrics

---

## 6. Success Metrics

### 6.1 System Correctness

| Metric | Target | Measurement |
|--------|--------|-------------|
| **No Leakage** | 100% features pass leakage check | Automated test in `make test` |
| **Mature Labels Only** | 100% training data >7 days old | SQL query validation |
| **Event-Time Features** | All features use `timestamp < T` | Code review + test |

### 6.2 Model Performance

| Metric | Target | Rationale |
|--------|--------|-----------|
| **PR-AUC** | >0.60 | Baseline for 2% fraud rate |
| **Precision@100** | >0.15 | 15+ frauds in top 100 (vs 2 random) |
| **Recall@100** | >0.08 | Catch 8% of fraud with 1% review rate |

### 6.3 Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Review Queue Fill Rate** | 100 transactions/day | Count in `review_queue` table |
| **Capacity Exceeded Rate** | <5% of HIGH/CRITICAL | Flag in `review_queue` |
| **Label Maturity Lag** | Median 5 days | Histogram in reports |

### 6.4 Interview Readiness

| Metric | Target | Validation |
|--------|--------|-------------|
| **End-to-End Run** | <5 minutes | `make run-full` completes |
| **Failure Injection** | All 4 scenarios documented | `INCIDENTS.md` complete |
| **Code Quality** | Type hints, docstrings, tests | `make test` passes |

---

## 7. Technical Constraints

### 7.1 Technology Stack

- **Language**: Python 3.9+
- **Database**: SQLite (single file, no server)
- **ML Libraries**: scikit-learn, pandas, numpy
- **Testing**: pytest
- **Orchestration**: Makefile (no Airflow/Prefect)

**Rationale**: Minimize dependencies, maximize portability. Any interviewer can run this on their laptop.

### 7.2 Performance Requirements

- **Transaction Generation**: 100k transactions in <30 seconds
- **Feature Building**: All features in <2 minutes
- **Model Training**: Both models in <1 minute
- **Scoring**: 10k transactions in <10 seconds

**Rationale**: Fast feedback loop for development and demos.

### 7.3 Data Constraints

- **Storage**: <100 MB total (SQLite + artifacts)
- **Memory**: <2 GB RAM usage
- **Disk I/O**: Sequential reads/writes only

**Rationale**: Laptop-friendly, no cloud resources required.

---

## 8. Risks & Mitigations

### 8.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Synthetic data too simple** | Medium | High | Use realistic fraud patterns (velocity, merchant risk) |
| **Accidental leakage** | High | Critical | Automated leakage checker, code review |
| **Poor model performance** | Low | Medium | Tune features, use GBM, accept baseline metrics |
| **Slow execution** | Low | Low | Profile code, optimize SQL queries |

### 8.2 Project Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Scope creep** | High | Medium | Strict non-goals, time-box to 7 days |
| **Over-engineering** | Medium | Medium | Use SQLite, avoid distributed systems |
| **Under-documentation** | Medium | High | Write docs first, code second |
| **Unclear value prop** | Low | High | Focus on delayed labels + event-time features |

### 8.3 Interview Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Interviewer unfamiliar with fraud** | Medium | Medium | Clear README, explain delayed labels |
| **Technical issues during demo** | Low | High | Pre-record demo video, test on clean machine |
| **Questions on production deployment** | High | Low | Acknowledge non-goals, focus on principles |

---

## 9. Open Questions

### 9.1 Resolved

- ✅ **Q**: Use real payment data or synthetic?  
  **A**: Synthetic. Real data has privacy/legal issues, synthetic proves engineering skills.

- ✅ **Q**: How to simulate label delays realistically?  
  **A**: Uniform random 3-7 days. Simple but demonstrates the constraint.

- ✅ **Q**: What fraud patterns to include?  
  **A**: Velocity spikes, unusual merchants, large amounts. Enough for features, not too complex.

### 9.2 Open

- ❓ **Q**: Should we include a "label quality" dimension (noisy labels)?  
  **Lean**: No. Adds complexity without demonstrating core skills. Focus on delayed labels.

- ❓ **Q**: Should we simulate concept drift over time?  
  **Lean**: No. Failure injection covers distribution shift. Concept drift is a separate topic.

- ❓ **Q**: Should we include a cost-benefit analysis for review queue?  
  **Lean**: Yes, but simple. Document assumed costs (review=$10, fraud=$100) in README.

---

## 10. Appendix

### 10.1 Glossary

- **Event-Time**: The timestamp when an event occurred (transaction time), not when it was processed
- **Mature Label**: A fraud label that has had sufficient time to arrive (>7 days old)
- **Leakage**: Using future information (data not available at prediction time) in features
- **PR-AUC**: Precision-Recall Area Under Curve, better than ROC-AUC for imbalanced classes
- **Review Queue**: Set of transactions flagged for manual review by fraud analysts
- **Capacity Constraint**: Limit on how many transactions can be reviewed per day

### 10.2 References

- [Delayed Feedback in ML](https://arxiv.org/abs/1907.06558)
- [Feature Engineering for Fraud Detection](https://fraud-detection-handbook.github.io/fraud-detection-handbook/)
- [Event-Time vs Processing-Time](https://www.oreilly.com/radar/the-world-beyond-batch-streaming-101/)

### 10.3 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial PRD |
