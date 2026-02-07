# Contributing to Network Pinger

Thank you for your interest in contributing to network-pinger! This document provides guidelines for contributing.

## How to Contribute

### Reporting Bugs

Before creating a bug report, please:
1. Check if the issue already exists in [GitHub Issues](https://github.com/meshlg/_pinger/issues)
2. Use the latest version to verify the bug still exists
3. Collect relevant information: Python version, OS, error messages

When creating a bug report, include:
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version)
- Any relevant logs or screenshots

### Suggesting Features

Feature requests are welcome! Please:
1. Check existing issues to avoid duplicates
2. Explain the use case and why it would be valuable
3. Be open to discussion and alternative approaches

### Code Contributions

#### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/meshlg/_pinger.git
cd _pinger

# Install Poetry if not already installed
pip install poetry

# Install dependencies
poetry install

# Activate the environment
poetry shell
```

#### Making Changes

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Make your changes** following the code style guidelines below

3. **Test your changes**:
   ```bash
   poetry run pinger
   ```

4. **Commit your changes** with a clear message:
   ```bash
   git commit -m "Add: brief description of changes"
   ```

5. **Push to your fork** and submit a Pull Request

#### Code Style Guidelines

- Follow PEP 8 style guide
- Use type hints where appropriate
- Add docstrings for functions and classes
- Keep functions focused and single-purpose
- Write clear, descriptive variable names

Example:
```python
def calculate_latency_stats(latencies: list[float]) -> dict[str, float]:
    """Calculate min, max, avg, and median from latency list.
    
    Args:
        latencies: List of latency values in milliseconds
        
    Returns:
        Dictionary with min, max, avg, median keys
    """
    if not latencies:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "median": 0.0}
    
    return {
        "min": min(latencies),
        "max": max(latencies),
        "avg": statistics.mean(latencies),
        "median": statistics.median(latencies),
    }
```

#### Pre-commit Checklist

Before submitting a PR:
- [ ] Code follows style guidelines
- [ ] All existing tests pass (if any)
- [ ] New features have basic manual testing
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated with your changes
- [ ] Version bumped appropriately in `pyproject.toml` and `config.py`

### Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update CHANGELOG.md with a note about your changes
3. Ensure version numbers are updated in `pyproject.toml` and `config.py`
4. The PR will be reviewed by maintainers
5. Address any feedback from code review
6. Once approved, the PR will be merged

## Development Workflow

### Testing Changes Locally

```bash
# Run the application
poetry run pinger

# Or use pipx for testing installation
poetry build
pipx install dist/network_pinger-*.whl --force
pinger
```

### Building and Publishing

Maintainers follow this process for releases:

```bash
# Update version in pyproject.toml and config.py
poetry build
poetry publish
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

**⚠️ CRITICAL: Always create and push a git tag!**  
The in-app version check feature uses GitHub Tags API (`api.github.com/repos/meshlg/_pinger/tags`) to detect new releases. If you don't create a tag, users won't be notified about available updates.

## Questions?

- Open an issue for questions about contributing
- Check existing issues and documentation first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.
