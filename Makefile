# Makefile for advanced-analytics-ai

# Detect the correct Python command
ifeq ($(OS),Windows_NT)
    # Use the databricks-connect environment on Windows
    PYTHON := C:/Users/BYCLADM/AppData/Local/anaconda3/envs/databricks-connect/python.exe
    PYTEST := $(PYTHON) -m pytest
    PIP := $(PYTHON) -m pip
else
    PYTHON := python3
    PYTEST := pytest
    PIP := pip3
endif

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install-dev    - Install package with dev dependencies"
	@echo "  install-all    - Install all optional dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-fast      - Run tests excluding slow ones"
	@echo "  test-lp        - Run only linear programming tests"
	@echo "  test-ml        - Run only machine learning tests"
	@echo "  test-file      - Run specific test file (usage: make test-file FILE=tests/lp/test_demand.py)"
	@echo "  lint           - Run ruff linter"
	@echo "  clean          - Remove cache and build artifacts"

.PHONY: install-dev
install-dev:
	$(PIP) install -e ".[dev]"

.PHONY: install-all
install-all:
	$(PIP) install -e ".[dev,lp,ml,deep_learning,mcp]"

.PHONY: test
test:
	cd src && $(PYTEST) ../tests

.PHONY: test-fast
test-fast:
	cd src && $(PYTEST) ../tests -m "not slow"

.PHONY: test-lp
test-lp:
	$(PYTEST) tests/lp/

.PHONY: test-ml
test-ml:
	$(PYTEST) tests/ml/

.PHONY: test-file
test-file:
	$(PYTEST) $(FILE)

.PHONY: lint
lint:
	cd src && $(PYTHON) -m ruff check .

.PHONY: clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/ 2>/dev/null || true
