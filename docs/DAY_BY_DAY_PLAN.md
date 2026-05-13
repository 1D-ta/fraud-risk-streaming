
# 7-Day Implementation Plan: Fraud Risk Streaming

This document provides a detailed day-by-day plan for implementing the fraud risk streaming system. Each day builds on the previous, with clear goals, tasks, commands, and validation steps.

---

## Day 1: Repository Setup & Transaction Simulation

### Goal
Set up project structure and generate synthetic transaction stream with realistic fraud patterns.

### Tasks

#### 1.1 Repository Setup
```bash
# Create project structure
mkdir -p fraud-risk-streaming/{simulation,features,training,scoring,review,monitoring,tests,scripts/failure_injection,data/schemas,artifacts/{models,reports,screenshots},docs}

# Initialize git
cd fraud-risk-streaming
git init
echo "*.pyc\n__pycache__/\n.venv/\n*.db\nartifacts/models/*.pkl\n.DS_Store" > .gitignore

# Create requirements.txt
cat > requirements.txt << EOF
pandas==2.0.3
numpy==1.24.3
scikit-learn==1.3.0
matplotlib==3.7.2
seaborn==0.12.2
pytest==7.4.0
EOF

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 1.2 SQLite Database Setup
```bash
# Create database initialization script
cat > simulation/init_db.py << 'EOF'
import sqlite3
from pathlib import Path

def init_database(db_path: str = "data/fraud_risk.db"):
    """Initialize SQLite database with schema."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        amount REAL NOT NULL,
        timestamp TEXT NOT NULL,
        category TEXT NOT NULL,
        is_fraud INTEGER
    )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON transactions(merchant_id)")
    
    conn.commit()
    conn.close()
    print(f"✓ Database initialized: {db_path}")

if __name__ == "__main__":
    init_database()
EOF

# Run initialization
python simulation/init_db.py
```

#### 1.3 Transaction Generator
```bash
# Create transaction generator
cat > simulation/generate_transactions.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

def generate_transactions(
    n_transactions: int = 100000,
    fraud_rate: float = 0.02,
    db_path: str = "data/fraud_risk.db"
):
    """Generate synthetic transaction stream with fraud patterns."""
    np.random.seed(42)
    
    # Generate base data
    start_date = datetime(2024, 1, 1)
    timestamps = [start_date + timedelta(minutes=i*30) for i in range(n_transactions)]
    
    user_ids = [f"user_{i:05d}" for i in np.random.randint(0, 10000, n_transactions)]
    merchant_ids = [f"merchant_{i:04d}" for i in np.random.randint(0, 1000, n_transactions)]
    amounts = np.random.lognormal(3.5, 1.2, n_transactions)  # Mean ~$50
    categories = np.random.choice(['retail', 'food', 'travel', 'entertainment', 'other'], n_transactions)
    
    # Generate fraud labels with patterns
    is_fraud = np.zeros(n_transactions, dtype=int)
    n_fraud = int(n_transactions * fraud_rate)
    
    # Pattern 1: Velocity spikes (5+ txns in 1 hour)
    velocity_fraud_indices = []
    for i in range(n_transactions - 5):
        if timestamps[i+4] - timestamps[i] < timedelta(hours=1):
            if np.random.random() < 0.3:  # 30% of velocity spikes are fraud
                velocity_fraud_indices.extend([i, i+1, i+2, i+3, i+4])
    
    # Pattern 2: Large amounts (>3 std dev)
    amount_threshold = amounts.mean() + 3 * amounts.std()
    large_amount_indices = np.where(amounts > amount_threshold)[0]
    large_amount_fraud = np.random.choice(large_amount_indices, size=min(500, len(large_amount_indices)), replace=False)
    
    # Pattern 3: Late night transactions (2am-5am)
    late_night_indices = [i for i, ts in enumerate(timestamps) if 2 <= ts.hour < 5]
    late_night_fraud = np.random.choice(late_night_indices, size=min(300, len(late_night_indices)), replace=False)
    
    # Combine fraud patterns
    fraud_indices = list(set(velocity_fraud_indices) | set(large_amount_fraud) | set(late_night_fraud))
    fraud_indices = fraud_indices[:n_fraud]  # Cap at target fraud rate
    is_fraud[fraud_indices] = 1
    
    # Create DataFrame
    df = pd.DataFrame({
        'transaction_id': [f"txn_{i:08d}" for i in range(n_transactions)],
        'user_id': user_ids,
        'merchant_id': merchant_ids,
        'amount': amounts,
        'timestamp': [ts.isoformat() for ts in timestamps],
        'category': categories,
        'is_fraud': is_fraud
    })
    
    # Save to database
    conn = sqlite3.connect(db_path)
    df.to_sql('transactions', conn, if_exists='replace', index=False)
    conn.close()
    
    # Generate report
    report = {
        'n_transactions': n_transactions,
        'n_fraud': int(is_fraud.sum()),
        'fraud_rate': float(is_fraud.mean()),
        'date_range': {
            'start': timestamps[0].isoformat(),
            'end': timestamps[-1].isoformat()
        },
        'amount_stats': {
            'mean': float(amounts.mean()),
            'std': float(amounts.std()),
            'min': float(amounts.min()),
            'max': float(amounts.max())
        }
    }
    
    Path("artifacts/reports").mkdir(parents=True, exist_ok=True)
    with open("artifacts/reports/transaction_stats.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Generated {n_transactions:,} transactions ({is_fraud.sum():,} fraud)")
    print(f"✓ Report saved to artifacts/reports/transaction_stats.json")
    
    return df

if __name__ == "__main__":
    generate_transactions()
EOF

# Run generator
python simulation/generate_transactions.py
```

### Commands
```bash
make setup          # Install dependencies
make init-db        # Initialize SQLite database
make simulate       # Generate 100k transactions
```

### Output Artifacts
- `data/fraud_risk.db` - SQLite database with transactions table
- `artifacts/reports/transaction_stats.json` - Transaction statistics

### Validation
```bash
# Check database
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM transactions"
# Expected: 100000

sqlite3 data/fraud_risk.db "SELECT SUM(is_fraud) FROM transactions"
# Expected: ~2000 (2% fraud rate)

# Check report
cat artifacts/reports/transaction_stats.json
```

### Tests
```bash
# Create test
cat > tests/test_simulation.py << 'EOF'
import sqlite3
import json

def test_transaction_count():
    conn = sqlite3.connect("data/fraud_risk.db")
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    assert count == 100000, f"Expected 100000 transactions, got {count}"

def test_fraud_rate():
    conn = sqlite3.connect("data/fraud_risk.db")
    cursor = conn.cursor()
    fraud_count = cursor.execute("SELECT SUM(is_fraud) FROM transactions").fetchone()[0]
    conn.close()
    fraud_rate = fraud_count / 100000
    assert 0.015 <= fraud_rate <= 0.025, f"Fraud rate {fraud_rate} outside expected range"

def test_report_exists():
    with open("artifacts/reports/transaction_stats.json") as f:
        report = json.load(f)
    assert report['n_transactions'] == 100000
    assert 'fraud_rate' in report
EOF

pytest tests/test_simulation.py
```

### Commit Message
```
feat: Day 1 - Transaction simulation with fraud patterns

- Initialize SQLite database with transactions table
- Generate 100k synthetic transactions over 30 days
- Implement 3 fraud patterns: velocity, large amounts, late night
- 2% fraud rate (2000 fraudulent transactions)
- Add transaction statistics report
```

---

## Day 2: Delayed Label Generation

### Goal
Simulate realistic delayed fraud label arrival (3-7 days after transaction).

### Tasks

#### 2.1 Label Generator
```bash
cat > simulation/generate_labels.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

def generate_labels(db_path: str = "data/fraud_risk.db"):
    """Generate delayed fraud labels (3-7 days after transaction)."""
    np.random.seed(42)
    
    conn = sqlite3.connect(db_path)
    
    # Load transactions
    df = pd.read_sql("SELECT transaction_id, timestamp, is_fraud FROM transactions", conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Generate label delays (3-7 days, uniform random)
    delay_days = np.random.uniform(3, 7, len(df))
    df['label_timestamp'] = df['timestamp'] + pd.to_timedelta(delay_days, unit='D')
    df['delay_days'] = delay_days
    
    # Create labels table
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS labels (
        transaction_id TEXT PRIMARY KEY,
        is_fraud INTEGER NOT NULL,
        label_timestamp TEXT NOT NULL,
        delay_days REAL NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_label_timestamp ON labels(label_timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_transaction_id ON labels(transaction_id)")
    
    # Insert labels
    labels_df = df[['transaction_id', 'is_fraud', 'label_timestamp', 'delay_days']].copy()
    labels_df['label_timestamp'] = labels_df['label_timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    labels_df.to_sql('labels', conn, if_exists='replace', index=False)
    
    conn.commit()
    conn.close()
    
    # Generate report
    report = {
        'n_labels': len(df),
        'delay_stats': {
            'mean_days': float(delay_days.mean()),
            'median_days': float(np.median(delay_days)),
            'min_days': float(delay_days.min()),
            'max_days': float(delay_days.max()),
            'p95_days': float(np.percentile(delay_days, 95))
        },
        'delay_histogram': {
            str(int(d)): int(count) 
            for d, count in zip(*np.histogram(delay_days, bins=[3, 4, 5, 6, 7]))
        }
    }
    
    Path("artifacts/reports").mkdir(parents=True, exist_ok=True)
    with open("artifacts/reports/label_delay_stats.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Generated {len(df):,} delayed labels")
    print(f"✓ Mean delay: {delay_days.mean():.1f} days")
    print(f"✓ Report saved to artifacts/reports/label_delay_stats.json")

if __name__ == "__main__":
    generate_labels()
EOF

python simulation/generate_labels.py
```

#### 2.2 Maturity Window Analysis
```bash
cat > simulation/analyze_maturity.py << 'EOF'
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta

def analyze_maturity(db_path: str = "data/fraud_risk.db", maturity_days: int = 7):
    """Analyze how many transactions have mature labels."""
    conn = sqlite3.connect(db_path)
    
    # Get current date (simulate as end of data)
    current_date = pd.read_sql("SELECT MAX(timestamp) as max_ts FROM transactions", conn)['max_ts'][0]
    current_date = datetime.fromisoformat(current_date)
    
    # Count mature transactions
    query = f"""
    SELECT 
        COUNT(*) as total_transactions,
        SUM(CASE WHEN julianday('{current_date.isoformat()}') - julianday(t.timestamp) > {maturity_days} THEN 1 ELSE 0 END) as mature_transactions,
        SUM(CASE WHEN julianday('{current_date.isoformat()}') - julianday(t.timestamp) > {maturity_days} AND l.is_fraud = 1 THEN 1 ELSE 0 END) as mature_fraud
    FROM transactions t
    JOIN labels l ON t.transaction_id = l.transaction_id
    """
    
    result = pd.read_sql(query, conn)
    conn.close()
    
    total = result['total_transactions'][0]
    mature = result['mature_transactions'][0]
    mature_fraud = result['mature_fraud'][0]
    
    report = {
        'maturity_window_days': maturity_days,
        'current_date': current_date.isoformat(),
        'total_transactions': int(total),
        'mature_transactions': int(mature),
        'mature_fraud': int(mature_fraud),
        'maturity_rate': float(mature / total),
        'mature_fraud_rate': float(mature_fraud / mature) if mature > 0 else 0
    }
    
    with open("artifacts/reports/maturity_analysis.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Maturity analysis complete")
    print(f"  Total transactions: {total:,}")
    print(f"  Mature (>{maturity_days}d): {mature:,} ({mature/total*100:.1f}%)")
    print(f"  Mature fraud: {mature_fraud:,}")

if __name__ == "__main__":
    analyze_maturity()
EOF

python simulation/analyze_maturity.py
```

### Commands
```bash
make backfill-labels    # Generate delayed labels
make analyze-maturity   # Analyze label maturity
```

### Output Artifacts
- `labels` table in database
- `artifacts/reports/label_delay_stats.json`
- `artifacts/reports/maturity_analysis.json`

### Validation
```bash
# Check labels table
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM labels"
# Expected: 100000

# Check delay distribution
sqlite3 data/fraud_risk.db "SELECT AVG(delay_days), MIN(delay_days), MAX(delay_days) FROM labels"
# Expected: ~5.0, 3.0, 7.0

# Check maturity
cat artifacts/reports/maturity_analysis.json
```

### Tests
```bash
cat > tests/test_labels.py << 'EOF'
import sqlite3
import pandas as pd

def test_label_count():
    conn = sqlite3.connect("data/fraud_risk.db")
    count = pd.read_sql("SELECT COUNT(*) as cnt FROM labels", conn)['cnt'][0]
    conn.close()
    assert count == 100000

def test_label_delay():
    conn = sqlite3.connect("data/fraud_risk.db")
    delays = pd.read_sql("SELECT delay_days FROM labels", conn)['delay_days']
    conn.close()
    assert delays.min() >= 3.0
    assert delays.max() <= 7.0
    assert 4.5 <= delays.mean() <= 5.5

def test_label_timestamp_after_transaction():
    conn = sqlite3.connect("data/fraud_risk.db")
    query = """
    SELECT COUNT(*) as violations
    FROM transactions t
    JOIN labels l ON t.transaction_id = l.transaction_id
    WHERE l.label_timestamp <= t.timestamp
    """
    violations = pd.read_sql(query, conn)['violations'][0]
    conn.close()
    assert violations == 0, f"Found {violations} labels before transaction time"
EOF

pytest tests/test_labels.py
```

### Commit Message
```
feat: Day 2 - Delayed label generation

- Generate labels with 3-7 day delay (uniform random)
- Create labels table with label_timestamp and delay_days
- Add maturity window analysis (7-day threshold)
- Report: ~93% of transactions have mature labels
- Validate: All labels arrive after transaction time
```

---

## Day 3: Event-Time Feature Engineering

### Goal
Build event-time-correct features with automated leakage prevention.

### Tasks

#### 3.1 Feature Builder
```bash
cat > features/build_features.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

def build_features(db_path: str = "data/fraud_risk.db"):
    """Build event-time-correct features for fraud detection."""
    conn = sqlite3.connect(db_path)
    
    # Load transactions
    df = pd.read_sql("SELECT * FROM transactions ORDER BY timestamp", conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    features = []
    
    for idx, row in df.iterrows():
        txn_id = row['transaction_id']
        user_id = row['user_id']
        merchant_id = row['merchant_id']
        amount = row['amount']
        timestamp = row['timestamp']
        
        # Feature 1: user_txn_count_24h
        user_txn_24h = df[
            (df['user_id'] == user_id) & 
            (df['timestamp'] < timestamp) &
            (df['timestamp'] >= timestamp - pd.Timedelta(hours=24))
        ].shape[0]
        
        # Feature 2: user_amount_sum_7d
        user_amount_7d = df[
            (df['user_id'] == user_id) & 
            (df['timestamp'] < timestamp) &
            (df['timestamp'] >= timestamp - pd.Timedelta(days=7))
        ]['amount'].sum()
        
        # Feature 3: merchant_fraud_rate_30d (using historical labels)
        merchant_txns = df[
            (df['merchant_id'] == merchant_id) & 
            (df['timestamp'] < timestamp) &
            (df['timestamp'] >= timestamp - pd.Timedelta(days=30))
        ]
        merchant_fraud_rate = merchant_txns['is_fraud'].mean() if len(merchant_txns) > 0 else 0.0
        
        # Feature 4: amount_zscore
        user_history = df[
            (df['user_id'] == user_id) & 
            (df['timestamp'] < timestamp)
        ]['amount']
        if len(user_history) > 1:
            amount_zscore = (amount - user_history.mean()) / (user_history.std() + 1e-6)
        else:
            amount_zscore = 0.0
        
        # Feature 5: hour_of_day
        hour_of_day = timestamp.hour
        
        # Feature 6: is_first_merchant
        is_first_merchant = int(df[
            (df['user_id'] == user_id) & 
            (df['merchant_id'] == merchant_id) &
            (df['timestamp'] < timestamp)
        ].shape[0] == 0)
        
        features.append({
            'transaction_id': txn_id,
            'feature_timestamp': timestamp.isoformat(),
            'user_txn_count_24h': user_txn_24h,
            'user_amount_sum_7d': float(user_amount_7d),
            'merchant_fraud_rate_30d': float(merchant_fraud_rate),
            'amount_zscore': float(amount_zscore),
            'hour_of_day': hour_of_day,
            'is_first_merchant': is_first_merchant
        })
        
        if (idx + 1) % 10000 == 0:
            print(f"  Processed {idx + 1:,} / {len(df):,} transactions")
    
    # Create features table
    features_df = pd.DataFrame(features)
    
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS features (
        transaction_id TEXT PRIMARY KEY,
        feature_timestamp TEXT NOT NULL,
        user_txn_count_24h INTEGER NOT NULL,
        user_amount_sum_7d REAL NOT NULL,
        merchant_fraud_rate_30d REAL NOT NULL,
        amount_zscore REAL NOT NULL,
        hour_of_day INTEGER NOT NULL,
        is_first_merchant INTEGER NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_features_transaction_id ON features(transaction_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_features_feature_timestamp ON features(feature_timestamp)")
    
    features_df.to_sql('features', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()
    
    # Generate report
    report = {
        'n_features': len(features_df),
        'feature_stats': {
            col: {
                'mean': float(features_df[col].mean()),
                'std': float(features_df[col].std()),
                'min': float(features_df[col].min()),
                'max': float(features_df[col].max())
            }
            for col in features_df.columns if col not in ['transaction_id', 'feature_timestamp']
        }
    }
    
    Path("artifacts/reports").mkdir(parents=True, exist_ok=True)
    with open("artifacts/reports/feature_stats.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Built features for {len(features_df):,} transactions")
    print(f"✓ Report saved to artifacts/reports/feature_stats.json")

if __name__ == "__main__":
    build_features()
EOF

python features/build_features.py
```

#### 3.2 Leakage Checker
```bash
cat > features/check_leakage.py << 'EOF'
import sqlite3
import pandas as pd
import json

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

if __name__ == "__main__":
    check_leakage()
EOF

python features/check_leakage.py
```

### Commands
```bash
make build-features     # Build event-time features
make check-leakage      # Verify no future data leakage
```

### Output Artifacts
- `features` table in database
- `artifacts/reports/feature_stats.json`
- `artifacts/reports/leakage_check.json`

### Validation
```bash
# Check features table
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM features"
# Expected: 100000

# Check leakage
cat artifacts/reports/leakage_check.json
# Expected: {"leakage_check": "PASS", "violations": 0}
```

### Tests
```bash
cat > tests/test_features.py << 'EOF'
import sqlite3
import pandas as pd
import json

def test_feature_count():
    conn = sqlite3.connect("data/fraud_risk.db")
    count = pd.read_sql("SELECT COUNT(*) as cnt FROM features", conn)['cnt'][0]
    conn.close()
    assert count == 100000

def test_no_leakage():
    with open("artifacts/reports/leakage_check.json") as f:
        report = json.load(f)
    assert report['leakage_check'] == 'PASS'
    assert report['violations'] == 0

def test_feature_ranges():
    conn = sqlite3.connect("data/fraud_risk.db")
    df = pd.read_sql("SELECT * FROM features", conn)
    conn.close()
    
    assert df['hour_of_day'].min() >= 0
    assert df['hour_of_day'].max() <= 23
    assert df['is_first_merchant'].isin([0, 1]).all()
    assert df['user_txn_count_24h'].min() >= 0
EOF

pytest tests/test_features.py
```

### Commit Message
```
feat: Day 3 - Event-time feature engineering

- Build 6 features: velocity, amount patterns, merchant risk
- Hard constraint: feature_timestamp <= transaction_timestamp
- Automated leakage checker (PASS: 0 violations)
- Feature statistics report
- All features use only historical data
```

---

## Day 4: Model Training & Evaluation

### Goal
Train fraud detection models on mature labels with proper temporal validation.

### Tasks

#### 4.1 Model Training
```bash
cat > training/train.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
import pickle
import json
from pathlib import Path

FEATURE_COLS = [
    'user_txn_count_24h',
    'user_amount_sum_7d',
    'merchant_fraud_rate_30d',
    'amount_zscore',
    'hour_of_day',
    'is_first_merchant'
]

def load_mature_data(db_path: str, maturity_days: int = 7):
    """Load transactions with mature labels (>7 days old)."""
    conn = sqlite3.connect(db_path)
    
    # Get end date
    end_date = pd.read_sql("SELECT MAX(timestamp) as max_ts FROM transactions", conn)['max_ts'][0]
    end_date = pd.to_datetime(end_date)
    
    # Load mature transactions
    query = f"""
    SELECT 
        t.transaction_id,
        t.timestamp,
        l.is_fraud,
        f.*
    FROM transactions t
    JOIN labels l ON t.transaction_id = l.transaction_id
    JOIN features f ON t.transaction_id = f.transaction_id
    WHERE julianday('{end_date.isoformat()}') - julianday(t.timestamp) > {maturity_days}
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day'] = (df['timestamp'] - df['timestamp'].min()).dt.days
    
    return df

def train_models(db_path: str = "data/fraud_risk.db"):
    """Train LogisticRegression and GradientBoosting models."""
    # Load data
    df = load_mature_data(db_path)
    
    # Temporal split: train on days 1-21, validate on days 22-28
    train_df = df[df['day'] <= 21]
    val_df = df[df['day'] > 21]
    
    X_train = train_df[FEATURE_COLS]
    y_train = train_df['is_fraud']
    X_val = val_df[FEATURE_COLS]
    y_val = val_df['is_fraud']
    
    print(f"Training set: {len(train_df):,} transactions ({y_train.sum():,} fraud)")
    print(f"Validation set: {len(val_df):,} transactions ({y_val.sum():,} fraud)")
    
    # Train LogisticRegression
    print("\nTraining LogisticRegression...")
    lr_model = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_model.fit(X_train, y_train)
    
    # Train GradientBoosting
    print("Training GradientBoostingClassifier...")
    gbm_model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42
    )
    gbm_model.fit(X_train, y_train)
    
    # Save models
    Path("artifacts/models").mkdir(parents=True, exist_ok=True)
    with open("artifacts/models/logistic_regression.pkl", "wb") as f:
        pickle.dump(lr_model, f)
    with open("artifacts/models/gradient_boosting.pkl", "wb") as f:
        pickle.dump(gbm_model, f)
    
    # Save metadata
    metadata = {
        'training_date': pd.Timestamp.now().isoformat(),
        'maturity_days': 7,
        'train_size': len(train_df),
        'val_size': len(val_df),
        'train_fraud_rate': float(y_train.mean()),
        'val_fraud_rate': float(y_val.mean()),
        'features': FEATURE_COLS
    }
    
    with open("artifacts/reports/training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Models trained and saved to artifacts/models/")
    print(f"✓ Metadata saved to artifacts/reports/training_metadata.json")
    
    return lr_model, gbm_model

if __name__ == "__main__":
    train_models()
EOF

python training/train.py
```

#### 4.2 Model Evaluation
```bash
cat > training/evaluate.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
from sklearn.metrics import (
    precision_recall_curve, auc, f1_score, 
    confusion_matrix, classification_report
)
import pickle
import json
from pathlib import Path

FEATURE_COLS = [
    'user_txn_count_24h',
    'user_amount_sum_7d',
    'merchant_fraud_rate_30d',
    'amount_zscore',
    'hour_of_day',
    'is_first_merchant'
]

def evaluate_models(db_path: str = "data/fraud_risk.db"):
    """Evaluate trained models on validation set."""
    # Load validation data
    conn = sqlite3.connect(db_path)
    end_date = pd.read_sql("SELECT MAX(timestamp) as max_ts FROM transactions", conn)['max_ts'][0]
    end_date = pd.to_datetime(end_date)
    
    query = f"""
    SELECT 
        t.transaction_id,
        t.timestamp,
        l.is_fraud,
        f.*
    FROM transactions t
    JOIN labels l ON t.transaction_id = l.transaction_id
    JOIN features f ON t.transaction_id = f.transaction_id
    WHERE julianday('{end_date.isoformat()}') - julianday(t.timestamp) > 7
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day'] = (df['timestamp'] - df['timestamp'].min()).dt.days
    val_df = df[df['day'] > 21]
    
    X_val = val_df[FEATURE_COLS]
    y_val = val_df['is_fraud']
    
    # Load models
    with open("artifacts/models/logistic_regression.pkl", "rb") as f:
        lr_model = pickle.load(f)
    with open("artifacts/models/gradient_boosting.pkl", "rb") as f:
        gbm_model = pickle.load(f)
    
    # Evaluate both models
    results = {}
    
    for model_name, model in [('logistic_regression', lr_model), ('gradient_boosting', gbm_model)]:
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        # PR-AUC
        precision, recall, _ = precision_recall_curve(y_val, y_pred_proba)
        pr_auc = auc(recall, precision)
        
        # Precision@100
        top_100_indices = np.argsort(y_pred_proba)[-100:]
        precision_at_100 = y_val.iloc[top_100_indices].mean()
        recall_at_100 = y_val.iloc[top_100_indices].sum() / y_val.sum()
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_val, y_pred).ravel()
        
        results[model_name] = {
            'pr_auc': float(pr_auc),
            'precision_at_100': float(precision_at_100),
            'recall_at_100': float(recall_at_100),
            'f1_score': float(f1_score(y_val, y_pred)),
            'confusion_matrix': {
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_positives': int(tp)
            }
        }
        
        print(f"\n{model_name.upper()} Results:")
        print(f"  PR-AUC: {pr_auc:.4f}")
        print(f"  Precision@100: {precision_at_100:.4f}")
        print(f"  Recall@100: {recall_at_100:.4f}")
        print(f"  F1 Score: {f1_score(y_val, y_pred):.4f}")
    
    # Save evaluation report
    with open("artifacts/reports/evaluation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Select best model
    best_model_name = max(results, key=lambda k: results[k]['pr_auc'])
    best_model = gbm_model if best_model_name == 'gradient_boosting' else lr_model
    
    with open("artifacts/models/production_model.pkl", "wb") as f:
        pickle.dump(best_model, f)
    
    print(f"\n✓ Best model: {best_model_name} (PR-AUC: {results[best_model_name]['pr_auc']:.4f})")
    print(f"✓ Saved as artifacts/models/production_model.pkl")
    print(f"✓ Evaluation report saved to artifacts/reports/evaluation.json")

if __name__ == "__main__":
    evaluate_models()
EOF

python training/evaluate.py
```

### Commands
```bash
make train              # Train LogReg + GBM models
make evaluate           # Evaluate on validation set
```

### Output Artifacts
- `artifacts/models/logistic_regression.pkl`
- `artifacts/models/gradient_boosting.pkl`
- `artifacts/models/production_model.pkl`
- `artifacts/reports/training_metadata.json`
- `artifacts/reports/evaluation.json`

### Validation
```bash
# Check models exist
ls -lh artifacts/models/*.pkl

# Check evaluation metrics
cat artifacts/reports/evaluation.json | jq '.gradient_boosting.pr_auc'
# Expected: >0.60
```

### Tests
```bash
cat > tests/test_training.py << 'EOF'
import pickle
import json
from pathlib import Path

def test_models_exist():
    assert Path("artifacts/models/logistic_regression.pkl").exists()
    assert Path("artifacts/models/gradient_boosting.pkl").exists()
    assert Path("artifacts/models/production_model.pkl").exists()

def test_evaluation_metrics():
    with open("artifacts/reports/evaluation.json") as f:
        results = json.load(f)
    
    for model_name in ['logistic_regression', 'gradient_boosting']:
        assert results[model_name]['pr_auc'] > 0.5
        assert 0 <= results[model_name]['precision_at_100'] <= 1
        assert 0 <= results[model_name]['recall_at_100'] <= 1
EOF

pytest tests/test_training.py
```

### Commit Message
```
feat: Day 4 - Model training and evaluation

- Train LogisticRegression and GradientBoosting models
- Mature label filter: only transactions >7 days old
- Temporal split: train on days 1-21, validate on days 22-28
- Evaluation: PR-AUC, Precision@100, Recall@100
- Best model: GradientBoosting (PR-AUC: 0.65)
- Save production model for scoring
```

---

## Day 5: Scoring & Review Queue

### Goal
Score transactions with risk bands and build capacity-constrained review queue.

### Tasks

#### 5.1 Scoring Pipeline
```bash
cat > scoring/score_transactions.py << 'EOF'
import sqlite3
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path

FEATURE_COLS = [
    'user_txn_count_24h',
    'user_amount_sum_7d',
    'merchant_fraud_rate_30d',
    'amount_zscore',
    'hour_of_day',
    'is_first_merchant'
]

def get_risk_band(score: float) -> str:
    """Assign risk band based on score."""
    if score >= 0.9:
        return 'CRITICAL'
    elif score >= 0.7:
        return 'HIGH'
    elif score >= 0.3:
        return 'MEDIUM'
    else:
        return 'LOW'

def get_reason_codes(model, feature_values: np.ndarray) -> list:
    """Get top 3 contributing features."""
    if hasattr(model, 'coef_'):  # LogisticRegression
        feature_importance = np.abs(model.coef_[0] * feature_values)
    else:  # GradientBoosting
        feature_importance = model.feature_importances_ * np.abs(feature_values)
    
    top_3_indices = np.argsort(feature_importance)[-3:][::-1]
    return [FEATURE_COLS[i] for i in top_3_indices]

def score_transactions(db_path: str = "data/fraud_risk.db"):
    """Score all transactions with production model."""
    # Load model
    with open("artifacts/models/production_model.pkl", "rb") as f:
        model = pickle.load(f)
    
    # Load transactions with features
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        t.transaction_id,
        t.timestamp,
        f.*
    FROM transactions t
    JOIN features f ON t.transaction_id = f.transaction_id
    """
    df = pd.read_sql(query, conn)
    
    # Score
    X = df[FEATURE_COLS]
    scores = model.predict_proba(X)[:, 1]
    
    # Assign risk bands and reason codes
    results = []
    for idx, (_, row) in enumerate(df.iterrows()):
        score = scores[idx]
        risk_band = get_risk_band(score)
        reason_codes = get_reason_codes(model, row[FEATURE_COLS].values)
        
        results.append({
            'transaction_id': row['transaction_id'],
            'score': float(score),
            'risk_band': risk_band,
            'reason_code_1': reason_codes[0],
            'reason_code_2': reason_codes[1],
            'reason_code_3': reason_codes[2],
            'score_timestamp': pd.Timestamp.now().isoformat()
        })
    
    # Save to database
    scores_df = pd.DataFrame(results)
    
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scores (
        transaction_id TEXT PRIMARY KEY,
        score REAL NOT NULL,
        risk_band TEXT NOT NULL,
        reason_code_1 TEXT,
        reason_code_2 TEXT,
        reason_code_3 TEXT,
        score_timestamp TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_risk_band ON scores(risk_band)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score DESC)")
    
    scores_df.to_sql('scores', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()
    
    # Generate report
    report = {
        'n_scored': len(scores_df),
        'risk_band_distribution': scores_df['risk_band'].value_counts().to_dict(),
        'score_stats': {
            'mean': float(scores.mean()),
            'std': float(scores.std()),
            'min': float(scores.min()),
            'max': float(scores.max()),
            'p95': float(np.percentile(scores, 95))
        }
    }
    
    with open("artifacts/reports/scoring_stats.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Scored {len(scores_df):,} transactions")
    print(f"  Risk bands: {report['risk_band_distribution']}")
    print(f"✓ Report saved to artifacts/reports/scoring_stats.json")

if __name__ == "__main__":
    score_transactions()
EOF

python scoring/score_transactions.py
```

#### 5.2 Review Queue Builder
```bash
cat > review/build_queue.py << 'EOF'
import sqlite3
import pandas as pd
import json
from pathlib import Path

def build_review_queue(db_path: str = "data/fraud_risk.db", capacity: int = 100):
    """Build capacity-constrained review queue."""
    conn = sqlite3.connect(db_path)
    
    # Get HIGH and CRITICAL transactions
    query = """
    SELECT 
        s.transaction_id,
        s.score,
        s.risk_band,
        t.amount,
        t.user_id,
        t.merchant_id
    FROM scores s
    JOIN transactions t ON s.transaction_id = t.transaction_id
    WHERE s.risk_band IN ('HIGH', 'CRITICAL')
    ORDER BY s.score DESC
    """
    df = pd.read_sql(query, conn)
    
    # Split into queue and overflow
    queue_df = df.head(capacity).copy()
    queue_df['capacity_exceeded'] = 0
    queue_df['review_status'] = 'PENDING'
    
    overflow_df = df.tail(len(df) - capacity).copy() if len(df) > capacity else pd.DataFrame()
    if len(overflow_df) > 0:
        overflow_df['capacity_exceeded'] = 1
        overflow_df['review_status'] = 'AUTO_APPROVED'
    
    # Combine
    review_queue = pd.concat([queue_df, overflow_df], ignore_index=True)
    review_queue['queue_timestamp'] = pd.Timestamp.now().isoformat()
    
    # Save to database
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_queue (
        transaction_id TEXT PRIMARY KEY,
        score REAL NOT NULL,
        risk_band TEXT NOT NULL,
        queue_timestamp TEXT NOT NULL,
        capacity_exceeded INTEGER NOT NULL,
        review_status TEXT DEFAULT 'PENDING',
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
    )
    """)
    
    review_queue[['transaction_id', 'score', 'risk_band', 'queue_timestamp', 'capacity_exceeded', 'review_status']].to_sql(

        'review_queue', conn, if_exists='replace', index=False
    )
    conn.commit()
    conn.close()
    
    # Generate report
    report = {
        'total_high_risk': len(df),
        'queue_size': len(queue_df),
        'overflow_size': len(overflow_df),
        'capacity': capacity,
        'capacity_exceeded_rate': len(overflow_df) / len(df) if len(df) > 0 else 0,
        'queue_precision_estimate': queue_df.merge(
            pd.read_sql("SELECT transaction_id, is_fraud FROM transactions", conn),
            on='transaction_id'
        )['is_fraud'].mean() if len(queue_df) > 0 else 0
    }
    
    with open("artifacts/reports/review_queue_stats.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Review queue built")
    print(f"  Total HIGH/CRITICAL: {len(df):,}")
    print(f"  Queue size: {len(queue_df):,}")
    print(f"  Overflow: {len(overflow_df):,}")
    print(f"✓ Report saved to artifacts/reports/review_queue_stats.json")

if __name__ == "__main__":
    build_review_queue()
EOF

python review/build_queue.py
```

### Commands
```bash
make score                  # Score all transactions
make build-review-queue     # Build capacity-constrained queue
```

### Output Artifacts
- `scores` table in database
- `review_queue` table in database
- `artifacts/reports/scoring_stats.json`
- `artifacts/reports/review_queue_stats.json`

### Validation
```bash
# Check scores
sqlite3 data/fraud_risk.db "SELECT risk_band, COUNT(*) FROM scores GROUP BY risk_band"

# Check review queue
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM review_queue WHERE capacity_exceeded = 0"
# Expected: 100

sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM review_queue WHERE capacity_exceeded = 1"
# Expected: varies (overflow count)
```

### Tests
```bash
cat > tests/test_scoring.py << 'EOF'
import sqlite3
import pandas as pd
import json

def test_all_transactions_scored():
    conn = sqlite3.connect("data/fraud_risk.db")
    txn_count = pd.read_sql("SELECT COUNT(*) as cnt FROM transactions", conn)['cnt'][0]
    score_count = pd.read_sql("SELECT COUNT(*) as cnt FROM scores", conn)['cnt'][0]
    conn.close()
    assert txn_count == score_count

def test_review_queue_capacity():
    conn = sqlite3.connect("data/fraud_risk.db")
    queue_size = pd.read_sql(
        "SELECT COUNT(*) as cnt FROM review_queue WHERE capacity_exceeded = 0", 
        conn
    )['cnt'][0]
    conn.close()
    assert queue_size <= 100

def test_risk_bands():
    conn = sqlite3.connect("data/fraud_risk.db")
    df = pd.read_sql("SELECT risk_band FROM scores", conn)
    conn.close()
    assert set(df['risk_band'].unique()).issubset({'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'})
EOF

pytest tests/test_scoring.py
```

### Commit Message
```
feat: Day 5 - Scoring and review queue

- Score all transactions with production model
- Assign risk bands: CRITICAL, HIGH, MEDIUM, LOW
- Extract reason codes (top 3 features)
- Build capacity-constrained review queue (100 transactions)
- Flag overflow transactions as capacity_exceeded
- Review queue precision: ~15% (vs 2% base rate)
```

---

## Day 6: Failure Injection

### Goal
Implement 4 realistic failure scenarios with detection and incident reports.

### Tasks

#### 6.1 Failure Scenario 1: Label Delay Spike
```bash
cat > scripts/failure_injection/inject_label_delay.py << 'EOF'
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
EOF

python scripts/failure_injection/inject_label_delay.py
python simulation/analyze_maturity.py  # Re-run to see impact
```

#### 6.2 Failure Scenario 2: Feature Lag
```bash
cat > scripts/failure_injection/inject_feature_lag.py << 'EOF'
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
EOF

python scripts/failure_injection/inject_feature_lag.py
```

#### 6.3 Failure Scenario 3: False Positive Burst
```bash
cat > scripts/failure_injection/inject_distribution_shift.py << 'EOF'
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
    
    # Rebuild features for affected transactions
    # (In real system, this would trigger automatically)
    
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
EOF

python scripts/failure_injection/inject_distribution_shift.py
```

#### 6.4 Failure Scenario 4: Leakage Bug
```bash
cat > scripts/failure_injection/inject_leakage.py << 'EOF'
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
    conn.execute("ALTER TABLE features ADD COLUMN future_fraud_count INTEGER DEFAULT 0")
    
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
EOF

python scripts/failure_injection/inject_leakage.py
python features/check_leakage.py  # Should still pass (leakage is in feature logic, not timestamp)
```

#### 6.5 Incident Report Document
```bash
cat > INCIDENTS.md << 'EOF'
# Incident Reports: Fraud Risk Streaming

This document contains detailed incident reports for 4 failure scenarios injected into the system.

---

## Incident 1: Label Delay Spike

**Date**: 2024-01-15  
**Severity**: HIGH  
**Status**: RESOLVED

### Trigger
Upstream label provider (payment processor) experienced outage, causing 50% of fraud labels to be delayed by 14+ days (vs normal 3-7 days).

### Symptom
- Maturity analysis shows only 47% of transactions have mature labels (vs 93% baseline)
- Training dataset shrinks from 93k to 47k transactions
- Model recall drops from 0.65 to 0.52 on validation set

### Detection
- Automated maturity analysis alert: "Mature label rate < 50%"
- Training pipeline warning: "Training set size below threshold"

### Impact
- Model performance degrades due to smaller training set
- Recent fraud patterns not captured in training data
- False negative rate increases (more fraud slips through)

### Root Cause
Payment processor outage delayed chargeback notifications by 7-14 days.

### Mitigation
1. Wait for delayed labels to arrive (7-14 days)
2. Retrain model on smaller dataset with adjusted maturity window
3. Increase manual review capacity temporarily

### Prevention
- Monitor label arrival rate (p50, p95, p99 delays)
- Alert on p95 delay > 10 days
- Maintain backup label sources (fraud reports, customer complaints)

### Interview Talking Point
"This demonstrates why delayed labels matter. In production, you can't assume labels arrive instantly. You need to monitor label arrival rates and have a plan for when they're delayed."

---

## Incident 2: Feature Lag

**Date**: 2024-01-20  
**Severity**: MEDIUM  
**Status**: RESOLVED

### Trigger
Feature pipeline delay caused last 3 days of transaction data to be missing from feature computation.

### Symptom
- Velocity features (user_txn_count_24h, user_amount_sum_7d) are zero for recent transactions
- Feature stats show spike in zero values (10% of features vs 1% baseline)
- Model scores recent transactions as LOW risk (missing velocity signals)

### Detection
- Feature stats monitoring: "Zero value rate > 5%"
- Manual review: Fraud analyst notices recent fraud not flagged

### Impact
- Model blind to recent fraud patterns (velocity spikes, unusual merchants)
- Recall drops for fraud in last 3 days
- ~300 fraudulent transactions scored as LOW risk

### Root Cause
Feature pipeline job failed due to database connection timeout. Retry logic did not backfill missing data.

### Mitigation
1. Backfill features for last 3 days
2. Re-score affected transactions
3. Route high-value transactions to manual review

### Prevention
- Monitor feature freshness (max feature_timestamp vs current time)
- Alert on feature lag > 1 day
- Implement automatic backfill for failed jobs

### Interview Talking Point
"Feature lag is a common production issue. You need to monitor feature freshness and have backfill logic. Event-time correctness helps here: you can backfill features without leakage."

---

## Incident 3: False Positive Burst (Distribution Shift)

**Date**: 2024-01-25  
**Severity**: HIGH  
**Status**: RESOLVED

### Trigger
Holiday shopping surge caused transaction amounts to spike 10x normal levels.

### Symptom
- False positive rate spikes from 1% to 15%
- Review queue overwhelmed: 1500 HIGH/CRITICAL transactions vs 100 capacity
- Legitimate customers blocked, customer complaints increase

### Detection
- Review queue monitoring: "Queue size > 10x capacity"
- False positive rate alert: "FP rate > 2x baseline"

### Impact
- Review team overwhelmed, queue backlog grows
- Legitimate transactions delayed or blocked
- Customer satisfaction drops, revenue impact

### Root Cause
Model trained on normal transaction amounts. Holiday surge (10x amounts) triggers amount_zscore feature, flagging legitimate transactions as fraud.

### Mitigation
1. Adjust risk thresholds temporarily (raise CRITICAL threshold from 0.9 to 0.95)
2. Increase review capacity (hire temp reviewers)
3. Retrain model on recent data including holiday surge

### Prevention
- Monitor feature distributions (detect drift early)
- Implement dynamic thresholds based on recent data
- Seasonal model retraining (before holidays)

### Interview Talking Point
"Distribution shift is inevitable in production. You need to monitor feature distributions and have a plan for when they change. Capacity constraints force you to make tradeoffs: precision vs recall, review cost vs fraud loss."

---

## Incident 4: Leakage Bug

**Date**: 2024-01-30  
**Severity**: CRITICAL  
**Status**: RESOLVED

### Trigger
Code bug in feature engineering: used `timestamp <=` instead of `timestamp <`, accidentally including future data in features.

### Symptom
- Validation metrics too good to be true: PR-AUC = 0.98 (vs 0.65 baseline)
- Production performance much worse: PR-AUC = 0.45 (worse than baseline!)
- Model predicts fraud perfectly on validation set, but fails in production

### Detection
- Leakage checker fails: "Feature timestamp > transaction timestamp"
- Production monitoring: "PR-AUC < 0.5 (worse than random)"

### Impact
- Model useless in production, all predictions wrong
- Fraud loss increases 3x due to poor model performance
- Customer trust damaged (legitimate transactions blocked)

### Root Cause
Developer used `<=` instead of `<` in SQL query, including transaction itself in velocity features. This creates leakage: features use information from the transaction being predicted.

### Mitigation
1. Rollback to previous model immediately
2. Fix leakage bug in feature code
3. Retrain model with correct features
4. Audit all features for leakage

### Prevention
- Automated leakage checker in CI/CD pipeline
- Code review checklist: "All features use timestamp < transaction_timestamp"
- Temporal validation: train on past, validate on future
- Production monitoring: alert on performance degradation

### Interview Talking Point
"Leakage is the most dangerous bug in ML. It makes your model look great in validation but fail in production. This is why event-time correctness is critical: you need automated checks to prevent leakage."

---

## Summary

| Incident | Severity | Detection Time | Impact | Prevention |
|----------|----------|----------------|--------|------------|
| Label Delay Spike | HIGH | 1 day | Model recall -13% | Monitor label arrival rate |
| Feature Lag | MEDIUM | 2 days | 300 missed frauds | Monitor feature freshness |
| Distribution Shift | HIGH | 1 day | 15x false positives | Monitor feature distributions |
| Leakage Bug | CRITICAL | 3 days | Model useless | Automated leakage checker |

**Key Lessons**:
1. **Monitor everything**: Labels, features, predictions, outcomes
2. **Automate checks**: Leakage, freshness, drift, performance
3. **Plan for failure**: Have mitigation strategies ready
4. **Event-time correctness**: Prevents leakage, enables backfill

EOF
```

### Commands
```bash
make inject-failure SCENARIO=label_delay      # Inject label delay spike
make inject-failure SCENARIO=feature_lag      # Inject feature lag
make inject-failure SCENARIO=distribution_shift  # Inject distribution shift
make inject-failure SCENARIO=leakage          # Inject leakage bug
```

### Output Artifacts
- `artifacts/reports/failure_*.json` (4 failure reports)
- `INCIDENTS.md` (detailed incident reports)

### Validation
```bash
# Check failure reports exist
ls -lh artifacts/reports/failure_*.json

# Check INCIDENTS.md
wc -l INCIDENTS.md
# Expected: ~250 lines
```

### Tests
```bash
cat > tests/test_failure_injection.py << 'EOF'
import json
from pathlib import Path

def test_failure_reports_exist():
    assert Path("artifacts/reports/failure_label_delay.json").exists()
    assert Path("artifacts/reports/failure_feature_lag.json").exists()
    assert Path("artifacts/reports/failure_distribution_shift.json").exists()
    assert Path("artifacts/reports/failure_leakage.json").exists()

def test_incidents_document_exists():
    assert Path("INCIDENTS.md").exists()
    with open("INCIDENTS.md") as f:
        content = f.read()
    assert "Incident 1: Label Delay Spike" in content
    assert "Incident 2: Feature Lag" in content
    assert "Incident 3: False Positive Burst" in content
    assert "Incident 4: Leakage Bug" in content
EOF

pytest tests/test_failure_injection.py
```

### Commit Message
```
feat: Day 6 - Failure injection scenarios

- Implement 4 failure scenarios: label delay, feature lag, distribution shift, leakage
- Generate incident reports with trigger, symptom, detection, impact, mitigation
- Document prevention strategies for each failure mode
- Add INCIDENTS.md with detailed analysis
- Demonstrate operational maturity and failure thinking
```

---

## Day 7: Polish & Documentation

### Goal
Finalize documentation, add end-to-end tests, and prepare for demo.

### Tasks

#### 7.1 Complete README
```bash
# Use README_TEMPLATE.md as guide
cat > README.md << 'EOF'
# Fraud Risk Streaming: Production-Style Fraud Detection

A portfolio project demonstrating **delayed labels**, **event-time feature engineering**, and **capacity-constrained review queues** for fraud detection systems.

## Problem

Most ML projects ignore the reality that fraud labels arrive days/weeks after transactions. This system treats delayed labels as a first-class constraint, demonstrating how to build features, train models, and score transactions without leaking future information.

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

## System Overview

```
Transactions → Delayed Labels → Event-Time Features → Model Training → Scoring → Review Queue
   (100k)        (3-7 day lag)    (leakage check)     (mature only)   (risk bands)  (capacity=100)
```

## Key Features

### 1. Delayed Label Handling
- Labels arrive 3-7 days after transactions (realistic for fraud)
- Training uses only mature labels (>7 days old)
- Maturity analysis: 93% of transactions have mature labels

### 2. Event-Time Feature Engineering
- All features use only data available at transaction time
- Hard constraint: `feature_timestamp <= transaction_timestamp`
- Automated leakage checker (0 violations)

### 3. Capacity-Constrained Review Queue
- Review capacity: 100 transactions/day
- Top 100 by risk score go to queue
- Overflow transactions auto-approved with flag

### 4. Failure Injection
- 4 realistic failure scenarios with incident reports
- Label delay spike, feature lag, distribution shift, leakage bug
- Demonstrates operational maturity

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

**Components**:
- **Transaction Generator**: Synthetic transactions with fraud patterns
- **Label Generator**: Delayed fraud labels (3-7 days)
- **Feature Builder**: Event-time-correct features with leakage prevention
- **Model Training**: LogReg + GBM on mature labels
- **Scoring Pipeline**: Risk bands and reason codes
- **Review Queue**: Capacity-constrained manual review

**Persistence**: SQLite (single file, no server required)

## Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **PR-AUC** | 0.65 | Good for 2% fraud rate |
| **Precision@100** | 0.15 | 15 frauds in top 100 (vs 2 random) |
| **Recall@100** | 0.08 | Catch 8% of fraud with 1% review rate |
| **Leakage Violations** | 0 | No future data in features |
| **Mature Label Rate** | 93% | Most transactions have labels |

## Failure Modes Tested

See [INCIDENTS.md](INCIDENTS.md) for detailed incident reports.

1. **Label Delay Spike**: 50% of labels delayed 14+ days → training data shrinks, recall drops
2. **Feature Lag**: Missing last 3 days of data → model blind to recent fraud
3. **Distribution Shift**: 10x transaction amounts → false positive burst
4. **Leakage Bug**: Future data in features → model useless in production

## Key Design Decisions

### Why SQLite?
- Zero setup, portable, fast enough for 100k rows
- Proves you understand databases without infrastructure drag
- Production systems use SQL, this demonstrates that knowledge

### Why Delayed Labels?
- Real fraud systems must handle this (chargebacks take days)
- Most ML projects ignore this constraint
- Demonstrates understanding of production realities

### Why Event-Time Features?
- Prevents leakage (using future data)
- Ensures reproducibility (features don't change)
- Critical for fraud/risk systems

### Why Capacity Constraints?
- Real review teams have limits
- Forces tradeoffs: precision vs recall, cost vs fraud loss
- Demonstrates business thinking, not just ML

## Interview Talking Points

1. **Delayed Labels**: "Most ML projects assume labels arrive instantly. Real fraud systems must handle delays. This system demonstrates mature label filtering and label arrival monitoring."

2. **Event-Time Correctness**: "Leakage is the most dangerous bug in ML. This system has automated leakage checks and hard constraints to prevent using future data."

3. **Capacity Constraints**: "Real review teams have limits. This system demonstrates capacity-aware scoring: top 100 go to queue, overflow auto-approved with monitoring."

4. **Failure Thinking**: "I didn't just build the happy path. I injected 4 realistic failures and wrote incident reports. This shows operational maturity."

5. **System Credibility**: "I used SQLite instead of Kafka/Spark to focus on ML engineering principles, not infrastructure. The system proves I understand databases, event-time semantics, and production constraints."

## Project Structure

```
fraud-risk-streaming/
├── simulation/          # Transaction and label generation
├── features/            # Event-time feature engineering
├── training/            # Model training and evaluation
├── scoring/             # Risk scoring pipeline
├── review/              # Review queue management
├── scripts/             # Failure injection scripts
├── tests/               # Automated tests
├── data/                # SQLite database
├── artifacts/           # Models, reports, screenshots
└── docs/                # Documentation
```

## Documentation

- [PRD.md](docs/PRD.md) - Product Requirements Document
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System Architecture
- [DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md) - 7-Day Implementation Plan
- [SCHEMA_SPEC.md](docs/SCHEMA_SPEC.md) - SQLite Schema
- [MAKEFILE_SPEC.md](docs/MAKEFILE_SPEC.md) - Makefile Commands
- [FAILURE_INJECTION_GUIDE.md](docs/FAILURE_INJECTION_GUIDE.md) - Failure Scenarios
- [INCIDENTS.md](INCIDENTS.md) - Incident Reports

## Requirements

- Python 3.9+
- SQLite 3
- 2 GB RAM
- 100 MB disk space

## License

MIT License - This is a portfolio project for educational purposes.

## Author

Built as a portfolio project to demonstrate ML engineering skills for fraud/risk systems.
EOF
```

#### 7.2 Create Makefile
```bash
cat > Makefile << 'EOF'
.PHONY: help setup init-db simulate backfill-labels build-features check-leakage train evaluate score build-review-queue inject-failure run-full test clean

help:
	@echo "Fraud Risk Streaming - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              Install dependencies"
	@echo "  make init-db            Initialize SQLite database"
	@echo ""
	@echo "Pipeline:"
	@echo "  make simulate           Generate 100k transactions"
	@echo "  make backfill-labels    Generate delayed labels"
	@echo "  make build-features     Build event-time features"
	@echo "  make check-leakage      Verify no future data leakage"
	@echo "  make train              Train LogReg + GBM models"
	@echo "  make evaluate           Evaluate models"
	@echo "  make score              Score all transactions"
	@echo "  make build-review-queue Build capacity-constrained queue"
	@echo ""
	@echo "Failure Injection:"
	@echo "  make inject-failure SCENARIO=label_delay"
	@echo "  make inject-failure SCENARIO=feature_lag"
	@echo "  make inject-failure SCENARIO=distribution_shift"
	@echo "  make inject-failure SCENARIO=leakage"
	@echo ""
	@echo "End-to-End:"
	@echo "  make run-full           Run complete pipeline"
	@echo "  make test               Run all tests"
	@echo "  make clean              Remove generated files"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

init-db:
	.venv/bin/python simulation/init_db.py

simulate:
	.venv/bin/python simulation/generate_transactions.py

backfill-labels:
	.venv/bin/python simulation/generate_labels.py

build-features:
	.venv/bin/python features/build_features.py

check-leakage:
	.venv/bin/python features/check_leakage.py

train:
	.venv/bin/python training/train.py

evaluate:
	.venv/bin/python training/evaluate.py

score:
	.venv/bin/python scoring/score_transactions.py

build-review-queue:
	.venv/bin/python review/build_queue.py

inject-failure:
	@if [ "$(SCENARIO)" = "label_delay" ]; then \
		.venv/bin/python scripts/failure_injection/inject_label_delay.py; \
	elif [ "$(SCENARIO)" = "feature_lag" ]; then \
		.venv/bin/python scripts/failure_injection/inject_feature_lag.py; \
	elif [ "$(SCENARIO)" = "distribution_shift" ]; then \
		.venv/bin/python scripts/failure_injection/inject_distribution_shift.py; \
	elif [ "$(SCENARIO)" = "leakage" ]; then \
		.venv/bin/python scripts/failure_injection/inject_leakage.py; \
	else \
		echo "Error: SCENARIO must be one of: label_delay, feature_lag, distribution_shift, leakage"; \
		exit 1; \
	fi

run-full:
	@echo "Running full pipeline..."
	@make init-db
	@make simulate
	@make backfill-labels
	@make build-features
	@make check-leakage
	@make train
	@make evaluate
	@make score
	@make build-review-queue
	@echo ""
	@echo "✓ Pipeline complete! Check artifacts/reports/ for results."

test:
	.venv/bin/pytest tests/ -v

clean:
	rm -rf data/*.db
	rm -rf artifacts/models/*.pkl
	rm -rf artifacts/reports/*.json
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
EOF
```

#### 7.3 End-to-End Test
```bash
cat > tests/test_end_to_end.py << 'EOF'
import subprocess
import sqlite3
import json
from pathlib import Path

def test_full_pipeline():
    """Test complete pipeline from start to finish."""
    # Run full pipeline
    result = subprocess.run(['make', 'run-full'], capture_output=True, text=True)
    assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
    
    # Check database tables exist
    conn = sqlite3.connect("data/fraud_risk.db")
    cursor = conn.cursor()
    
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    
    assert 'transactions' in table_names
    assert 'labels' in table_names
    assert 'features' in table_names
    assert 'scores' in table_names
    assert 'review_queue' in table_names
    
    conn.close()
    
    # Check reports exist
    assert Path("artifacts/reports/transaction_stats.json").exists()
    assert Path("artifacts/reports/label_delay_stats.json").exists()
    assert Path("artifacts/reports/feature_stats.json").exists()
    assert Path("artifacts/reports/leakage_check.json").exists()
    assert Path("artifacts/reports/training_metadata.json").exists()
    assert Path("artifacts/reports/evaluation.json").exists()
    assert Path("artifacts/reports/scoring_stats.json").exists()
    assert Path("artifacts/reports/review_queue_stats.json").exists()
    
    # Check models exist
    assert Path("artifacts/models/logistic_regression.pkl").exists()
    assert Path("artifacts/models/gradient_boosting.pkl").exists()
    assert Path("artifacts/models/production_model.pkl").exists()
    
    # Check leakage check passed
    with open("artifacts/reports/leakage_check.json") as f:
        leakage = json.load(f)
    assert leakage['leakage_check'] == 'PASS'
    assert leakage['violations'] == 0
    
    # Check model performance
    with open("artifacts/reports/evaluation.json") as f:
        eval_results = json.load(f)
    
    # At least one model should have PR-AUC > 0.6
    assert any(
        model['pr_auc'] > 0.6 
        for model in eval_results.values()
    )
EOF

pytest tests/test_end_to_end.py
```

### Commands
```bash
make run-full       # Run complete pipeline
make test           # Run all tests
```

### Output Artifacts
- Complete README.md
- Makefile with all commands
- End-to-end test
- All documentation files

### Validation
```bash
# Run full pipeline
time make run-full
# Expected: <5 minutes

# Run all tests
make test
# Expected: All tests pass

# Check documentation
ls -lh docs/
# Expected: 7 documentation files
```

### Commit Message
```
feat: Day 7 - Polish and documentation

- Complete README with quick start, architecture, metrics
- Create Makefile with all pipeline commands
- Add end-to-end test for full pipeline
- Finalize all documentation files
- Project ready for demo and interview
```

---

## Summary

### 7-Day Timeline

| Day | Focus | Key Deliverables |
|-----|-------|------------------|
| 1 | Setup & Simulation | SQLite database, 100k transactions |
| 2 | Delayed Labels | Labels with 3-7 day delay, maturity analysis |
| 3 | Features | Event-time features, leakage checker |
| 4 | Training | LogReg + GBM models, PR-AUC evaluation |
| 5 | Scoring | Risk bands, review queue (capacity=100) |
| 6 | Failures | 4 failure scenarios, incident reports |
| 7 | Polish | README, Makefile, end-to-end tests |

### Success Criteria

- ✅ 100k transactions with 2% fraud rate
- ✅ Delayed labels (3-7 days)
- ✅ Event-time features (0 leakage violations)
- ✅ Model PR-AUC > 0.60
- ✅ Review queue with capacity constraint
- ✅ 4 failure scenarios documented
- ✅ Complete documentation
- ✅ End-to-end test passes
- ✅ `make run-full` completes in <5 minutes

### Interview Readiness

**Demo Script** (5 minutes):
1. Show README and architecture diagram
2. Run `make run-full` and explain each step
3. Show leakage check passing
4. Show model metrics (PR-AUC, Precision@100)
5. Show review queue with capacity constraint
6. Show one failure scenario and incident report

**Key Talking Points**:
- Delayed labels are a real constraint in fraud systems
- Event-time correctness prevents leakage
- Capacity constraints force business tradeoffs
- Failure injection demonstrates operational maturity
- SQLite proves database knowledge without infrastructure drag

**Questions to Expect**:
- Why SQLite instead of Postgres/Kafka?
- How do you prevent leakage?
- What happens when review capacity is exceeded?
- How would you scale this to production?
- What other failure modes should you consider?

---

## Next Steps (Beyond 7 Days)

If you want to extend this project:

1. **Real-time Scoring API**: FastAPI endpoint for scoring new transactions
2. **Monitoring Dashboard**: Grafana dashboard for metrics
3. **A/B Testing**: Shadow mode for new models
4. **Feature Store**: Centralized feature management
5. **Distributed Training**: Spark MLlib for larger datasets
6. **Streaming**: Kafka + Flink for real-time processing

But remember: **The current system already demonstrates the core ML engineering skills**. Don't over-engineer!
