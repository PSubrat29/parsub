# ParSub API Reference

## Overview

This document describes the public API of ParSub, organized by module.

## Main Package

### `parsub`

Top-level package providing convenience functions.

#### `analyze_latex_file(latex_file: str, output_dir: str = "./output") -> str`
Convenience function that performs complete analysis and code generation from a LaTeX file.

**Args:**
- `latex_file`: Path to LaTeX source file
- `output_dir`: Directory for generated code and outputs

**Returns:**
- Path to generated Python code file

**Example:**
```python
from parsub import analyze_latex_file

code_file = analyze_latex_file("paper.tex", "./results")
```

## Parser Module

### `parsub.parser.latex_parser`

#### `parse_latex_source(latex_source: str) -> Dict[str, Any]`
Parse LaTeX source and extract mathematical expressions and metadata.

**Args:**
- `latex_source`: Raw LaTeX source code

**Returns:**
Dictionary containing:
- `expressions`: List of parsed mathematical expressions
- `goals`: List of detected research goals
- `methods`: List of detected methods
- `parameters`: List of inferred parameters
- `raw_latex`: Original input
- `parse_error`: Error message if parsing failed (optional)

**Expression Dictionary Format:**
Each expression contains:
- `raw_latex`: Original LaTeX string
- `sympy_expr`: SymPy expression object (if conversion successful)
- `variables`: List of variable names
- `constants`: List of constant names
- `description`: Textual description (if available)

**Example:**
```python
from parsub.parser.latex_parser import parse_latex_source

result = parse_latex_source("$E = mc^2$")
print(result['expressions'][0]['sympy_expr'])  # E - c**2*m
```

#### `LaTeXParser`
Main parser class with more granular control.

##### `__init__()`
Initialize a new LaTeXParser instance.

##### `parse(latex_source: str) -> Dict[str, Any]`
Same as `parse_latex_source` function.

### Expression Analysis Module

#### `parsub.analyzer.expression_analyzer`

#### `analyze_expressions(expressions: List[Dict[str, Any]], context: Dict[str, Any] = None) -> List[Dict[str, Any]]`
Analyze mathematical expressions to determine computation tasks.

**Args:**
- `expressions`: List of expression dictionaries from parser
- `context`: Optional context with goals, methods, and parameters

**Returns:**
List of task dictionaries, each containing:
- `expression`: String representation of the expression
- `variables`: List of variable names
- `goal_type`: Type of computation ('evaluate', 'plot', 'solve', 'optimize', 'integrate', 'differentiate')
- `parameters`: Dictionary of parameter information
- `suggested_sampling`: Sampling strategy for numerical evaluation
- `expected_output_type`: Expected output type ('scalar', 'array', 'function')

**Example:**
```python
from parsub.analyzer.expression_analyzer import analyze_expressions

tasks = analyze_expressions(parsed_result['expressions'], {
    'goals': parsed_result['goals'],
    'methods': parsed_result['methods']
})
```

#### `ExpressionAnalyzer`
Analyzer class with more granular control.

##### `__init__()`
Initialize a new ExpressionAnalyzer instance.

##### `analyze_expressions(expressions, context) -> List[ComputationTask]`
Return list of ComputationTask objects instead of dictionaries.

### Code Generation Module

#### `parsub.generator.code_generator`

#### `generate_code_from_tasks(tasks: List[Dict[str, Any]], output_dir: str = "./output") -> str`
Generate Python code from analysis tasks and save to file.

**Args:**
- `tasks`: List of task dictionaries from analyzer
- `output_dir`: Directory to save generated code and outputs

**Returns:**
Path to generated Python code file

**Example:**
```python
from parsub.generator.code_generator import generate_code_from_tasks

code_file = generate_code_from_tasks(tasks, "./my_output")
```

#### `CodeGenerator`
Code generator class with more granular control.

##### `__init__(output_dir: str = "./output")`
Initialize a new CodeGenerator.

##### `generate_evaluation_code(tasks: List[Dict[str, Any]]) -> str`
Generate complete Python code as string (does not save to file).

##### `save_code(code: str, filename: str = "generated_computation.py") -> str`
Save generated code to file and return the path.

### CLI Module

#### `parsub.cli.main`

The CLI is accessed through the `parsub` command-line interface rather than direct Python imports.

See the [User Guide](docs/user_guide.md) for detailed CLI documentation.

### API Module

#### `parsub.api.main`

The API module contains the FastAPI application.

##### `app`
The FastAPI application instance.

To run the API server:
```bash
uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000
```

## Data Models

### Internal Data Structures

While not part of the public API, understanding these helps with advanced usage:

#### `MathExpression` (in parser)
Represents a parsed mathematical expression:
- `raw_latex`: str
- `sympy_expr`: Optional[sp.Expr]
- `variables`: List[str]
- `constants`: List[str]
- `description`: Optional[str]

#### `ComputationTask` (in analyzer)
Represents a analysis task:
- `expression`: str
- `sympy_expr`: sp.Expr
- `variables`: List[str]
- `goal_type`: str
- `parameters`: Dict[str, Any]
- `suggested_sampling`: Dict[str, Any]
- `expected_output_type`: str

## Version Information

### `__version__`
Access the package version:
```python
import parsub
print(parsub.__version__)  # Requires adding __version__ to __init__.py
```

Or via CLI:
```bash
parsub version
```

## Dependencies

ParSub depends on these key packages:
- `sympy` >= 1.12: Symbolic mathematics
- `latexwalker` >= 2.1: LaTeX parsing
- `numpy` >= 1.24.0: Numerical computations
- `scipy` >= 1.10.0: Scientific algorithms
- `matplotlib` >= 3.7.0: Plotting
- `plotly` >= 5.15.0: Interactive plotting (optional)
- `pandas` >= 2.0.0: Data handling
- `typer` >= 0.9.0: CLI framework
- `fastapi` >= 0.100.0: REST API framework
- `uvicorn` >= 0.23.0: ASGI server

## Error Handling

ParSub follows these error handling principles:

1. **Graceful Degradation**: When possible, ParSub continues with partial results rather than failing completely
2. **Informative Errors**: Error messages include context about what failed and why
3. **Validation**: Input validation occurs at API boundaries
4. **Logging**: Internal errors are logged for debugging

Common exceptions you might encounter:
- `FileNotFoundError`: When input file doesn't exist
- `ValueError`: When input data is invalid
- `RuntimeError`: When code generation or execution fails
- `ImportError`: When required dependencies are missing

## Extending ParSub

### Adding New Goal Types

To add a new type of computation (e.g., 'fourier_transform'):

1. Add the goal type to `ExpressionAnalyzer._determine_goal_type()`
2. Add a code generation method in `CodeGenerator` (e.g., `_generate_fourier_code_block`)
3. Update the task routing in `_generate_task_code`

### Adding New Output Formats

To add support for a new data format (e.g., HDF5):

1. Add a save function in `CodeGenerator._generate_helper_functions()`
2. Update the `save_data` helper to handle the new format
3. Update documentation

### Custom LaTeX Construct Handling

For specialized LaTeX packages or macros:

1. Extend `LaTeXParser` to recognize new constructs
2. Add appropriate conversion to SymPy expressions
3. Update parameter inference if needed

## Changelog

### Version 0.1.0 (Initial Release)
- Basic LaTeX parsing and expression extraction
- Goal detection (evaluate, solve, plot, optimize, integrate, differentiate)
- Parameter inference and range suggestion
- Python code generation with NumPy/SciPy/Matplotlib
- CLI and REST API interfaces
- Comprehensive test suite
- Documentation and examples

---

*Generated by ParSub v0.1.0*