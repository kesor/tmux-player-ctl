.PHONY: test test-verbose test-file test-class test-function test-cov test-integration display help

# Run all unit tests (excludes integration tests)
test:
	@echo "Running unit tests..."
	@cd tests && python3 -m unittest discover -v

# Run all tests including integration tests
test-all:
	@echo "Running all tests..."
	@cd tests && python3 -m unittest discover -v && python3 -m unittest integration -v

# Run integration tests (requires actual playerctl)
test-integration:
	@echo "Running integration tests..."
	@cd tests && python3 -m unittest integration -v

# Run tests with coverage (requires nix develop)
test-cov:
	@echo "Running tests with coverage..."
	@nix develop --command bash -c "cd tests && python3 -m coverage run --source=.. -m unittest test_signals test_playerctl test_row test_composed test_utils -q && python3 -m coverage report --skip-covered"

# Run a specific test file
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=test_row"; \
		exit 1; \
	fi
	@echo "Running tests in $(FILE)..."
	@cd tests && python3 -m unittest $(FILE) -v

# Run a specific test class
test-class:
	@if [ -z "$(CLASS)" ]; then \
		echo "Usage: make test-class CLASS=TestRow"; \
		exit 1; \
	fi
	@echo "Running $(CLASS) tests..."
	@cd tests && python3 -m unittest $(CLASS) -v

# Run a specific test function
test-function:
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make test-function NAME=test_row.TestRow.test_row_one_slot"; \
		exit 1; \
	fi
	@echo "Running test: $(NAME)..."
	@cd tests && python3 -m unittest $(NAME) -v

# List all test classes
list:
	@echo "Available test files:"
	@ls tests/test_*.py | xargs -I{} basename {} .py | sort

# Run tests and stop on first failure
test-failfast:
	@echo "Running tests (failfast)..."
	@cd tests && python3 -m unittest discover -v -f
# Run the display demo
display:
	@echo "Running display demo..."
	@python3 test_display.py

# Default target
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  test              Run unit tests (excludes integration)"
	@echo "  test-all          Run all tests (including integration)"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-cov          Run tests with coverage report"
	@echo "  test-file FILE=x  Run tests in a specific file"
	@echo "  test-class CLASS=x Run tests in a specific class"
	@echo "  test-function NAME=x Run a specific test function"
	@echo "  test-failfast     Run tests, stop on first failure"
	@echo "  list              List all test classes"
	@echo ""
	@echo "Examples:"
	@echo "  make test"
	@echo "  make test-file FILE=TestRow"
	@echo "  make test-class CLASS=test_row.TestRow"
	@echo "  make test-function NAME=test_row.TestRow.test_row_one_slot"
	@echo "  make test-integration"
