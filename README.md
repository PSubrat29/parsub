# ParSub - Agentic Math/Physics Research Tool

[![Tests](https://github.com/PSubrat29/parsub/actions/workflows/tests.yml/badge.svg)](https://github.com/PSubrat29/parsub/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/parsub)](https://pypi.org/project/parsub/)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/PSubrat29/parsub/blob/master/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/PSubrat29/parsub/blob/master/LICENSE)

![ParSub Logo](https://raw.githubusercontent.com/PSubrat29/parsub/master/docs/logo.png)

**ParSub** reads the mathematics in a LaTeX document, works out what can be computed from it, and
writes a ready-to-run Python script that evaluates, plots, solves, optimizes, integrates,
differentiates or numerically verifies every formula it understands — producing publication-quality
plots and data files.

```
paper.tex ──parse──► expressions ──analyze──► tasks ──generate──► generated_computation.py ──run──► plots/ + data/
```

## 🔬 Features

- **LaTeX parsing** – extracts inline (`$...$`, `\(...\)`) and display math (`$$...$$`, `\[...\]`,
  `equation`, `align`, `gather`, `multline`, `eqnarray`, ...), splits multi-line environments,
  keeps equation labels, skips the preamble, comments and bibliography.
- **LaTeX → SymPy** – uses SymPy's LaTeX parser in strict mode (no silently truncated formulas) with
  clean-up for real papers: `\pi`, `e^{x}`, `\Gamma(z)`, subscripts such as `v_0`/`x_{max}`, font
  macros, `:=`, and side conditions such as `(\Re(z) > 0)` that become sampling constraints.
- **Special-function notation** – hypergeometric functions `{}_pF_q(a; b; z)`, Pochhammer symbols
  `(a)_n`, Laguerre/Gegenbauer/Jacobi polynomials `L_n^{(a)}(x)`, Bessel functions `J_\nu(x)`,
  indexed functions `w_{\alpha}(z)` and derivatives `w''(z)`, `w^{\prime}(z)`.
- **Uses the document's own definitions** – a function defined in the paper (`\pi(x) = 1/\Gamma(x+1)`)
  is substituted wherever it is used, parameters defined in terms of others
  (`\vartheta = \alpha + (b+1)/2`) get consistent values, and `i = \sqrt{-1}` is honoured.
- **Checks the mathematics** – identities, alternative definitions of the same function and
  differential equations are verified numerically, so misprints are caught
  (see [Validation](#-validation-on-a-real-paper)).
- **Goal recognition** – reads the surrounding prose ("we want to plot", "find the maximum", "solve
  for x", ...) to choose between *evaluate*, *plot*, *solve*, *optimize*, *integrate*,
  *differentiate*, *series*, *verify* (numerical check of identities) and *symbolic*.
- **Parameter inference** – decides which variables are swept and which are held fixed, with sensible
  ranges and default values; values stated in the text (e.g. `$g = 9.81$`) are used automatically.
- **Self-contained code generation** – one small, editable function per task plus an embedded helper
  library (NumPy, SciPy, SymPy, Matplotlib, pandas). Integrals and infinite sums are evaluated
  numerically when no closed form is needed.
- **Robust execution** – every task runs in isolation with a time limit, so one hard formula never
  blocks the rest; a `summary.json` records what succeeded.
- **High-quality output** – 300 DPI PNG plots and CSV/TSV/Excel/JSON data.
- **Privacy-first** – everything runs locally; no data leaves your machine.
- **CLI, Python API, REST API and Docker image**, covered by an automated test suite.

## 📦 Installation

Requires Python 3.9 or newer.

```bash
pip install parsub
```

From source (for development):

```bash
git clone https://github.com/PSubrat29/parsub.git
cd parsub
pip install -e ".[dev]"     # includes the test tools
```

## 🚀 Quick Start

### Command line

```bash
# Try the built-in projectile-motion demo (analyze + run)
parsub demo --run

# Analyze a LaTeX file, then run the generated code
parsub analyze examples/projectile.tex --output-dir ./results
parsub run ./results/generated_computation.py

# ...or both in one step
parsub analyze examples/sample.tex -o ./results --run
```

`parsub --help` lists all commands and options (`analyze`, `run`, `demo`, `version`).

### Python API

```python
import parsub

# One call: parse, analyze and write generated_computation.py + analysis.json
result = parsub.analyze_latex(r"We plot $y = \sin(x) e^{-x/5}$", output_dir="./output")
for task in result.tasks:
    print(task["goal_type"], "-", task["description"])

# Run the generated script (results go next to it: ./output/plots and ./output/data)
process = parsub.run_generated_code(result.code_path)
print(process.stdout)
```

The individual stages are available too:

```python
from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

parsed = parse_latex_source(open("paper.tex", encoding="utf-8").read())
tasks = analyze_expressions(parsed["expressions"], {
    "goals": parsed["goals"],
    "methods": parsed["methods"],
    "assignments": parsed["assignments"],
})
code_file = generate_code_from_tasks(tasks, "./output")
```

### REST API

```bash
parsub-api                                   # http://127.0.0.1:8000 (interactive docs at /docs)
# or: uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000

curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"latex_source": "\\begin{equation} E = mc^2 \\end{equation}", "output_dir": "api_results"}'

curl -X POST http://127.0.0.1:8000/run \
  -H "Content-Type: application/json" \
  -d '{"code_path": "api_results/generated_computation.py"}'
```

Endpoints: `POST /analyze`, `POST /upload`, `POST /run`, `GET /execute/{path}`,
`GET /download/{path}`, `GET /health`. All files live inside one output root
(`PARSUB_OUTPUT_ROOT`, default `./output`); paths outside it are rejected.

### Docker

The REST API is available as a ready-made image (no Python installation needed):

```bash
docker run -d --name parsub -p 8000:8000 -v parsub-data:/data ghcr.io/psubrat29/parsub:latest
```

Open http://localhost:8000/ for the interactive API documentation. See the
[Docker section of the User Guide](https://psubrat29.github.io/parsub/docs/user_guide.html#docker).

## 📊 Output

```
output/
├── generated_computation.py     # the generated, editable Python script
├── analysis.json                # what was extracted and why each task was chosen
├── plots/
│   ├── task_1_plot.png          # 1-D plots
│   ├── task_2_surface_plot.png  # 2-D surface plots
│   └── task_3_verification_plot.png
└── data/
    ├── task_1_plot_data.csv     # numerical data
    ├── task_3_verification.json # results (roots, extrema, integrals, identity checks, ...)
    └── summary.json             # status of every task
```

The generated script accepts `--output-dir DIR`, `--timeout SECONDS` (per task) and `--tasks 1,3`.

## 📚 Documentation

- [User Guide](https://psubrat29.github.io/parsub/docs/user_guide.html) – detailed usage of the CLI, Python API and REST API
- [API Reference](https://psubrat29.github.io/parsub/docs/api_reference.html) – modules, functions and data formats
- [Development Guide](https://psubrat29.github.io/parsub/docs/development_guide.html) – setting up, testing, releasing
- [Validation report](https://psubrat29.github.io/parsub/docs/validation.html) – what ParSub found in the example paper
- [Changelog](https://psubrat29.github.io/parsub/docs/changelog.html) – what changed in each version
- [Examples](https://github.com/PSubrat29/parsub/tree/master/examples) – `projectile.tex` (physics) and
  `sample.tex` (a research note on generalized Bessel functions)

## ✅ Validation on a real paper

[`examples/sample.tex`](https://github.com/PSubrat29/parsub/blob/master/examples/sample.tex) is a
research note on generalized Bessel functions with 25 numbered equations. Running

```bash
parsub analyze examples/sample.tex -o results --run
```

converts every numbered equation except the generic definition (4) and runs 28 computations in about
90 seconds. Of the 22 numerical checks, 19 confirm the paper's identities. Among them: the Gamma
integral, both Beta-function forms, Kummer's second transformation, the claim that the series (9)
solves the differential equation (8), and every alternative form of w_α(z) and of the Bessel-Clifford
function. The remaining three flag real problems:

| Equation | ParSub's verdict | Explanation |
|----------|------------------|-------------|
| (6) | does not hold | Kummer's first formula is misprinted; it should read ₁F₁(ε; ϱ; z) = eᶻ ₁F₁(ϱ−ε; **ϱ**; **−z**) |
| (22) | does not hold | the Laguerre index should be L_k^{(ϑ)}, not L_k^{(ϑ−1)} (equation (23) is correct) |
| w_α(0) = 0 | holds except at α = 0 | true for Re α > 0 only |

Each finding was confirmed independently with mpmath. Details are in the
[validation report](https://psubrat29.github.io/parsub/docs/validation.html).

## 🧪 Running Tests

```bash
pip install -e ".[dev]"
pytest                      # all tests
pytest --cov=parsub         # with coverage
pytest tests/test_parser.py # one module
```

## 🔒 Privacy & Security

- **Local processing** – parsing, analysis, code generation and execution happen on your machine.
- **No telemetry** – nothing is sent to external servers.
- **Isolated execution** – generated code runs in a separate Python process with time limits.
  It is ordinary Python, so review it before running code generated from documents you do not trust.
- **File access control** – the REST API only reads and writes inside its output root and only runs
  scripts that ParSub generated there.

## 🛠️ Architecture

```
src/parsub/
├── parser/      # LaTeX walking (pylatexenc) and LaTeX → SymPy conversion
├── analyzer/    # goal detection, variable roles, sampling strategy
├── generator/   # code generation + runtime helpers embedded in generated scripts
├── core/        # shared parameter knowledge and the end-to-end pipeline
├── cli/         # `parsub` command (Typer + Rich)
└── api/         # REST API (FastAPI)
```

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](https://github.com/PSubrat29/parsub/blob/master/CONTRIBUTING.md).

## 📄 License

ParSub is released under the MIT License. See [LICENSE](https://github.com/PSubrat29/parsub/blob/master/LICENSE).

## 🙏 Acknowledgements

- [SymPy](https://www.sympy.org/) for symbolic mathematics and LaTeX parsing
- [pylatexenc](https://github.com/phfaist/pylatexenc) for LaTeX tokenisation
- [NumPy](https://numpy.org/), [SciPy](https://scipy.org/), [pandas](https://pandas.pydata.org/) and
  [Matplotlib](https://matplotlib.org/) for numerics, data and plotting
- [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/) for the CLI
- [FastAPI](https://fastapi.tiangolo.com/) for the REST API

---

**ParSub** - Turning LaTeX mathematics into computational insights, automatically.
