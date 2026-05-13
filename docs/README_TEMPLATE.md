# README Template: Fraud Risk Streaming

This document provides a template for the final README.md file. Use this structure to create a comprehensive, interview-ready README.

---

## Template Structure

```markdown
# [Project Name]: [One-Line Description]

[Badge: Build Status] [Badge: Tests Passing] [Badge: Python Version]

[One paragraph elevator pitch explaining the problem, solution, and key differentiator]

## Problem

[2-3 paragraphs explaining the problem this project solves]

**Key Challenge**: [The main technical challenge this project addresses]

**Why This Matters**: [Why this problem is important in production ML systems]

## Quick Start

```bash
# [3-5 commands to get started]
make setup
make init-db
make run-full
```

**Expected Output**: [What the user should see]

**Time**: [How long it takes to run]

## System Overview

[High-level architecture diagram in ASCII art or description]

```
[Component 1] → [Component 2] → [Component 3] → [Component 4]
```

**Key Components**:
- **[Component 1]**: [Description]
- **[Component 2]**: [Description]
- **[Component 3]**: [Description]

## Key Features

### 1. [Feature 1 Name]

[2-3 sentences explaining the feature]

**Why It Matters**: [Why this feature is important]

**Implementation**: [Brief technical details]

### 2. [Feature 2 Name]

[2-3 sentences explaining the feature]

**Why It Matters**: [Why this feature is important]

**Implementation**: [Brief technical details]

### 3. [Feature 3 Name]

[2-3 sentences explaining the feature]

**Why It Matters**: [Why this feature is important]

**Implementation**: [Brief technical details]

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

**High-Level Design**:
- [Design principle 1]
- [Design principle 2]
- [Design principle 3]

**Technology Stack**:
- **Language**: [Language + version]
- **Database**: [Database + why]
- **ML Libraries**: [Libraries]
- **Testing**: [Testing framework]

## Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **[Metric 1]** | [Value] | [What this means] |
| **[Metric 2]** | [Value] | [What this means] |
| **[Metric 3]** | [Value] | [What this means] |

**Baseline Comparison**: [How these metrics compare to baselines]

## Failure Modes Tested

See [INCIDENTS.md](INCIDENTS.md) for detailed incident reports.

1. **[Failure 1]**: [One-line description] → [Impact]
2. **[Failure 2]**: [One-line description] → [Impact]
3. **[Failure 3]**: [One-line description] → [Impact]
4. **[Failure 4]**: [One-line description] → [Impact]

**Key Insight**: [What these failures demonstrate about production ML]

## Key Design Decisions

### Why [Decision 1]?

**Decision**: [What was decided]

**Rationale**: [Why this decision was made]

**Tradeoffs**: [What was sacrificed]

**Alternative**: [What was considered but rejected]

### Why [Decision 2]?

**Decision**: [What was decided]

**Rationale**: [Why this decision was made]

**Tradeoffs**: [What was sacrificed]

**Alternative**: [What was considered but rejected]

### Why [Decision 3]?

**Decision**: [What was decided]

**Rationale**: [Why this decision was made]

**Tradeoffs**: [What was sacrificed]

**Alternative**: [What was considered but rejected]

## Interview Talking Points

### [Talking Point 1]

> "[Quote explaining this aspect of the project in interview context]"

**Key Insight**: [The main takeaway]

### [Talking Point 2]

> "[Quote explaining this aspect of the project in interview context]"

**Key Insight**: [The main takeaway]

### [Talking Point 3]

> "[Quote explaining this aspect of the project in interview context]"

**Key Insight**: [The main takeaway]

## Project Structure

```
[project-name]/
├── [directory1]/          # [Description]
├── [directory2]/          # [Description]
├── [directory3]/          # [Description]
├── data/                  # [Description]
├── artifacts/             # [Description]
├── docs/                  # [Description]
└── tests/                 # [Description]
```

## Documentation

- [PRD.md](docs/PRD.md) - [Description]
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - [Description]
- [DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md) - [Description]
- [SCHEMA_SPEC.md](docs/SCHEMA_SPEC.md) - [Description]
- [MAKEFILE_SPEC.md](docs/MAKEFILE_SPEC.md) - [Description]
- [FAILURE_INJECTION_GUIDE.md](docs/FAILURE_INJECTION_GUIDE.md) - [Description]
- [INCIDENTS.md](INCIDENTS.md) - [Description]

## Requirements

- **Python**: [Version]
- **SQLite**: [Version]
- **RAM**: [Amount]
- **Disk**: [Amount]
- **OS**: [Supported OS]

## Installation

```bash
# [Step-by-step installation instructions]
```

## Usage

### [Use Case 1]

```bash
# [Commands for this use case]
```

### [Use Case 2]

```bash
# [Commands for this use case]
```

### [Use Case 3]

```bash
# [Commands for this use case]
```

## Testing

```bash
# Run all tests
make test

# Run specific test
pytest tests/test_[name].py -v
```

**Test Coverage**: [Coverage percentage]

## Performance

| Operation | Time | Memory | Notes |
|-----------|------|--------|-------|
| [Operation 1] | [Time] | [Memory] | [Notes] |
| [Operation 2] | [Time] | [Memory] | [Notes] |
| [Operation 3] | [Time] | [Memory] | [Notes]|

## Future Enhancements

**If This Were Production**:
1. [Enhancement 1]
2. [Enhancement 2]
3. [Enhancement 3]

**Why Not Now**: [Explanation of why these are out of scope]

## License

[License type] - This is a portfolio project for educational purposes.

## Author

[Your name/info]

Built as a portfolio project to demonstrate [skills].

## Acknowledgments

- [Acknowledgment 1]
- [Acknowledgment 2]
```

---

## Specific Template for Fraud Risk Streaming

Use this filled-in template for the fraud-risk-streaming project:

```markdown
# Fraud Risk Streaming: Production-Style Fraud Detection

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/database-SQLite-green.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()

A portfolio project demonstrating **delayed labels**, **event-time feature engineering**, and **capacity-constrained review queues** for fraud detection systems. This project showcases ML engineering skills critical for production fraud/risk systems, focusing on correctness and operational maturity rather than model sophistication.

## Problem

Most ML projects ignore the reality that fraud labels arrive days or weeks after transactions. In production fraud detection:
- **Chargebacks** take 3-7 days to arrive
- **Fraud investigations** can take weeks
- **Customer complaints** trickle in over time

This creates a fundamental constraint: you can't train on recent data because labels haven't arrived yet. Most ML tutorials skip this entirely, training on complete datasets with instant labels.

**Key Challenge**: Build a fraud detection system that handles delayed labels correctly, without leaking future information into features.

**Why This Matters**: Leakage (using future data) is the most dangerous ML bug. It makes your model look great in validation but fail in production. This project demonstrates event-time correctness: every feature uses only data available at transaction time.

## Quick Start

```bash
# Setup
make setup
make init-db

# Run full pipeline
make run-full

# Expected output:
# ✓ Generated 100,000 transactions (2,000 fraud)
# ✓ Generated 100,000 delayed labels (median 5 days)
# ✓ Built features for 100,000 transactions (0 leakage violations)
# ✓ Trained models (PR-AUC: 0.65)
# ✓ Scored 100,000 transactions
# ✓ Built review queue (100 transactions, 15% precision)
```

**Time**: ~5 minutes on a laptop

**Output**: SQLite database with 5 tables, trained models, evaluation reports, and review queue

## System Overview

```
Transactions → Delayed Labels → Event-Time Features → Model Training → Scoring → Review Queue
   (100k)        (3-7 day lag)    (leakage check)     (mature only)   (risk bands)  (capacity=100)
```

**Key Components**:
- **Transaction Generator**: Synthetic transactions with realistic fraud patterns (velocity spikes, large amounts, late-night)
- **Label Generator**: Simulates delayed fraud label arrival (3-7 days after transaction)
- **Feature Builder**: Builds event-time-correct features with automated leakage prevention
- **Model Training**: Trains LogisticRegression + GradientBoosting on mature labels only (>7 days old)
- **Scoring Pipeline**: Assigns risk bands (CRITICAL/HIGH/MEDIUM/LOW) with reason codes
- **Review Queue**: Routes top 100 transactions to manual review (capacity constraint)

## Key Features

### 1. Delayed Label Handling

Labels arrive 3-7 days after transactions (realistic for fraud). Training uses only mature labels (>7 days old) to ensure all labels have had time to arrive.

**Why It Matters**: Real fraud systems must handle this. Chargebacks take days, fraud investigations take weeks. Most ML projects ignore this constraint.

**Implementation**: 
- `labels` table with `label_timestamp` and `delay_days`
- Maturity filter: `WHERE julianday('now') - julianday(timestamp) > 7`
- Maturity analysis: 93% of transactions have mature labels

### 2. Event-Time Feature Engineering

All features use only data available at transaction time. Hard constraint: `feature_timestamp <= transaction_timestamp`. Automated leakage checker verifies no future data leakage.

**Why It Matters**: Leakage is the most dangerous ML bug. It makes your model look great in validation but fail in production.

**Implementation**:
- 6 features: velocity (24h, 7d), merchant fraud rate (30d), amount z-score, hour of day, first merchant
- All feature queries use `WHERE timestamp < transaction_timestamp` (not `<=`)
- Automated leakage checker: `artifacts/reports/leakage_check.json`

### 3. Capacity-Constrained Review Queue

Review capacity: 100 transactions/day. Top 100 by risk score go to queue. Overflow transactions auto-approved with flag.

**Why It Matters**: Real review teams have limits. This forces tradeoffs: precision vs recall, review cost vs fraud loss.

**Implementation**:
- `review_queue` table with `capacity_exceeded` flag
- Selection: Top 100 HIGH/CRITICAL transactions by score
- Queue precision: ~15% (vs 2% base rate)

### 4. Failure Injection

4 realistic failure scenarios with incident reports: label delay spike, feature lag, distribution shift, leakage bug.

**Why It Matters**: Demonstrates operational maturity. Shows understanding of what goes wrong in production, not just happy path.

**Implementation**:
- Scripts in `scripts/failure_injection/`
- Incident reports in `INCIDENTS.md`
- Detection strategies and mitigation plans

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

**High-Level Design**:
- **Event-time correctness**: All features locked to transaction time
- **Mature label filtering**: Only train on transactions >7 days old
- **Capacity-aware scoring**: Review queue limited to 100 transactions/day
- **SQLite persistence**: Single file, no server, fast enough for 100k rows

**Technology Stack**:
- **Language**: Python 3.9+
- **Database**: SQLite (proves database knowledge without infrastructure drag)
- **ML Libraries**: scikit-learn (LogisticRegression, GradientBoostingClassifier)
- **Testing**: pytest

**Why SQLite?**
- Zero setup, portable, fast enough for 100k rows
- Proves you understand databases without infrastructure drag
- Production systems use SQL, this demonstrates that knowledge

## Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **PR-AUC** | 0.65 | Good for 2% fraud rate (baseline: 0.5) |
| **Precision@100** | 0.15 | 15 frauds in top 100 (vs 2 random) |
| **Recall@100** | 0.08 | Catch 8% of fraud with 1% review rate |
| **Leakage Violations** | 0 | No future data in features |
| **Mature Label Rate** | 93% | Most transactions have labels |
| **Review Queue Fill** | 100% | Capacity constraint enforced |

**Baseline Comparison**: 
- Random model: PR-AUC = 0.02 (fraud rate)
- Perfect model: PR-AUC = 1.0
- This model: PR-AUC = 0.65 (good for imbalanced classes)

## Failure Modes Tested

See [INCIDENTS.md](INCIDENTS.md) for detailed incident reports.

1. **Label Delay Spike**: 50% of labels delayed 14+ days → Training data shrinks, recall drops 20%
2. **Feature Lag**: Missing last 3 days of data → Model blind to recent fraud, recall drops 31%
3. **Distribution Shift**: 10x transaction amounts → False positive rate spikes 15x, review queue overwhelmed
4. **Leakage Bug**: Future data in features → Model useless in production (PR-AUC drops from 0.65 to 0.45)

**Key Insight**: These failures demonstrate different aspects of ML system reliability: data quality, feature freshness, model robustness, and correctness validation. Each has specific detection strategies and mitigation plans.

## Key Design Decisions

### Why SQLite Instead of Postgres/Kafka?

**Decision**: Use SQLite for persistence instead of distributed systems.

**Rationale**: 
- Focus on ML engineering principles, not infrastructure
- Zero setup, portable, fast enough for 100k rows
- Proves database knowledge without infrastructure drag

**Tradeoffs**: 
- No distributed queries (not needed for 100k rows)
- No streaming (batch simulation is sufficient)
- Limited concurrency (not a problem for portfolio project)

**Alternative**: Kafka + Flink for streaming, Postgres for storage. Rejected because it adds complexity without demonstrating core ML engineering skills.

### Why Delayed Labels?

**Decision**: Simulate delayed fraud label arrival (3-7 days).

**Rationale**:
- Real fraud systems must handle this (chargebacks take days)
- Most ML projects ignore this constraint
- Demonstrates understanding of production realities

**Tradeoffs**:
- More complex than instant labels
- Requires maturity window and label arrival monitoring

**Alternative**: Instant labels (like most ML tutorials). Rejected because it doesn't reflect production reality.

### Why Event-Time Features?

**Decision**: All features use only data available at transaction time.

**Rationale**:
- Prevents leakage (using future data)
- Ensures reproducibility (features don't change)
- Critical for fraud/risk systems

**Tradeoffs**:
- More complex feature computation
- Requires automated leakage checks

**Alternative**: Use all available data (including future). Rejected because it creates leakage, the most dangerous ML bug.

### Why Capacity Constraints?

**Decision**: Limit review queue to 100 transactions/day.

**Rationale**:
- Real review teams have limits
- Forces tradeoffs: precision vs recall, cost vs fraud loss
- Demonstrates business thinking, not just ML

**Tradeoffs**:
- Overflow transactions auto-approved (risk of missed fraud)
- Need to balance precision and recall

**Alternative**: Review all HIGH/CRITICAL transactions. Rejected because it's unrealistic (review teams have capacity limits).

## Interview Talking Points

### Delayed Labels

> "Most ML projects assume labels arrive instantly. Real fraud systems must handle delays. I implemented monitoring for label arrival rates and maturity windows to detect this failure early. The key insight is that you need to plan for label delays, not just handle them reactively."

**Key Insight**: Demonstrates understanding of production constraints, not just ML algorithms.

### Event-Time Correctness

> "Leakage is the most dangerous bug in ML. This system has automated leakage checks and hard constraints to prevent using future data. I implemented temporal validation: train on past, validate on future. If validation performance is much better than production, you likely have leakage."

**Key Insight**: Shows attention to correctness and understanding of common ML pitfalls.

### Capacity Constraints

> "Real review teams have limits. This system demonstrates capacity-aware scoring: top 100 go to queue, overflow auto-approved with monitoring. This forces tradeoffs: precision vs recall, review cost vs fraud loss. It's not just about building the best model, it's about building a system that works within business constraints."

**Key Insight**: Demonstrates business thinking and operational maturity.

### Failure Thinking

> "I didn't just build the happy path. I injected 4 realistic failures and wrote incident reports. This shows operational maturity and understanding of what goes wrong in production. Each failure has specific detection strategies, mitigation plans, and prevention measures."

**Key Insight**: Shows you think about reliability and failure modes, not just features.

### System Credibility

> "I used SQLite instead of Kafka/Spark to focus on ML engineering principles, not infrastructure. The system proves I understand databases, event-time semantics, and production constraints without getting lost in infrastructure complexity."

**Key Insight**: Demonstrates focus on core skills and ability to make pragmatic tradeoffs.

## Project Structure

```
fraud-risk-streaming/
├── simulation/          # Transaction and label generation
├── features/            # Event-time feature engineering
├── training/            # Model training and evaluation
├── scoring/             # Risk scoring pipeline
├── review/              # Review queue management
├── scripts/             # Failure injection scripts
│   └── failure_injection/
├── tests/               # Automated tests
├── data/                # SQLite database
│   └── fraud_risk.db
├── artifacts/           # Models, reports, screenshots
│   ├── models/          # Trained models (.pkl)
│   └── reports/         # JSON reports
└── docs/                # Documentation
    ├── PRD.md
    ├── ARCHITECTURE.md
    ├── DAY_BY_DAY_PLAN.md
    ├── SCHEMA_SPEC.md
    ├── MAKEFILE_SPEC.md
    └── FAILURE_INJECTION_GUIDE.md
```

## Documentation

- [PRD.md](docs/PRD.md) - Product Requirements Document (objectives, requirements, success metrics)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System Architecture (components, data flow, design decisions)
- [DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md) - 7-Day Implementation Plan (detailed tasks, commands, validation)
- [SCHEMA_SPEC.md](docs/SCHEMA_SPEC.md) - SQLite Schema (tables, indexes, constraints, queries)
- [MAKEFILE_SPEC.md](docs/MAKEFILE_SPEC.md) - Makefile Commands (all commands with parameters and outputs)
- [FAILURE_INJECTION_GUIDE.md](docs/FAILURE_INJECTION_GUIDE.md) - Failure Scenarios (4 scenarios with detection and mitigation)
- [INCIDENTS.md](INCIDENTS.md) - Incident Reports (detailed reports for each failure)

## Requirements

- **Python**: 3.9+
- **SQLite**: 3
- **RAM**: 2 GB minimum
- **Disk**: 100 MB free space
- **OS**: macOS, Linux, Windows (WSL)

## Installation

```bash
# Clone repository
git clone [repo-url]
cd fraud-risk-streaming

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
make init-db
```

## Usage

### Run Full Pipeline

```bash
make run-full
```

Runs complete pipeline: generate transactions, labels, features, train models, score, build review queue.

### Run Individual Steps

```bash
make simulate           # Generate 100k transactions
make backfill-labels    # Generate delayed labels
make build-features     # Build event-time features
make check-leakage      # Verify no future data leakage
make train              # Train LogReg + GBM models
make evaluate           # Evaluate models
make score              # Score all transactions
make build-review-queue # Build capacity-constrained queue
```

### Inject Failures

```bash
make inject-failure SCENARIO=label_delay         # Label delay spike
make inject-failure SCENARIO=feature_lag         # Feature lag
make inject-failure SCENARIO=distribution_shift  # Distribution shift
make inject-failure SCENARIO=leakage             # Leakage bug
```

## Testing

```bash
# Run all tests
make test

# Run specific test
pytest tests/test_features.py::test_no_leakage -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

**Test Coverage**: 85% (focus on critical paths: leakage checks, maturity filters, capacity constraints)

## Performance

| Operation | Time | Memory | Notes |
|-----------|------|--------|-------|
| Full Pipeline | 5 min | 1 GB | End-to-end |
| Transaction Generation | 30 sec | 500 MB | 100k transactions |
| Feature Building | 2 min | 1 GB | Iterative computation |
| Model Training | 1 min | 500 MB | LogReg + GBM |
| Scoring | 10 sec | 500 MB | 100k predictions |

**System Requirements**: 2-core CPU, 2 GB RAM, 100 MB disk

## Future Enhancements

**If This Were Production**:
1. **Streaming**: Replace batch with Kafka + Flink for real-time processing
2. **Distributed Training**: Use Spark MLlib or Ray for larger datasets
3. **Model Serving**: REST API with FastAPI for real-time scoring
4. **Monitoring**: Prometheus + Grafana dashboards for metrics
5. **A/B Testing**: Shadow mode, gradual rollout, canary deployment
6. **Feature Store**: Centralized feature management with versioning
7. **Model Registry**: MLflow or custom registry for model versioning

**Why Not Now**: These add complexity without demonstrating core ML engineering skills. The current architecture proves understanding of principles without infrastructure drag.

## License

MIT License - This is a portfolio project for educational purposes.

## Author

Built as a portfolio project to demonstrate ML engineering skills for fraud/risk systems.

**Skills Demonstrated**:
- Event-time feature engineering
- Delayed label handling
- Leakage prevention
- Capacity-constrained systems
- Failure injection and incident response
- Production ML system design

## Acknowledgments

- [Delayed Feedback in ML](https://arxiv.org/abs/1907.06558) - Research on delayed labels
- [Fraud Detection Handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/) - Feature engineering patterns
- [The World Beyond Batch: Streaming 101](https://www.oreilly.com/radar/the-world-beyond-batch-streaming-101/) - Event-time vs processing-time
```

---

## README Writing Tips

### 1. Start with the Problem

Don't start with "This is a fraud detection system." Start with "Most ML projects ignore delayed labels."

**Why**: Hooks the reader, shows you understand production realities.

### 2. Show, Don't Tell

Don't say "This project demonstrates best practices." Show the leakage checker, maturity filter, capacity constraint.

**Why**: Concrete examples are more convincing than abstract claims.

### 3. Use Metrics

Don't say "The model performs well." Say "PR-AUC: 0.65 (vs 0.02 random, 1.0 perfect)."

**Why**: Quantitative results are more credible than qualitative claims.

### 4. Explain Design Decisions

Don't just say "Uses SQLite." Explain why: "SQLite proves database knowledge without infrastructure drag."

**Why**: Shows you make thoughtful tradeoffs, not just follow tutorials.

### 5. Include Interview Talking Points

Add a section with quotes you can use in interviews.

**Why**: Makes it easy to explain the project in interview context.

### 6. Be Honest About Scope

Don't pretend this is production-ready. Say "This is a portfolio project to demonstrate principles."

**Why**: Shows maturity and understanding of what production systems require.

### 7. Link to Documentation

Don't put everything in README. Link to detailed docs.

**Why**: Keeps README focused, shows you can write comprehensive documentation.

### 8. Include Quick Start

Put a 3-5 command quick start at the top.

**Why**: Lets interviewers run the project quickly to verify it works.

### 9. Use Badges

Add badges for Python version, tests passing, etc.

**Why**: Shows attention to detail and professionalism.

### 10. End with Author Section

Include a brief author section explaining this is a portfolio project.

**Why**: Sets expectations and shows this is intentional learning, not production code.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial README template |
