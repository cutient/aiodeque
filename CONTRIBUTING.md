# Contributing

## Development Setup

```bash
# Clone the repository
git clone https://github.com/cutient/aiodeque.git
cd aiodeque

# Install dev dependencies (requires Python 3.11+)
uv sync --extra dev
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Running Benchmarks

```bash
uv run python benchmarks/run.py
```

## Pull Requests

1. Fork the repo and create a feature branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass
4. Submit a pull request

## Code Style

- Use type annotations
- Follow existing patterns in the codebase
- Keep async and sync APIs consistent
