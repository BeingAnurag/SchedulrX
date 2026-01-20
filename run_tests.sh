#!/bin/bash
# Run all tests with coverage

echo "Running test suite..."
pytest tests/ -v --tb=short

echo ""
echo "Running with coverage..."
pytest tests/ --cov=app --cov-report=html --cov-report=term

echo ""
echo "Coverage report generated in htmlcov/index.html"
