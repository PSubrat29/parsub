# ParSub User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Command Line Interface](#command-line-interface)
3. [Python API](#python-api)
4. [REST API](#rest-api)
5. [Understanding the Workflow](#understanding-the-workflow)
6. [The Generated Script](#the-generated-script)
7. [Advanced Usage](#advanced-usage)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

ParSub requires Python 3.9 or higher.

```bash
git clone https://github.com/PSubrat29/parsub.git
cd parsub
pip install -e .

# Verify the installation
parsub --version
# ParSub v0.1.0
```

### Basic Concepts

ParSub works in five stages:
1. **Input**: LaTeX source code (a file or a string)
2. **Parsing**: extract the mathematical expressions and the prose around them
3. **Analysis**: decide what to compute for every expression
4. **Code generation**: write a self-contained Python script
5. **Execution**: run the script to produce plots and data

## Command Line Interface

```bash
parsub --help
```

### analyze

Analyze LaTeX source and generate Python code:

```
parsub analyze LATEX_FILE [OPTIONS]

Arguments:
  LATEX_FILE  Path to LaTeX source file  [required]

Options:
  -o, --output-dir TEXT  Output directory for generated code and results  [default: ./output]
  -v, --verbose          Verbose output
  --show-code            Print the generated Python code
  --run                  Run the generated code immediately
  --timeout FLOAT        Time limit in seconds when using --run  [default: 600]
  --help                 Show this message and exit.
```

Example:
```bash
parsub analyze paper.tex --output-dir ./results --verbose
```

The command prints a table of the computation tasks and writes
`generated_computation.py` and `analysis.json` to the output directory.

### run

Execute generated Python code:

```
parsub run CODE_FILE [OPTIONS]

Arguments:
  CODE_FILE  Path to generated Python code file  [required]

Options:
  -o, --output-dir TEXT  Directory where results will be saved [default: the script's directory]
  --timeout FLOAT        Overall time limit in seconds  [default: 600]
  --task-timeout FLOAT   Time limit per task in seconds
  --help                 Show this message and exit.
```

Example:
```bash
parsub run ./results/generated_computation.py
```

The exit code is 0 when every task succeeded and 1 otherwise.

### demo

Run the built-in projectile-motion demonstration:

```bash
parsub demo            # analyze only, writes ./demo_output
parsub demo --run      # analyze and run
```

### version

```bash
parsub version
parsub --version
```

`python -m parsub ...` works as an alternative to the `parsub` command.

### CLI Examples

#### Simple expression

Given `physics.tex` containing:
```latex
The kinetic energy is given by $E = \frac{1}{2}mv^2$
```

```bash
parsub analyze physics.tex --run
```

ParSub recognises `E = ...` as a definition, and because the right-hand side has two
variables (`m`, `v`) it draws a surface plot of the kinetic energy over both.

#### Plotting a wave

Given `wave.tex` containing:
```latex
We want to plot the wave function:
\begin{equation}
\psi(x,t) = A \sin(kx - \omega t)
\end{equation}
```

```bash
parsub analyze wave.tex --output-dir ./wave_results --run
```

The plot sweeps `x` and holds `t`, `A`, `k` and `omega` at default values that are
listed in the task description (and can be edited in the generated script).

## Python API

### One-step analysis

```python
import parsub

result = parsub.analyze_latex(latex_source, output_dir="./output", source_name="paper.tex")
print(result.code_path)        # ./output/generated_computation.py
print(result.analysis_path)    # ./output/analysis.json
print(result.summary())        # counts, goals, methods, parameters, warnings
for task in result.tasks:
    print(task["goal_type"], task["description"])

process = parsub.run_generated_code(result.code_path)   # subprocess.CompletedProcess
print(process.returncode, process.stdout)

# From a file: returns the path of the generated script
code_file = parsub.analyze_latex_file("paper.tex", "./output")
```

### Stage by stage

```python
from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

with open("document.tex", encoding="utf-8") as f:
    latex_source = f.read()

parsed = parse_latex_source(latex_source)
tasks = analyze_expressions(
    parsed["expressions"],
    {
        "goals": parsed["goals"],
        "methods": parsed["methods"],
        "parameters": parsed["parameters"],
        "assignments": parsed["assignments"],
    },
)
code_file = generate_code_from_tasks(tasks, "./my_output")
```

### Customizing the analysis

The goal detection can be steered with your own context, or overridden per
expression with a `goal_type` key:

```python
from parsub.parser.latex_parser import LaTeXParser
from parsub.analyzer.expression_analyzer import ExpressionAnalyzer
from parsub.generator.code_generator import CodeGenerator

parsed = LaTeXParser().parse(latex_source)

custom_context = {
    "goals": ["we want to plot this function", "find the maximum value"],
    "methods": [],
    "assignments": {"g": 9.81},          # values for parameters held fixed
}
analyzer = ExpressionAnalyzer()
tasks = [task.to_dict() for task in analyzer.analyze_expressions(parsed["expressions"], custom_context)]

# Force a goal for one expression
parsed["expressions"][0]["goal_type"] = "optimize"

generator = CodeGenerator("./custom_output")
code = generator.generate_evaluation_code(tasks)      # the script as a string
path = generator.save_code(code)                      # ./custom_output/generated_computation.py
```

## REST API

### Starting the server

```bash
# Method 1: console script (127.0.0.1:8000; PARSUB_API_HOST / PARSUB_API_PORT override)
parsub-api

# Method 2: uvicorn directly
uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000

# Method 3: development with auto-reload
uvicorn parsub.api.main:app --reload
```

Open `http://localhost:8000/` in a browser for the interactive documentation.

All files are kept inside an **output root** (`PARSUB_OUTPUT_ROOT`, default `./output`
relative to the server's working directory). `output_dir` values in requests are
sub-directories of that root, and all returned paths are relative to it.

### POST /analyze

**Request body:**
```json
{
  "latex_source": "\\begin{equation} E = mc^2 \\end{equation}",
  "output_dir": "api_results"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Analysis completed successfully",
  "expressions_found": 1,
  "tasks_generated": 1,
  "output_dir": "api_results",
  "generated_code_path": "api_results/generated_computation.py",
  "analysis_path": "api_results/analysis.json",
  "extracted_info": {
    "goals": [],
    "methods": [],
    "parameters": [
      {"name": "E", "frequency": 1, "type": "unknown", "suggested_range": {"min": -5.0, "max": 5.0}, "default": 1.0},
      {"name": "c", "frequency": 1, "type": "constant", "suggested_range": {"min": -5.0, "max": 5.0}, "default": 1.0},
      {"name": "m", "frequency": 1, "type": "constant", "suggested_range": {"min": 0.1, "max": 10.0}, "default": 1.0}
    ],
    "expressions": [{"latex": "E = mc^2", "sympy": "Eq(E, c**2*m)", "kind": "equation", "label": null}],
    "tasks": [{"goal_type": "plot", "description": "Plot E = c**2*m for c in [-5, 5], m in [0.1, 10]"}]
  },
  "warnings": []
}
```

### POST /upload

Multipart form with `file` (a `.tex`, `.latex` or `.ltx` file, UTF-8, at most 5 MB)
and an optional `output_dir` field. The response has the same format as `/analyze`.

```bash
curl -F "file=@paper.tex" -F "output_dir=paper" http://localhost:8000/upload
```

### POST /run

Runs a script generated by ParSub inside the output root and lists the files it produced.

```json
{"code_path": "api_results/generated_computation.py", "timeout": 600}
```

```json
{
  "success": true,
  "message": "All tasks completed",
  "output_files": ["api_results/plots/task_1_surface_plot.png", "api_results/data/task_1_surface_data.csv",
                   "api_results/data/summary.json"],
  "tasks_succeeded": 1,
  "tasks_failed": 0,
  "stdout": "...",
  "stderr": ""
}
```

### GET /execute/{code_path}

Returns the shell command that runs a generated script locally (it does not run it).

### GET /download/{file_path}

Downloads a generated file, e.g. `GET /download/api_results/plots/task_1_surface_plot.png`.

### GET /health

```json
{"status": "healthy", "service": "ParSub API", "version": "0.1.0"}
```

### Status codes

| Code | Meaning |
|------|---------|
| 400 | Invalid input (wrong file type, not a ParSub script, bad encoding) |
| 403 | Path outside the output root |
| 404 | File not found |
| 413 | Upload too large |
| 422 | Request body does not match the schema |
| 504 | `/run` exceeded its time limit |

### API security notes

- Every path is resolved inside the output root; absolute paths and `..` escapes are rejected.
- `/run` only executes `.py` files whose header shows they were generated by ParSub.
- Running generated code costs CPU time; expose the API only to trusted users or put it
  behind authentication.

## Understanding the Workflow

### Stage 1: LaTeX parsing

ParSub walks the document with pylatexenc and collects:
- inline math (`$...$`, `\(...\)`) and display math (`$$...$$`, `\[...\]`, `equation`,
  `align`, `gather`, `multline`, `flalign`, `alignat`, `eqnarray`, `displaymath`, `dmath`,
  and their starred forms); `align`-like environments are split at `\\`
- equation labels (`\label{...}`) and the prose preceding each formula
- side conditions such as `\,\,\, (\Re(z) > 0)` or `\quad x \geq 1`, turned into range
  constraints

The preamble, comments, bibliography and references are ignored. Inline mentions such as
`$x$` or `$\Gamma(z)$` and inequalities are not treated as computations, while statements
such as `$g = 9.81$` are remembered as parameter values.

Each formula is converted with SymPy's LaTeX parser in strict mode, so a formula is either
converted completely or reported as not converted (`sympy_expr = None`) — it is never
silently truncated.

### Stage 2: Goal and context analysis

For each expression the analyzer chooses a goal:

| Goal | Chosen when | Output |
|------|-------------|--------|
| `evaluate` | "compute", "calculate", ... or 3+ variables | value at a point and a sweep (CSV + plot) |
| `plot` | "plot", "graph", ... or 1–2 variables | line or surface plot + data |
| `solve` | "solve", "roots", "zeros", or a plain equation | symbolic and numeric roots + plot |
| `optimize` | "maximum", "minimize", "optimal", ... | minimum and/or maximum + plot |
| `integrate` | "integral", "integrate" or an integral in the formula | antiderivative, definite integral or integral values |
| `differentiate` | "derivative" or a derivative in the formula | partial derivatives + plot of f and f' |
| `series` | "Taylor", "expansion", "approximation" | series expansion + comparison plot |
| `verify` | an identity between special functions, integrals or sums | numerical check of both sides |
| `symbolic` | the formula uses functions ParSub cannot evaluate | symbolic record (JSON) |

Keywords in the sentences just before a formula count twice as much as the document-wide
goals and methods. Definitions such as `y = f(x)` or `B(\zeta, \eta) = ...` compute the
right-hand side and use the left-hand side as the label.

### Stage 3: Parameter inference

- **Independent variables** (swept) are chosen by name: `x`, `t`, `z`, `r`, `theta`, ...
  come before parameters such as `g`, `m`, `alpha`; values stated in the document are never swept
  unless nothing else can be.
- **Fixed parameters** get the value stated in the document or a typical default
  (`g = 9.81`, `theta = pi/4`, generic constants `= 1`, ...).
- **Ranges** come from the variable name (e.g. `t` in [0, 10], `theta` in [0, 2π]) and
  are tightened by side conditions.

### Stage 4: Code generation

The generated script contains the ParSub runtime helpers followed by one small function per
task, so it runs without ParSub installed and is easy to edit.

### Stage 5: Execution

Every task runs in isolation with a time limit. Results and failures are recorded in
`data/summary.json`; one failing task never stops the others.

## The Generated Script

```bash
python generated_computation.py                    # all tasks, results next to the script
python generated_computation.py --output-dir out   # write somewhere else
python generated_computation.py --tasks 1,3        # only some tasks
python generated_computation.py --timeout 300      # per-task time limit (seconds, 0 = none)
```

The output directory can also be set with the `PARSUB_OUTPUT_DIR` environment variable.
A task looks like this:

```python
def task_2(ctx):
    """Find extrema of R = v_0**2*sin(2*theta)/g for theta in [0, 6.28318] with v_0=10, g=9.81"""
    expr = parse_sympy("Mul(Pow(Symbol('g'), Integer(-1)), Pow(Symbol('v_0'), Integer(2)), sin(Mul(Integer(2), Symbol('theta'))))")
    return optimize_task(
        ctx, 2, expr, independent=['theta'],
        fixed={'v_0': 10.0, 'g': 9.81},
        ranges={'theta': (0.0, 6.283185), 'v_0': (0.0, 20.0), 'g': (9.0, 10.0)},
        direction='maximize', points=1000,
    )
```

Change `fixed`, `ranges` or `points` and re-run the script to explore other values.

## Advanced Usage

### Output formats

`save_data(data, filename, ctx=ctx)` chooses the format from the extension:
CSV (`.csv`), TSV (`.tsv`), Excel (`.xlsx`) or JSON (`.json`). Change the file names in the
generated script to switch formats.

### High-resolution output

Plots are saved at 300 DPI. To change this, edit in the generated script:
```python
plt.rcParams["savefig.dpi"] = 300
```

### Expressions NumPy cannot evaluate

Integrals, infinite sums and products are evaluated point by point with SymPy/mpmath; sampling
is automatically reduced (at most 120 points per curve, 25×25 per surface) to keep run times
reasonable. Results that are not real numbers are stored as empty cells (NaN).

### Extending ParSub

1. **Add a goal type**: add keywords to `GOAL_KEYWORDS` in
   `parsub/analyzer/expression_analyzer.py`, a `*_task` function in
   `parsub/generator/runtime.py` and a branch in `CodeGenerator._generate_task_code`.
2. **Improve parameter inference**: extend `PARAMETER_HINTS` in `parsub/core/parameters.py`.
3. **Support more LaTeX**: extend the clean-up in `parsub/parser/latex_to_sympy.py`.

## Troubleshooting

### "No mathematical expressions were found in the input"
- Make sure formulas are in math mode (`$...$`, `\[...\]`, `equation`, ...).
- Inline symbols such as `$x$` on their own are intentionally ignored.

### An expression is listed but not converted
- `analysis.json` lists every expression with `"kind": null` when SymPy could not read it.
  Typical causes: `\dots`, hypergeometric notation such as `{}_1F_1`, custom macros or
  text inside formulas. Rewriting the formula in plain notation usually helps.

### A task failed
- `data/summary.json` contains the error message and traceback of every task.
- Run a single task with `python generated_computation.py --tasks N`.
- Increase the per-task time limit with `--timeout`.

### Plots look empty
- The function may not be real-valued in the chosen range (e.g. `sqrt(x)` for `x < 0`);
  adjust `ranges` in the generated script.

### FAQ

**Q: Do I need to install LaTeX?**
A: No. ParSub reads LaTeX as text; it never compiles documents.

**Q: Can ParSub handle my custom macros?**
A: Standard math is supported. Unknown macros usually make a formula unconvertible; it is then
reported rather than computed incorrectly.

**Q: Is my data safe?**
A: Yes. Everything runs locally.

**Q: Can I use ParSub in a Jupyter notebook?**
A: Yes. Use the Python API, then display the PNG files from the `plots` directory.

**Q: How does ParSub compare to Mathematica or Maple?**
A: ParSub focuses on extracting computations from LaTeX and generating Python code; it relies on
the scientific Python stack rather than being a computer algebra system itself.

---

*Happy researching with ParSub!*
