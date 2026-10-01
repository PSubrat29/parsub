# ParSub Development Guide

## Setting Up the Development Environment

### Prerequisites

- Python 3.9 or higher
- Git
- No LaTeX distribution is needed (ParSub reads LaTeX as text)

### Installation

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/parsub.git
   cd parsub
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

3. Install the package in development mode with the development dependencies
   (pytest, pytest-cov, httpx):
   ```bash
   pip install -e ".[dev]"
   ```

### Project Structure

```
parsub/
├── .github/workflows/tests.yml   # continuous integration
├── docs/                         # documentation (also published on GitHub Pages)
├── examples/                     # example LaTeX files
├── src/parsub/
│   ├── __init__.py               # version and top-level convenience functions
│   ├── __main__.py               # python -m parsub
│   ├── parser/
│   │   ├── latex_parser.py       # walks the LaTeX document, collects formulas and prose
│   │   └── latex_to_sympy.py     # strict LaTeX -> SymPy conversion and clean-up
│   ├── analyzer/
│   │   └── expression_analyzer.py  # goal detection, variable roles, sampling
│   ├── generator/
│   │   ├── code_generator.py     # writes generated_computation.py
│   │   └── runtime.py            # helpers embedded in every generated script
│   ├── core/
│   │   ├── parameters.py         # symbol name -> type, range, default
│   │   └── pipeline.py           # end-to-end workflow shared by all interfaces
│   ├── cli/main.py               # `parsub` command
│   └── api/main.py               # REST API
├── tests/                        # unit and integration tests
├── _config.yml                   # GitHub Pages (Jekyll) configuration
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

## Running Tests

```bash
pytest                              # everything
pytest tests/test_parser.py         # one module
pytest -k "verify"                  # tests matching a keyword
pytest --cov=parsub --cov-report=html   # coverage report in htmlcov/
```

The suite contains:
- **Unit tests** for the parser, the LaTeX conversion, the analyzer, the generator and the runtime
  helpers (`test_parser.py`, `test_analyzer.py`, `test_generator.py`)
- **Integration tests** (`test_interfaces.py`) that analyze the example files, run the generated
  scripts and exercise the CLI and the REST API end to end

Integration tests run real computations and take about a minute.

## Code Style

- **PEP 8**, with a line length of 120 (configured for Black in `pyproject.toml`)
- **Type hints** for public functions; the code must stay compatible with Python 3.9
  (no `match`, no `X | Y` type unions at runtime)
- **Docstrings** for public modules, classes and functions
- **Naming**: `CapWords` classes, `snake_case` functions and variables, `UPPER_CASE` constants,
  `_leading_underscore` for private helpers

Optional formatting:
```bash
pip install black
black src tests
```

`src/parsub/generator/runtime.py` is copied verbatim into generated scripts, so it must only
import the scientific stack (NumPy, SciPy, SymPy, Matplotlib, pandas) and never `parsub` itself.

## Making Changes

1. Create a branch: `git checkout -b feature/your-feature-name`
2. Implement your change following the existing patterns; add or update tests.
3. Run `pytest`.
4. Commit with a message that explains why the change was made.
5. Push and open a pull request against `master`.

For bug fixes, add a failing test that reproduces the bug first.

When changing behaviour, update the documentation:
- `docs/user_guide.md` for user-facing changes
- `docs/api_reference.md` for API changes
- this guide for changes to the development process

## Continuous Integration

GitHub Actions (`.github/workflows/tests.yml`) runs on every push and pull request:
- installs the package with `pip install -e ".[dev]"` on Python 3.9, 3.11 and 3.13
- runs the complete test suite
- runs the CLI demo end to end

## Website

The project website is served by GitHub Pages from the `master` branch with Jekyll:
`_config.yml` selects the theme, `README.md` becomes the home page and the Markdown files in
`docs/` become documentation pages (`docs/index.md` is the documentation index). Links between
Markdown files are converted automatically, so link to `user_guide.md`, not to `.html` files.
Avoid double opening curly braces and the brace-percent sequence anywhere in Markdown (even in code
blocks): Jekyll treats them as Liquid template tags and the site build fails.

## Releasing New Versions

ParSub uses [Semantic Versioning](https://semver.org/). The version is defined once, in
`src/parsub/__init__.py` (`__version__`); `pyproject.toml` reads it from there.

1. Make sure CI is green and the documentation and changelog are up to date.
2. Update `__version__`.
3. Commit and tag:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin master --tags
   ```
4. Build and publish:
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```
5. Create a GitHub release with the release notes.

## Debugging

### The parser

```python
from parsub.parser.latex_parser import parse_latex_source
from parsub.parser.latex_to_sympy import clean_latex, latex_to_sympy

result = parse_latex_source(latex_source)
for expr in result["expressions"]:
    print(expr["label"], expr["kind"], expr["sympy_str"] or expr["latex"])

print(latex_to_sympy(clean_latex(r"\frac{a}{b}")))   # convert a single formula
```

To see the raw node tree:
```python
from pylatexenc.latexwalker import LatexWalker

nodes, _, _ = LatexWalker(latex_source, tolerant_parsing=True).get_latex_nodes()
print(nodes)
```

### The analyzer

```python
from parsub.analyzer.expression_analyzer import analyze_expressions

for task in analyze_expressions(result["expressions"], {"goals": result["goals"]}):
    print(task["goal_type"], task["description"])
```

`analysis.json`, written next to every generated script, contains the same information.

### The generated code

```bash
python -m py_compile output/generated_computation.py   # syntax check
python output/generated_computation.py --tasks 3       # run one task
```

`data/summary.json` contains the traceback of every failed task.

## Security Considerations

1. Generated code embeds expressions as SymPy `srepr` strings and all other values with
   `repr`; text from the LaTeX source only appears in sanitised comments.
2. The REST API resolves every path inside its output root and only runs ParSub-generated scripts.
3. Generated scripts are ordinary Python: they run with the user's permissions.

## Getting Help

1. Check the documentation.
2. Look at similar code in the repository.
3. Open an issue on GitHub.
