# Tests Directory

This directory contains test scripts and their outputs for the Product Categorizer application.

## Structure

```
tests/
├── README.md               # This file
├── .gitignore              # Ignores test outputs
├── __init__.py             # Makes tests a package
├── conftest.py             # Shared pytest fixtures
├── output/                 # Test output files (ignored by git)
│   └── .gitkeep
└── test_*.py               # Test scripts
```

## Purpose

- **Isolate test artifacts** from production code
- **Prevent test data pollution** in main output directory
- **Follow Python best practices** for test organization

## Usage

Run tests from the project root:

```bash
cd /path/to/categorizer

# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_ai_provider.py -v

# Run specific test
pytest tests/test_ai_provider.py::TestLoadCache::test_load_cache_file_not_exists -v
```

All test outputs will be written to `tests/output/` and automatically ignored by git.

## Test Scripts

- `test_ai_provider.py` - AI provider abstraction layer tests
- `test_claude_api.py` - Claude API integration tests (if applicable)
- `test_openai_api.py` - OpenAI API integration tests (if applicable)
- `test_taxonomy_search.py` - Shopify taxonomy search and caching tests
- `test_utils.py` - Utility functions tests (image counting, prompt generation)
- `test_config.py` - Configuration management tests
- `conftest.py` - Shared pytest fixtures for all tests

## Test Coverage

The project maintains high test coverage on critical modules:
- `src/utils.py` - 100% coverage
- `src/ai_provider.py` - 100% coverage
- `src/config.py` - 100% coverage
- `src/taxonomy_search.py` - ~89% coverage

Run `pytest tests/ --cov=src --cov-report=html` to generate a detailed coverage report in `htmlcov/index.html`.

## Fixtures

Shared test fixtures are defined in `conftest.py`:
- Sample product data
- Temporary files (config, taxonomy, cache)
- Mock API responses (Claude, OpenAI, Shopify)
- Utility fixtures (logging, status functions)

## Best Practices

✅ **Do:**
- Place all test scripts in `tests/` directory
- Write test outputs to `tests/output/`
- Use descriptive names: `test_feature_name.py`
- Document what each test does
- Use shared fixtures from `conftest.py`

❌ **Don't:**
- Commit test output files
- Mix test files with production code
- Write test outputs to main `output/` directory
- Skip testing edge cases
- Hardcode absolute paths in test scripts
