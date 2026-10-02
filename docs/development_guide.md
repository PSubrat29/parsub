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
├── .github/workflows/        # tests, website and PyPI release automation
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

GitHub Actions workflows in `.github/workflows/`:
- `tests.yml` – on every push and pull request: installs the package with `pip install -e ".[dev]"`
  on Python 3.9, 3.11 and 3.13, runs the complete test suite and the CLI demo end to end
- `pages.yml` – on every push to `master`: builds and deploys the website, then checks that the
  live pages respond
- `publish.yml` – on a published GitHub release (or manually): builds, checks and uploads the
  package to PyPI or TestPyPI, then installs the uploaded version from the index
- `docker.yml` – on every push, pull request and release tag: builds the REST API image from the
  `Dockerfile`, runs it and tests the API; on `master` and release tags it publishes the image
  (amd64 + arm64) to `ghcr.io/psubrat29/parsub`

## Website

The website is built with Jekyll from the `master` branch: `_config.yml` selects the theme,
`README.md` becomes the home page and the Markdown files in `docs/` become documentation pages
(`docs/index.md` is the documentation index). It is published by the `pages.yml` workflow, which
needs **Settings → Pages → Build and deployment → Source: GitHub Actions** (one-time setting).
The site is at https://psubrat29.github.io/parsub/.

Links between Markdown files in `docs/` are converted automatically, so link to `user_guide.md`,
not to `.html` files. `README.md` uses absolute links because it is also shown on PyPI.
Avoid double opening curly braces and the brace-percent sequence anywhere in Markdown (even in code
blocks): Jekyll treats them as Liquid template tags and the site build fails.

## Docker image

The `Dockerfile` builds a wheel from `src/` and installs it in a slim Python image that runs
`parsub-api` as an unprivileged user, with `/data` as output root and a health check. The
`docker.yml` workflow publishes it to the GitHub Container Registry using the repository's own
`GITHUB_TOKEN`; no extra secret is needed. The image appears under **Packages** on the repository
page.

The image is public, so anyone can `docker pull` it without logging in. Should it ever show as
private, open https://github.com/users/PSubrat29/packages/container/package/parsub →
**Package settings** → **Danger Zone → Change visibility → Public**.

Tags: `latest` and `sha-<commit>` for every push to `master`; `X.Y.Z` and `X.Y` for every release
tag `vX.Y.Z`. To add version tags to an image built after a release without code changes, run
**Actions → Docker image → Run workflow** on `master` with *Also tag the image with the released
package version*; it refuses if `src/` differs from the release.

Local build and test:

```bash
docker build -t parsub-api .
docker run --rm -p 8000:8000 parsub-api
curl http://127.0.0.1:8000/health
```

## Publishing to PyPI

ParSub is published at https://pypi.org/project/parsub/ (and rehearsed on
https://test.pypi.org/project/parsub/). Publishing is free. It uses *Trusted Publishing*: GitHub
Actions proves its identity to PyPI directly, so no password or API token is stored anywhere.

The workflow `.github/workflows/publish.yml` does everything:

| Trigger | Uploads | Version |
|---------|---------|---------|
| Publishing a GitHub release `vX.Y.Z` | PyPI | `X.Y.Z` (must equal `__version__`) |
| Actions → Publish to PyPI → Run workflow → `testpypi` | TestPyPI | `X.Y.Z.devN`, unique for every run |
| Actions → Publish to PyPI → Run workflow → `pypi` | PyPI | `X.Y.Z` |

Each run builds the sdist and wheel, runs `twine check --strict`, installs the wheel in a clean
environment and runs the demo. It uploads, then installs exactly the uploaded version from the
index and runs the demo again. Before a PyPI upload it checks that the version is not on PyPI yet.

### One-time setup (already done for ParSub)

1. Create accounts at https://pypi.org/account/register/ and https://test.pypi.org/account/register/
   (they are separate), verify the e-mail addresses and enable two-factor authentication.
2. On PyPI open **Your account → Publishing → Add a new pending publisher** and enter:
   - PyPI project name: `parsub`
   - Owner: `PSubrat29`, Repository name: `parsub`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

   On TestPyPI do the same with the environment name `testpypi`. Once a project exists, the
   publisher is listed under **Your projects → parsub → Manage → Publishing**.
3. On GitHub open **Settings → Environments** and create the environments `pypi` and `testpypi`
   (optionally add yourself as a required reviewer for `pypi`, so every upload needs a click).

### Every release

1. Make sure CI is green on `master`.
2. Raise `__version__` in `src/parsub/__init__.py` (`pyproject.toml` reads it from there), e.g.
   `0.2.0` → `0.2.1` for fixes or `0.3.0` for new features, and add the version to
   `docs/changelog.md`. Update "current version" in `docs/index.md`. Commit and push to `master`.
3. Optional rehearsal: **Actions → Publish to PyPI → Run workflow**, choose `testpypi`,
   **Run workflow**. It can be repeated as often as you like. To try a rehearsal version
   yourself, take only ParSub from TestPyPI and its dependencies from PyPI (TestPyPI contains
   unrelated, sometimes broken, copies of popular packages):

   ```bash
   pip download --no-deps --dest wheel --index-url https://test.pypi.org/simple/ "parsub==X.Y.Z.devN"
   pip install wheel/parsub-*.whl
   ```
4. **Releases → Draft a new release**:
   - **Choose a tag**: type `vX.Y.Z` and select *Create new tag: vX.Y.Z on publish*
   - **Target**: `master`
   - **Release title**: `ParSub vX.Y.Z`
   - **Description**: the changelog entry for the version
   - leave *Set as a pre-release* unchecked and *Set as the latest release* checked
   - **Publish release**
5. Watch **Actions → Publish to PyPI**: all jobs should end green, including
   *Install the uploaded version*. Then check https://pypi.org/project/parsub/.

### Troubleshooting

| Error in the log | Meaning | Fix |
|------------------|---------|-----|
| `invalid-publisher: valid token, but no corresponding publisher` | PyPI/TestPyPI has no trusted publisher matching owner, repository, workflow and environment | Add or correct the publisher (step 2 of the setup), then **Re-run failed jobs** |
| `400 File already exists` | That version is already on the index; PyPI and TestPyPI never accept the same file twice, not even after deleting it | For PyPI raise `__version__` and release again; rehearsals use unique `.devN` versions |
| `FileNotFoundError ... DESCRIPTION.txt` (or another build error of a dependency) while installing from TestPyPI | pip took a dependency from TestPyPI instead of PyPI | Install only ParSub from TestPyPI (`pip download --no-deps ...`, see step 3) |
| `Release tag vA does not match package version B` | Tag and `__version__` differ | Delete the release and its tag, or raise `__version__` to match, then release again |
| `ParSub X is already on PyPI` | Version was released before | Raise `__version__` |
| `Environment protection rules` / waiting | The `pypi` environment requires approval | Approve the deployment in the run's page |

### Manual alternative

```bash
pip install build twine
python -m build                 # creates dist/parsub-X.Y.Z.tar.gz and .whl
twine check --strict dist/*
twine upload dist/*             # user name: __token__, password: a PyPI API token
```

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
