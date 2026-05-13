PYTHON := .venv/bin/python

.PHONY: help setup init-db simulate backfill-labels analyze-maturity clean

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

clean:
	rm -f data/fraud_risk.db artifacts/reports/*.json
