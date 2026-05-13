PYTHON := .venv/bin/python

.PHONY: help setup init-db simulate backfill-labels analyze-maturity build-features check-leakage train evaluate score review-queue clean

help:
	@echo "Fraud Risk Streaming - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup       Create virtual environment and install dependencies"
	@echo "  make init-db     Initialize SQLite database"
	@echo ""
	@echo "Pipeline:"
	@echo "  make simulate    Generate synthetic transactions"
	@echo "  make backfill-labels  Generate delayed fraud labels"
	@echo "  make analyze-maturity  Analyze label maturity"
	@echo "  make build-features  Build event-time features"
	@echo "  make check-leakage  Verify feature temporal correctness"
	@echo "  make train       Train baseline fraud models"
	@echo "  make evaluate    Evaluate models and save production artifact"
	@echo "  make score       Score transactions with production model"
	@echo "  make review-queue  Build capacity-constrained review queue"
	@echo "  make monitor     Run monitoring reports (drift + performance)"
	@echo ""
	@echo "Utility:"
	@echo "  make clean       Remove generated database and reports"

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

init-db:
	$(PYTHON) simulation/init_db.py

simulate:
	$(PYTHON) -m simulation.generate_transactions --num-transactions 100000 --fraud-rate 0.02

backfill-labels:
	$(PYTHON) -m simulation.generate_labels

analyze-maturity:
	$(PYTHON) -m simulation.analyze_maturity

build-features:
	$(PYTHON) -m features.build_features

check-leakage:
	$(PYTHON) -m features.check_leakage

train:
	$(PYTHON) -m training.train_model

evaluate:
	$(PYTHON) -m training.evaluate_model

score:
	$(PYTHON) -m scoring.score_transactions

review-queue:
	$(PYTHON) -m review.build_queue

monitor:
	$(PYTHON) -m monitoring.drift_detection
	$(PYTHON) -m monitoring.performance_tracker

clean:
	rm -f data/fraud_risk.db artifacts/reports/*.json artifacts/models/*.pkl
