# Fraud Risk Streaming - Project Guide

**One-Line Description:** A real-time fraud detection system that handles delayed labels, ensures event-time correctness, and optimizes review capacity through intelligent scoring and prioritization.

---

## 🎯 Table of Contents

1. [Project Overview](#project-overview)
2. [Why This Project Exists](#why-this-project-exists)
3. [Key Technical Challenges](#key-technical-challenges)
4. [System Architecture](#system-architecture)
5. [Design Principles](#design-principles)
6. [Technology Stack](#technology-stack)
7. [7-Day MVP Plan](#7-day-mvp-plan)
8. [Current Status](#current-status)
9. [Next Steps](#next-steps)
10. [Documentation Structure](#documentation-structure)
11. [Interview Talking Points](#interview-talking-points)
12. [How to Use This Guide](#how-to-use-this-guide)

---

## 🎯 Project Overview

**Fraud Risk Streaming** is a production-grade fraud detection system designed to solve real-world challenges in financial transaction monitoring. Unlike typical ML projects, this system addresses three critical problems that make fraud detection uniquely difficult:

1. **Delayed Labels** - Fraud labels arrive hours or days after transactions
2. **Event-Time Correctness** - Features must reflect what was known at transaction time
3. **Review Capacity Constraints** - Human reviewers can only check a limited number of transactions

This project demonstrates advanced ML engineering skills including streaming data processing, temporal correctness, model monitoring, and production-ready architecture.

---

## 🔍 Why This Project Exists

### The Fraud Detection Problem

In real-world fraud detection:

- **Transactions happen in real-time** - Decisions needed in milliseconds
- **Labels arrive late** - Fraud confirmation takes hours/days (chargebacks, investigations)
- **Features must be temporally correct** - Can't use future information
- **Review capacity is limited** - Only top N% of transactions can be manually reviewed
- **Models degrade over time** - Fraud patterns evolve, requiring monitoring

### What Makes This Interview-Worthy

This project showcases:

1. **Streaming Architecture** - Real-time processing with event-time semantics
2. **Temporal Correctness** - Preventing data leakage in time-series ML
3. **Production ML** - Model versioning, monitoring, rollback capabilities
4. **System Design** - Database schema design for streaming workloads
5. **Business Impact** - Optimizing review capacity while maximizing fraud detection

**This is not a Kaggle competition.** It's a production system that solves real engineering challenges.

---

## 🚧 Key Technical Challenges

### Challenge 1: Delayed Labels

**Problem:** Fraud labels arrive hours or days after transactions occur.

**Solution:**
- Store transactions with `event_time` (when transaction occurred)
- Store labels with `label_time` (when fraud was confirmed)
- Training pipeline joins on `transaction_id` with temporal awareness
- Features computed using only data available at `event_time`

### Challenge 2: Event-Time Feature Safety

**Problem:** Features must reflect what was known at transaction time, not when the model trains.

**Example of Data Leakage:**
```python
# WRONG - Uses all historical data
user_fraud_rate = frauds / total_transactions

# CORRECT - Uses only data before event_time
user_fraud_rate = frauds_before_event_time / transactions_before_event_time
```

**Solution:**
- All aggregations filtered by `event_time < current_transaction_time`
- Explicit temporal windows (e.g., "fraud rate in last 30 days")
- Database schema enforces temporal ordering

### Challenge 3: Review Capacity Optimization

**Problem:** Can only review top N transactions per day (e.g., 100 out of 10,000).

**Solution:**
- Score all transactions with fraud probability
- Route high-risk (score > threshold) to review queue
- Track review outcomes to measure precision
- Optimize threshold to maximize fraud caught within capacity

### Challenge 4: Model Monitoring & Drift

**Problem:** Fraud patterns change, models degrade over time.

**Solution:**
- Track prediction distribution shifts (PSI - Population Stability Index)
- Monitor feature distributions
- Alert on significant drift
- Support model rollback if performance degrades

---

## 🏗️ System Architecture

### High-Level Components

```
┌─────────────────┐
│   Simulation    │  Generate synthetic transactions + delayed labels
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Feature Store  │  SQLite with event-time semantics
│   (SQLite DB)   │  - transactions table (event_time)
└────────┬────────┘  - labels table (label_time)
         │           - features table (computed at event_time)
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌─────────┐
│Training │ │ Scoring │  Real-time inference
│Pipeline │ │ Service │  - Load model
└────┬────┘ └────┬────┘  - Compute features
     │           │        - Score transaction
     │           │        - Route to review
     ▼           ▼
┌─────────────────┐
│  Review Queue   │  Human review interface
│  + Monitoring   │  - Prioritized by score
└─────────────────┘  - Track outcomes
```

### Data Flow

1. **Transaction Arrives** → Stored with `event_time`
2. **Features Computed** → Using only data before `event_time`
3. **Model Scores** → Fraud probability assigned
4. **Routing Decision** → High scores → Review queue
5. **Label Arrives** (delayed) → Stored with `label_time`
6. **Training Pipeline** → Joins transactions + labels + features
7. **Model Updated** → New version deployed
8. **Monitoring** → Tracks drift, alerts on issues

### Database Schema (Event-Time Correctness)

```sql
-- Core transaction data
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,  -- When transaction occurred
    user_id TEXT NOT NULL,
    amount REAL NOT NULL,
    merchant_category TEXT,
    -- ... other transaction fields
    INDEX idx_event_time (event_time),
    INDEX idx_user_event (user_id, event_time)
);

-- Delayed fraud labels
CREATE TABLE labels (
    transaction_id TEXT PRIMARY KEY,
    label_time TIMESTAMP NOT NULL,  -- When fraud was confirmed
    is_fraud INTEGER NOT NULL,      -- 0 or 1
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

-- Pre-computed features (event-time safe)
CREATE TABLE features (
    transaction_id TEXT PRIMARY KEY,
    computed_at TIMESTAMP NOT NULL,  -- Must equal event_time
    user_transaction_count_30d INTEGER,
    user_fraud_rate_30d REAL,
    -- ... other features
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

-- Model predictions
CREATE TABLE predictions (
    transaction_id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    fraud_score REAL NOT NULL,
    prediction_time TIMESTAMP NOT NULL,
    routed_to_review INTEGER NOT NULL
);
```

**Key Design Principle:** Every table has a timestamp column that establishes temporal ordering. Features are computed using only data where `event_time < current_transaction_time`.

---

## 🎨 Design Principles

### 1. Event-Time Semantics

**All features must be computable at transaction time using only historical data.**

```python
# Feature computation template
def compute_user_features(user_id, event_time, db):
    """
    Compute features for user at specific event_time.
    Only uses data where event_time < current event_time.
    """
    query = """
        SELECT 
            COUNT(*) as transaction_count,
            AVG(amount) as avg_amount,
            SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) as fraud_count
        FROM transactions t
        LEFT JOIN labels l ON t.transaction_id = l.transaction_id
        WHERE t.user_id = ?
          AND t.event_time < ?
          AND t.event_time >= datetime(?, '-30 days')
    """
    return db.execute(query, (user_id, event_time, event_time)).fetchone()
```

### 2. Separation of Concerns

- **simulation/** - Data generation (synthetic transactions + labels)
- **features/** - Feature engineering (event-time safe)
- **training/** - Model training pipeline
- **scoring/** - Real-time inference service
- **review/** - Review queue management
- **monitoring/** - Model health tracking

### 3. Reproducibility

- All data generation is seeded
- Training splits are deterministic
- Model artifacts versioned with metadata
- Feature computation is idempotent

### 4. Production Readiness

- Model versioning and rollback
- Monitoring and alerting
- Schema validation
- Error handling and logging
- Performance metrics

---

## 🛠️ Technology Stack

### Core Technologies

- **Python 3.9+** - Primary language
- **SQLite** - Database (event-time queries, ACID guarantees)
- **scikit-learn** - ML framework (Logistic Regression, Random Forest)
- **pandas** - Data manipulation
- **pytest** - Testing framework

### Why SQLite?

1. **ACID Transactions** - Ensures data consistency
2. **Temporal Queries** - Efficient event-time filtering with indexes
3. **Zero Configuration** - No separate database server
4. **Portable** - Single file, easy to share
5. **Production-Ready** - Used by major companies (Apple, Airbus, etc.)

### Project Structure

```
fraud-risk-streaming/
├── docs/                    # All documentation
│   ├── PROJECT_GUIDE.md    # This file - START HERE
│   ├── PRD.md              # Product requirements
│   ├── ARCHITECTURE.md     # Detailed architecture
│   ├── DAY_BY_DAY_PLAN.md  # Implementation timeline
│   ├── MAKEFILE_SPEC.md    # Build commands
│   ├── SCHEMA_SPEC.md      # Database schemas
│   └── FAILURE_INJECTION_GUIDE.md  # Testing guide
│
├── data/
│   └── schemas/            # JSON schemas for validation
│
├── artifacts/
│   ├── models/             # Trained model files (.pkl)
│   ├── reports/            # Training reports, metrics
│   └── screenshots/        # Visualizations
│
├── fraud_risk/             # Core library code
├── simulation/             # Transaction + label generation
├── features/               # Feature engineering
├── training/               # Model training pipeline
├── scoring/                # Real-time inference
├── review/                 # Review queue management
├── monitoring/             # Model monitoring & alerts
├── scripts/                # Utility scripts
│   └── failure_injection/  # Testing failure scenarios
└── tests/                  # Unit and integration tests
```

---

## 📅 7-Day MVP Plan

### Day 1-2: Foundation & Data Generation

**Goal:** Set up project structure and generate synthetic data

- ✅ Create repository structure
- ✅ Write PROJECT_GUIDE.md (this file)
- [ ] Implement transaction simulator
  - Generate realistic transaction patterns
  - User behavior modeling (frequency, amounts)
  - Merchant categories
- [ ] Implement label simulator
  - Delayed label generation (random delays)
  - Fraud rate configuration (e.g., 2% fraud rate)
- [ ] Create SQLite schema
  - transactions, labels, features tables
  - Indexes for event-time queries
- [ ] Generate initial dataset (10K transactions)

**Deliverables:**
- `simulation/transaction_generator.py`
- `simulation/label_generator.py`
- `data/schemas/schema.sql`
- `fraud_risk.db` (SQLite database)

### Day 3: Feature Engineering

**Goal:** Build event-time safe feature pipeline

- [ ] Implement feature computation functions
  - User aggregates (transaction count, avg amount)
  - Temporal features (time of day, day of week)
  - Fraud rate features (with event-time filtering)
- [ ] Create feature validation
  - Ensure no future data leakage
  - Test temporal correctness
- [ ] Populate features table
- [ ] Document feature definitions

**Deliverables:**
- `features/compute_features.py`
- `features/feature_definitions.md`
- `tests/test_feature_temporal_correctness.py`

### Day 4: Training Pipeline

**Goal:** Train initial fraud detection model

- [x] Implement training pipeline
  - Join transactions + labels + features
  - Train/validation/test split (temporal)
  - Model training (Logistic Regression baseline)
- [x] Model evaluation
  - Precision, Recall, F1 at various thresholds
  - ROC curve, PR curve
  - Calibration analysis
- [x] Save model artifacts
  - Model file (.pkl)
  - Training metadata (features used, metrics)
  - Feature importance

**Deliverables:**
- `training/train_model.py`
- `training/evaluate_model.py`
- `artifacts/models/fraud_model_v1.pkl`
- `artifacts/reports/training_report_v1.json`

### Day 5: Scoring Service

**Goal:** Real-time inference with review routing

- [x] Implement scoring service
  - Load trained model
  - Compute features for new transaction
  - Generate fraud score
  - Route to review if score > threshold
- [x] Review queue management
  - Priority queue (sorted by score)
  - Capacity constraints (max N per day)
  - Track review outcomes
- [x] Performance optimization
  - Feature caching
  - Batch scoring

**Deliverables:**
- `scoring/score_transactions.py`
- `review/build_queue.py`
- `tests/test_scoring.py`

### Day 6: Monitoring & Drift Detection

**Goal:** Production monitoring and alerting

- [ ] Implement drift detection
  - PSI (Population Stability Index) for predictions
  - Feature distribution monitoring
  - Alert thresholds
- [ ] Model performance tracking
  - Precision/recall over time
  - False positive rate
  - Review queue metrics
- [ ] Visualization dashboard
  - Score distribution plots
  - Drift metrics over time
  - Review queue status

**Deliverables:**
- `monitoring/drift_detection.py`
- `monitoring/performance_tracker.py`
- `artifacts/reports/monitoring_dashboard.html`

### Day 7: Testing & Documentation

**Goal:** Production readiness and handoff

- [x] Comprehensive testing
  - Unit tests for all components
  - Integration tests (end-to-end)
  - Failure injection tests
- [x] Documentation completion
  - API documentation
  - Deployment guide
  - Troubleshooting guide
- [x] Demo preparation
  - Sample transactions
  - Walkthrough script
  - Performance benchmarks

**Deliverables:**
- `tests/` (full test suite)
- `docs/API.md`
- `docs/DEPLOYMENT.md`
- `scripts/demo.py`

---

## 📊 Current Status

### ✅ Completed

- [x] Repository structure created
- [x] PROJECT_GUIDE.md written
- [x] .gitignore configured
- [x] README.md created
- [x] Day 1 transaction simulation implemented
- [x] Day 2 delayed label generation implemented
- [x] Day 3 event-time feature engineering implemented
- [x] Day 4 training pipeline implemented
- [x] Day 5 scoring and review queue implemented
- [x] Day 6 monitoring and drift detection implemented
- [x] Day 7 testing, docs, demo, and failure injection implemented

### 🚧 In Progress

- [ ] None currently

### 📋 Next Up

- [ ] Extend the demo with charts or screenshots if needed
- [ ] Add more failure scenarios as the system evolves
- [ ] Port the pipeline to a service-based deployment if required

### 🎯 Milestone Progress

**MVP Progress: 100% Complete** (Day 7 of 7)

---

## 🚀 Next Steps

### Immediate Actions (Start Here)

1. **Review this guide thoroughly** - Understand the problem and architecture
2. **Read README.md** - Follow the concise project overview and commands
3. **Read docs/DEPLOYMENT.md** - See the supported setup and execution flow
4. **Run make demo** - Reproduce the end-to-end pipeline locally

### Development Workflow

```bash
# 1. Set up environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Run the full demo
make demo

# 3. Run monitoring directly
python -m monitoring.drift_detection

# 4. Inject a failure scenario
make inject-failure SCENARIO=label_delay
```

### Key Files to Create Next

1. `requirements.txt` - Python dependencies
2. `Makefile` - Build automation (see MAKEFILE_SPEC.md)
3. `simulation/transaction_generator.py` - First implementation file
4. `data/schemas/schema.sql` - Database schema

---

## 📚 Documentation Structure

This project uses a multi-document approach for clarity:

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **PROJECT_GUIDE.md** (this file) | Complete project overview, handoff document | **START HERE** - Read first |
| **PRD.md** | Product requirements, business context | After PROJECT_GUIDE |
| **ARCHITECTURE.md** | Detailed technical architecture, design decisions | When implementing |
| **DAY_BY_DAY_PLAN.md** | Detailed implementation timeline with code examples | Daily reference |
| **SCHEMA_SPEC.md** | Database schema, indexes, queries | When working with data |
| **MAKEFILE_SPEC.md** | Build commands, automation | When setting up workflows |
| **FAILURE_INJECTION_GUIDE.md** | Testing failure scenarios | When testing |
| **README_TEMPLATE.md** | Template for component READMEs | When documenting code |

**Navigation Tip:** Each document links to related documents. Follow the links as needed.

---

## 💼 Interview Talking Points

### What Makes This Project Stand Out

1. **Real-World Problem Solving**
   - "This isn't a Kaggle dataset - it solves actual production challenges"
   - "Delayed labels are common in fraud, credit risk, and ad click prediction"

2. **Temporal Correctness**
   - "Preventing data leakage in time-series ML is critical but often overlooked"
   - "I designed a database schema that enforces event-time semantics"

3. **System Design**
   - "This demonstrates end-to-end ML system design, not just model training"
   - "I considered scalability, monitoring, and production operations"

4. **Business Impact**
   - "Optimizing review capacity is a real constraint in fraud operations"
   - "I can explain the precision/recall tradeoff in business terms"

5. **Production ML**
   - "I implemented model versioning, monitoring, and rollback capabilities"
   - "The system detects drift and alerts when model performance degrades"

### Technical Deep Dives

**If asked about event-time correctness:**
- Explain the data leakage problem with examples
- Walk through the SQL query that ensures temporal filtering
- Discuss how indexes optimize event-time queries

**If asked about architecture:**
- Draw the component diagram
- Explain separation of concerns
- Discuss why SQLite was chosen over other databases

**If asked about monitoring:**
- Explain PSI (Population Stability Index)
- Discuss alert thresholds and false positive rates
- Show how to detect model degradation

**If asked about scalability:**
- Discuss how to migrate from SQLite to PostgreSQL/Cassandra
- Explain feature caching strategies
- Talk about batch vs. real-time scoring tradeoffs

---

## 🔄 How to Use This Guide

### For New Chat Sessions

When starting a new chat session, provide this context:

```
I'm working on the fraud-risk-streaming project. Please read 
docs/PROJECT_GUIDE.md to understand the project context, then 
help me with [specific task].
```

### For Continuing Development

1. **Check Current Status** - See what's completed above
2. **Review Next Steps** - See what to work on next
3. **Update Status** - Mark tasks complete as you finish them
4. **Update This Guide** - Keep it current as the project evolves

### For Debugging

1. **Check Architecture** - Understand component interactions
2. **Review Design Principles** - Ensure temporal correctness
3. **Check Schema** - Verify database queries
4. **Review Tests** - Look for similar test cases

### For Demos/Interviews

1. **Read Interview Talking Points** - Prepare key messages
2. **Review Architecture Diagram** - Be ready to draw it
3. **Prepare Examples** - Have code snippets ready
4. **Know the Numbers** - Dataset size, performance metrics

---

## 🎓 Learning Resources

### Concepts to Understand

1. **Event-Time vs. Processing-Time**
   - Event time: When event occurred
   - Processing time: When system processes event
   - Why this matters in streaming systems

2. **Data Leakage in Time-Series**
   - Using future information in features
   - How to prevent it with temporal filtering
   - Testing for leakage

3. **Model Monitoring**
   - PSI (Population Stability Index)
   - Feature drift vs. concept drift
   - When to retrain vs. rollback

4. **Review Queue Optimization**
   - Precision/recall tradeoff
   - Capacity constraints
   - Threshold tuning

### Recommended Reading

- "Designing Data-Intensive Applications" by Martin Kleppmann (Chapter 11: Stream Processing)
- "Machine Learning Design Patterns" by Lakshmanan et al. (Chapter 5: Reproducibility)
- "Reliable Machine Learning" by Hulten (Chapter 8: Monitoring)

---

## 📝 Maintenance Notes

### Updating This Guide

As the project evolves, update these sections:

1. **Current Status** - Mark tasks complete, add new tasks
2. **Next Steps** - Update immediate actions
3. **Milestone Progress** - Update percentage complete
4. **Technology Stack** - Add new dependencies
5. **Interview Talking Points** - Add new achievements

### Version History

- **v1.0** (2026-05-13) - Initial creation, project setup complete

---

## 🤝 Contributing

This is a personal project for learning and interviews. However, if you're using this as a template:

1. Fork the repository
2. Customize for your use case
3. Update PROJECT_GUIDE.md with your changes
4. Share your learnings!

---

## 📞 Contact & Questions

For questions about this project or to discuss fraud detection systems:

- **GitHub Issues** - For bugs or feature requests
- **LinkedIn** - For professional inquiries
- **Email** - For collaboration opportunities

---

## 🎯 Success Criteria

This project is successful when:

- ✅ All 7 days of MVP plan are complete
- ✅ System handles 10K+ transactions with <100ms scoring latency
- ✅ Model achieves >80% precision at 10% review capacity
- ✅ Drift detection alerts within 1 day of distribution shift
- ✅ Complete test coverage (>80%)
- ✅ Documentation is comprehensive and clear
- ✅ Demo is polished and impressive

**Most importantly:** You can confidently explain every design decision and tradeoff in an interview.

---

## 🚀 Let's Build!

You now have everything you need to understand and continue this project. Start with the Next Steps section, and remember:

**This project demonstrates production ML engineering, not just model training.**

Good luck! 🎉

---

*Last Updated: 2026-05-13*
*Version: 1.0*
*Status: Foundation Complete, Ready for Day 1 Implementation*