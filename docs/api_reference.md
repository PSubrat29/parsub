# ParSub API Reference

This document describes the public Python API of ParSub, organized by module.
For the command line and the REST API see the [User Guide](user_guide.md).

## Main Package

### `parsub`

#### `__version__`
The package version string, e.g. `"0.1.0"` (also shown by `parsub --version`).

#### `analyze_latex(latex_source, output_dir="./output", source_name=None) -> AnalysisResult`
Parse, analyze and generate code for a LaTeX string. Writes `generated_computation.py` and
`analysis.json` into `output_dir`. See [`AnalysisResult`](#analysisresult).

#### `analyze_latex_file(latex_file, output_dir="./output") -> str`
Same for a file; returns the path of the generated Python script.

```python
from parsub import analyze_latex_file

code_file = analyze_latex_file("paper.tex", "./results")
```

#### `run_generated_code(code_path, output_dir=None, timeout=600, capture_output=True) -> subprocess.CompletedProcess`
Run a generated script in a separate Python process. Results are written to `output_dir`
(default: the script's directory). Raises `FileNotFoundError` for a missing script and
`subprocess.TimeoutExpired` when `timeout` seconds are exceeded.

## Pipeline Module

### `parsub.core.pipeline`

#### `AnalysisResult`
Returned by `analyze_latex`:
- `parsed`: the parser result (see `parse_latex_source`)
- `tasks`: list of task dictionaries (see `analyze_expressions`)
- `code_path`, `analysis_path`, `output_dir`: paths of the written files
- `warnings`: list of messages (e.g. no expressions found)
- `expressions`: shortcut for `parsed["expressions"]`
- `summary()`: JSON-friendly overview (counts, goals, methods, parameters, paths, warnings)

#### `analyze_latex(...)`, `analyze_latex_file(...)`, `run_generated_code(..., task_timeout=None)`
The implementations behind the top-level functions. `task_timeout` sets the per-task time limit
of the generated script.

#### `read_run_summary(output_dir) -> dict | None`
Load `data/summary.json` written by a generated script.

## Parser Module

### `parsub.parser.latex_parser`

#### `parse_latex_source(latex_source: str) -> Dict[str, Any]`
Parse LaTeX source and extract mathematical expressions and metadata.

**Returns** a dictionary containing:
- `expressions`: list of expression dictionaries (below)
- `goals`: research goals found in the prose ("we aim to ...", "the goal is to ...")
- `methods`: methods found in the prose ("we use ...", "by applying ...")
- `parameters`: every free symbol with `name`, `frequency`, `type`, `suggested_range` and `default`
- `assignments`: values stated in the document, e.g. `{"g": 9.81}`
- `raw_latex`: the original input
- `text`: the prose with formulas replaced by placeholders
- `statistics`: `math_segments`, `expressions`, `converted`
- `parse_error`: only present if parsing failed

**Expression dictionary:**
- `raw_latex`: the formula as written
- `latex`: the cleaned formula that was converted
- `sympy_expr`: SymPy object (`sympy.Eq` for equations) or `None` if it could not be converted
- `sympy_str`: `str(sympy_expr)` or `None`
- `kind`: `"equation"`, `"expression"`, `"assignment"` or `None`
- `variables`: names of the free symbols
- `constants`: numeric constants used (`pi`, `E`, `I`)
- `display`: `True` for display math
- `environment`: `"inline"`, `"display"` or the environment name (`"equation"`, `"align*"`, ...)
- `label`: the `\label{...}` of the equation, if any
- `context`: prose preceding the formula
- `conditions` / `constraints`: side conditions and the bounds derived from them,
  e.g. `{"z": {"min": 0.0}}`
- `description`: reserved for a textual description (currently `None`)

**Example:**
```python
from parsub.parser.latex_parser import parse_latex_source

result = parse_latex_source("$E = mc^2$")
print(result["expressions"][0]["sympy_expr"])  # Eq(E, c**2*m)
```

#### `LaTeXParser`
Parser class. `LaTeXParser(context_chars=400).parse(latex_source)` returns the same dictionary as
`parse_latex_source`.

#### `MathExpression`
Dataclass behind the expression dictionaries (`to_dict()` produces them).

### `parsub.parser.latex_to_sympy`

Helpers used by the parser:
- `latex_to_sympy(latex) -> sympy object | None` – strict conversion of a single formula
- `clean_latex(latex) -> str` – remove labels, spacing and font macros
- `split_conditions(latex) -> (formula, conditions)` – split off `\,\,\, (\Re(z)>0)` style conditions
- `parse_constraints(conditions) -> dict` – bounds such as `{"z": {"min": 0.0}}`
- `is_assignment(expr)`, `assignment_value(expr)` – recognise `g = 9.81`

## Analyzer Module

### `parsub.analyzer.expression_analyzer`

#### `analyze_expressions(expressions, context=None) -> List[Dict[str, Any]]`
Analyze expressions and return JSON-serialisable task dictionaries.

**Args:**
- `expressions`: expression dictionaries from the parser (only `sympy_expr` is required;
  `context`, `constraints`, `kind`, `label`, `latex` and `goal_type` are used when present)
- `context`: optional `goals`, `methods`, `parameters` and `assignments`

**Task dictionary:**
- `expression`: what is computed (`str`); for a definition `y = f(x)` this is `f(x)`
- `srepr`: exact SymPy representation used by the generated code
- `latex`: LaTeX of `expression`
- `variables`: free variables
- `goal_type`: `evaluate`, `plot`, `solve`, `optimize`, `integrate`, `differentiate`, `series`,
  `verify` or `symbolic`
- `independent_variables`: variables that are swept
- `fixed_parameters`: `{name: value}` for the other variables
- `parameters`: per variable `type`, `range`, `default` and `role`
- `suggested_sampling`: `method`, `points` and `ranges` (`{name: (min, max)}`)
- `expected_output_type`: `scalar`, `array`, `function` or `symbolic`
- `options`: goal-specific options (`direction` for optimize, `solve_for`, series `order`/`point`)
- `label`: left-hand side of a definition, if any
- `equation`: `lhs`/`rhs` (srepr and str) for `solve` and `verify`
- `source_latex`, `source_label`: where the task came from
- `description`: human-readable summary

**Example:**
```python
from parsub.analyzer.expression_analyzer import analyze_expressions

tasks = analyze_expressions(parsed["expressions"], {
    "goals": parsed["goals"],
    "methods": parsed["methods"],
    "assignments": parsed["assignments"],
})
```

#### `ExpressionAnalyzer`
`ExpressionAnalyzer().analyze_expressions(expressions, context)` returns `ComputationTask`
objects instead of dictionaries (`task.to_dict()` converts them).

## Code Generation Module

### `parsub.generator.code_generator`

#### `generate_code_from_tasks(tasks, output_dir="./output", source_name=None) -> str`
Generate Python code from task dictionaries, save it as `generated_computation.py` and return its path.

#### `CodeGenerator`
- `CodeGenerator(output_dir="./output")` – creates `output_dir`, `plots/` and `data/`
- `generate_evaluation_code(tasks, source_name=None) -> str` – the complete script as a string
- `save_code(code, filename="generated_computation.py") -> str` – save it and return the path

### `parsub.generator.runtime`

The helper library that is embedded in every generated script (and importable directly):
- `lambdify_expr(expr, variables, fixed=None)` – vectorised numeric function; falls back to
  point-by-point SymPy evaluation for integrals and sums (`.pointwise` tells which is used)
- `evaluate_expression(expr, variables, values_dict) -> float`
- `save_plot(fig, filename, ctx=...)`, `save_data(data, filename, ctx=...)` – `.csv`, `.tsv`,
  `.xlsx` or `.json`
- `evaluate_task`, `plot_task`, `solve_task`, `optimize_task`, `integrate_task`,
  `differentiate_task`, `series_task`, `verify_task`, `symbolic_task` – one per goal type
- `run_tasks(tasks, argv=None, default_output_dir=None) -> int` – command-line runner
- `time_limit(seconds)`, `attempt(func, seconds)` – time limits (Unix)

## Shared Knowledge

### `parsub.core.parameters`

- `PARAMETER_HINTS`: `name -> (type, (min, max), default)` for common symbols
- `infer_parameter_type(name)`, `infer_parameter_range(name)`, `default_value(name)`,
  `describe_parameter(name, frequency)`; subscripted and variant names (`v_0`, `vartheta`)
  use the entry of their base name.

## CLI Module

### `parsub.cli.main`

The Typer application `app` behind the `parsub` command (`main()` is the console-script entry
point). See the [User Guide](user_guide.md#command-line-interface).

## REST API Module

### `parsub.api.main`

- `app`: the FastAPI application (`uvicorn parsub.api.main:app`)
- `run(host=None, port=None)`: entry point of the `parsub-api` command
- Environment variables: `PARSUB_OUTPUT_ROOT` (default `./output`), `PARSUB_API_HOST`
  (default `127.0.0.1`), `PARSUB_API_PORT` (default `8000`)

See the [User Guide](user_guide.md#rest-api) for the endpoints.

## Dependencies

- `sympy` >= 1.12 and `antlr4-python3-runtime` 4.11: symbolic mathematics and LaTeX parsing
- `pylatexenc` >= 2.10: LaTeX tokenisation
- `numpy` >= 1.24, `scipy` >= 1.10: numerical computation
- `matplotlib` >= 3.7: plotting
- `pandas` >= 2.0, `openpyxl` >= 3.1: data files (CSV/TSV/Excel)
- `typer` >= 0.9, `rich` >= 12: command line interface
- `fastapi` >= 0.100, `uvicorn` >= 0.23, `python-multipart`: REST API

## Error Handling

1. **Graceful degradation**: a formula that cannot be converted is reported, not guessed; a task
   that fails or times out is recorded in `data/summary.json` while the others continue.
2. **Informative errors**: the CLI prints clear messages and returns exit code 1; the REST API
   returns 400/403/404/413/504 with a `detail` message.
3. **Validation**: inputs are validated at the CLI and REST API boundaries.

## Extending ParSub

### Adding a goal type (e.g. `fourier_transform`)

1. Add keywords to `GOAL_KEYWORDS` (and `GOAL_PRIORITY`) in `expression_analyzer.py`.
2. Add a `fourier_task(ctx, task_id, expr, ...)` function to `generator/runtime.py`.
3. Add a branch for the goal in `CodeGenerator._generate_task_code`.
4. Add tests.

### Adding an output format

Extend `save_data` in `generator/runtime.py` (the format is chosen by file extension).

### Custom LaTeX constructs

Extend `clean_latex` / `_postprocess` in `parser/latex_to_sympy.py`.

## Changelog

### Version 0.1.0
- LaTeX parsing (inline/display math, align-like environments, labels, conditions, assignments)
- Strict LaTeX → SymPy conversion with clean-up for real papers
- Goal detection: evaluate, plot, solve, optimize, integrate, differentiate, series, verify, symbolic
- Parameter inference with ranges, defaults and document-stated values
- Self-contained generated scripts with isolated, time-limited tasks
- CLI, Python API and REST API
- Automated test suite and continuous integration
