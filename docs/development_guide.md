# ParSub Development Guide

## Setting Up the Development Environment

### Prerequisites

- Python 3.8 or higher
- Git
- (Optional) LaTeX distribution for testing (TeX Live, MikTeX)

### Installation

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/yourusername/parsub.git
   cd parsub
   ```

2. Create a virtual environment:
   ```bash
   # Using venv (built-in)
   python -m venv venv
   
   # Activate it
   # On Unix/macOS:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. Install the package in development mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Install pre-commit hooks (recommended):
   ```bash
   pre-commit install
   ```

### Project Structure

```
ParSub/
├── docs/                 # Documentation
├── examples/             # Example LaTeX files
├── parsub/               # Source code
│   ├── cli/              # Command-line interface
│   ├── api/              # REST API interface
│   ├── parser/           # LaTeX parsing
│   ├── analyzer/         # Expression analysis
│   ├── generator/        # Code generation
│   └── __init__.py       # Package initialization
├── tests/                # Unit tests
├── pyproject.toml        # Project configuration
├── README.md             # Project overview
├── CONTRIBUTING.md       # Contribution guidelines
└── LICENSE               # MIT license
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests from a specific module
pytest tests/test_parser.py

# Run tests matching a keyword
pytest -k "parser"
```

### Coverage Reporting

```bash
# Generate coverage report
pytest --cov=parsub tests/

# Generate HTML coverage report
pytest --cov=parsub --cov-report=html tests/
# Then open htmlcov/index.html in your browser

# Generate XML coverage report (for CI)
pytest --cov=parsub --cov-report=xml tests/
```

### Test Types

ParSub includes:
- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test workflows across multiple modules
- **Example tests**: Test with the provided example LaTeX files

## Code Style

ParSub follows these style guidelines:

### Python Code Style

- **PEP 8**: Primary style guide
- **Line length**: 88 characters (Black default)
- **Type hints**: Use Python 3.8+ typing syntax
- **Docstrings**: Google-style docstrings for all public functions and classes
- **Naming**: 
  - Classes: `CapWords`
  - Functions and variables: `snake_case`
  - Constants: `UPPER_CASE_WITH_UNDERSCORES`
  - Private members: `_leading_underscore`

### Code Formatting

We use [Black](https://black.readthedocs.io/) for automatic code formatting:

```bash
# Format a specific file
black parsub/module/file.py

# Format the entire project
black .

# Check formatting without making changes
black --check .
```

We use [Flake8](https://flake8.pycqa.org/) for linting:

```bash
# Check a specific file
flake8 parsub/module/file.py

# Check the entire project
flake8 .
```

We use [isort](https://pycqa.isort.readthedocs.io/) for import sorting:

```bash
# Sort imports in a specific file
isort parsub/module/file.py

# Sort imports in the entire project
isort .
```

### Pre-commit Hooks

We've configured pre-commit to run Black, Flake8, and isort automatically:

```bash
# Install hooks (done once)
pre-commit install

# Now hooks run automatically on commit
# To manually run all hooks:
pre-commit run --all-files
```

## Making Changes

### Adding New Features

1. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement your changes**:
   - Follow the existing code patterns
   - Add appropriate type hints
   - Write comprehensive docstrings
   - Add unit tests for new functionality

3. **Test your changes**:
   ```bash
   # Run relevant tests
   pytest tests/ -k "related_to_your_change"
   
   # Run full test suite to ensure nothing broke
   pytest
   
   # Check code style
   black --check .
   flake8 .
   isort --check-only .
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add your-feature-name"
   ```

5. **Push and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   # Then create a PR on GitHub
   ```

### Fixing Bugs

1. **Create a bugfix branch**:
   ```bash
   git checkout -b fix/bug-description
   ```

2. **Add a failing test** that reproduces the bug (TDD approach)

3. **Fix the bug** and ensure the test passes

4. **Run the full test suite** to ensure no regressions

5. **Follow the same commit and PR process** as for features

### Documentation Updates

When changing functionality, update the relevant documentation:

- **User Guide**: `docs/user_guide.md` for user-facing changes
- **API Reference**: `docs/api_reference.md` for API changes
- **Development Guide**: This file for development process changes
- **Inline docstrings**: For code-level documentation

## Continuous Integration

ParSub uses GitHub Actions for CI. The workflow runs on:
- Pushes to `main` branch
- Pull requests
- Scheduled nightly builds

The CI checks:
- Code compiles and installs correctly
- All tests pass
- Code style requirements are met
- Documentation builds correctly

## Releasing New Versions

### Versioning

ParSub uses [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH**
- MAJOR: Incompatible API changes
- MINOR: Backward-compatible functionality
- PATCH: Backward-compatible bug fixes

### Release Process

1. **Ensure everything is ready**:
   - All tests pass on CI
   - Documentation is up to date
   - Changelog is updated

2. **Update version number**:
   - Update `__version__` in `parsub/__init__.py`
   - Update version in `pyproject.toml`
   - Update version in any other relevant places

3. **Create release commit**:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```

4. **Build and publish**:
   ```bash
   # Build distribution files
   python -m build
   
   # Upload to PyPI (requires maintainer privileges)
   twine upload dist/*
   ```

5. **Create GitHub Release**:
   - Tag the release
   - Add release notes
   - Upload distribution files

## Working with Dependencies

### Adding New Dependencies

1. Add to `pyproject.toml` in the appropriate section:
   - `[project]` for runtime dependencies
   - `[project.optional-dependencies]` for optional features
   - `[project.optional-dependencies.dev]` for development dependencies

2. Run to update lock files (if using):
   ```bash
   pip install -e ".[dev]"
   ```

### Updating Dependencies

```bash
# Check for outdated packages
pip list --outdated

# Update a specific package
pip install --upgrade package-name

# Update all development dependencies
pip install --upgrade -e ".[dev]"
```

## Testing Strategies

### Unit Testing Principles

1. **Test behavior, not implementation**: Focus on what the code does, not how it does it
2. **Edge cases**: Test boundary conditions and unusual inputs
3. **Error conditions**: Test that appropriate errors are raised when expected
4. **Isolation**: Mock external dependencies when testing internal logic
5. **Deterministic tests**: Tests should produce the same results every time

### Specific Testing Guidelines

#### Parser Tests
- Test with various LaTeX constructs
- Test edge cases like empty input, malformed LaTeX
- Verify expression extraction accuracy
- Test goal and method detection

#### Analyzer Tests
- Test goal type detection accuracy
- Test parameter inference
- Test sampling strategy generation
- Test with various expression complexities

#### Generator Tests
- Test code generation completeness
- Test that generated code is syntactically valid
- Test output file creation
- Test different goal types generate appropriate code

#### Integration Tests
- Test complete workflows from LaTex to generated code to execution
- Test with the provided example files
- Test API endpoints

## Debugging

### Common Debugging Techniques

1. **Verbose output**: Use `--verbose` flag with CLI commands
2. **Interactive debugging**: Use `pdb` or IDE debuggers
3. **Logging**: Add temporary `print()` statements or use the `logging` module
4. **Sample inputs**: Reduce complex inputs to minimal reproducing examples

### Debugging the Parser

If parsing isn't working as expected:
```python
from parsub.parser.latex_parser import LaTeXParser
from latexwalker import parse_latex

parser = LaTeXParser()
# Or use the lower-level parser to see raw parse tree
raw_parse, pos, _ = parse_latex(latex_source)
print(raw_parse)  # See the raw parse tree
```

### Debugging the Analyzer

If goal detection isn't working:
```python
from parsub.analyzer.expression_analyzer import ExpressionAnalyzer

analyzer = ExpressionAnalyzer()
# Test goal detection in isolation
goal_type = analyzer._determine_goal_type(expr_data, context)
```

### Debugging the Code Generator

If generated code isn't working:
```python
# Check that generated code is syntactically valid
python -m py_compile generated_file.py

# Run with verbose error tracing
python generated_file.py 2>&1
```

## Performance Considerations

While ParSub is not primarily a high-performance tool, consider:

1. **Lazy evaluation**: Delay expensive computations until needed
2. **Caching**: Cache results of expensive operations when appropriate
3. **Efficient algorithms**: Use NumPy vectorization instead of Python loops
4. **Memory usage**: Be mindful of large parameter sweeps generating large arrays

### Profiling

```bash
# Profile the CLI
python -m cProfile -s time parsub analyze example.tex

# Profile specific functions
import cProfile
import pstats
from parsub import some_function

profiler = cProfile.Profile()
profiler.enable()
result = some_function()
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('time')
stats.print_stats()
```

## Internationalization

Currently, ParSub is English-only. If you'd like to help with internationalization:

1. Externalize all user-facing strings
2. Use Python's `gettext` module
3. Add support for locale-specific formatting (numbers, dates, etc.)

## Accessibility

Ensure that:
- Generated plots are colorblind-friendly (we use viridis colormap by default)
- Text in plots is readable at high resolutions
- Alternative text descriptions are considered for visual outputs

## Security Considerations

When extending ParSub:

1. **Input validation**: Always validate and sanitize inputs
2. **Generated code security**: Be careful about what code gets generated
3. **File system access**: Restrict file operations to intended directories
4. **API security**: Validate all API inputs and use proper authentication in production

## Contributing Back

We appreciate your contributions! Please:

1. **Be respectful** of other contributors
2. **Follow the contribution guidelines** in CONTRIBUTING.md
3. **Write clear commit messages** that explain why changes were made
4. **Keep pull requests focused** on a single topic or fix
5. **Be responsive to feedback** during code review

## Getting Help

If you need help during development:

1. Check the existing documentation
2. Look at similar implementations in the codebase
3. Ask in the GitHub discussions or issue tracker
4. For complex issues, reach out to maintainers

---

*Happy coding! Remember: the goal is to make ParSub useful for researchers and scientists everywhere.*