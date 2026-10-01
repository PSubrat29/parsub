# ParSub - Agentic Math/Physics Research Tool

[![Tests](https://github.com/PSubrat29/parsub/actions/workflows/tests.yml/badge.svg)](https://github.com/PSubrat29/parsub/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/PSubrat29/parsub/blob/master/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/PSubrat29/parsub/blob/master/LICENSE)

![ParSub Logo](docs/logo.png)

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
- **CLI, Python API and REST API**, covered by an automated test suite.

## 📦 Installation

Requires Python 3.9 or newer.

```bash
git clone https://github.com/PSubrat29/parsub.git
cd parsub
pip install -e .            # or: pip install -e ".[dev]" for the test tools
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

- [User Guide](docs/user_guide.md) – detailed usage of the CLI, Python API and REST API
- [API Reference](docs/api_reference.md) – modules, functions and data formats
- [Development Guide](docs/development_guide.md) – setting up, testing and contributing
- [Examples](https://github.com/PSubrat29/parsub/tree/master/examples) – `projectile.tex` (physics) and
  `sample.tex` (a research note on generalized Bessel functions)

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
