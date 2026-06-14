# ParSub User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Command Line Interface](#command-line-interface)
3. [Python API](#python-api)
4. [REST API](#rest-api)
5. [Understanding the Workflow](#understanding-the-workflow)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

ParSub requires Python 3.8 or higher.

```bash
# Install from source
git clone https://github.com/yourusername/parsub.git
cd parsub
pip install -e .

# Verify installation
parsub --version
# Should output: ParSub v0.1.0
```

### Basic Concepts

ParSub works in four stages:
1. **Input**: LaTeX source code (file or string)
2. **Parsing**: Extract mathematical expressions and metadata
3. **Analysis**: Determine what computations to perform
4. **Output**: Generate executable Python code and run it to produce results

## Command Line Interface

ParSub provides a rich CLI built with Typer and Rich.

### Main Commands

```bash
parsub --help
```

#### analyze

Analyze LaTeX source and generate Python code:

```bash
parsub analyze INPUT_FILE [OPTIONS]

Arguments:
  INPUT_FILE  Path to LaTeX source file  [required]

Options:
  -o, --output-dir DIRECTORY  Output directory  [default: ./output]
  -v, --verbose               Verbose output
  --help                      Show this message and exit
```

Example:
```bash
parsub analyze paper.tex --output-dir ./results --verbose
```

#### run

Execute generated Python code:

```bash
parsub run CODE_FILE [OPTIONS]

Arguments:
  CODE_FILE  Path to generated Python code file  [required]

Options:
  -o, --output-dir DIRECTORY  Output directory  [default: ./output]
  --help                      Show this message and exit
```

Example:
```bash
parsub run ./results/generated_computation.py --output-dir ./results
```

#### demo

Run a built-in demonstration:

```bash
parsub demo
```

#### version

Show version information:

```bash
parsub version
```

### CLI Examples

#### Simple Expression Analysis

Given a file `physics.tex` containing:
```latex
The kinetic energy is given by $E = \frac{1}{2}mv^2$
```

Run:
```bash
parsub analyze physics.tex
```

This will:
1. Extract the expression $E = \frac{1}{2}mv^2$
2. Identify that we likely want to evaluate it
3. Generate Python code to compute kinetic energy for various mass and velocity values
4. Save the code to `./output/generated_computation.py`

#### Complex Analysis with Plotting

Given a file `wave.tex` containing:
```latex
We want to plot the wave function:
\begin{equation}
\psi(x,t) = A \sin(kx - \omega t)
\end{equation}
```

Run:
```bash
parsub analyze wave.tex --output-dir ./wave_results
parsub run ./wave_results/generated_computation.py --output-dir ./wave_results
```

This will generate plots of the wave function for different values of x and t.

## Python API

ParSub can be used programmatically through its Python API.

### Basic Usage

```python
from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

# Step 1: Read LaTeX source
with open("document.tex", "r") as f:
    latex_source = f.read()

# Step 2: Parse LaTeX
parsed_result = parse_latex_source(latex_source)

# Step 3: Analyze expressions
tasks = analyze_expressions(
    parsed_result.get('expressions', []),
    {
        'goals': parsed_result.get('goals', []),
        'methods': parsed_result.get('methods', []),
        'parameters': parsed_result.get('parameters', [])
    }
)

# Step 4: Generate code
output_dir = "./my_output"
code_file = generate_code_from_tasks(tasks, output_dir)

print(f"Analysis complete! Generated code saved to: {code_file}")
```

### Direct Function Access

You can also use the high-level convenience functions:

```python
from parsub import analyze_latex_file

# One-step analysis and code generation
code_file = analyze_latex_file("paper.tex", "./output")
```

### Customizing Analysis

You can override the automatic goal detection by providing explicit context:

```python
from parsub.parser.latex_parser import LaTeXParser
from parsub.analyzer.expression_analyzer import ExpressionAnalyzer
from parsub.generator.code_generator import CodeGenerator

parser = LaTeXParser()
analyzer = ExpressionAnalyzer()
generator = CodeGenerator("./custom_output")

# Parse
result = parser.parse(latex_source)

# Provide explicit goals/methods if auto-detection isn't sufficient
custom_context = {
    'goals': ['we want to plot this function', 'find the maximum value'],
    'methods': ['using numerical sampling', 'applying optimization techniques'],
    'parameters': []  # Will be auto-extracted from expressions
}

# Analyze with custom context
tasks = analyzer.analyze_expressions(
    result.get('expressions', []),
    custom_context
)

# Generate code
code_file = generator.generate_evaluation_code(tasks)
```

## REST API

ParSub includes a FastAPI-based REST API for integration with web applications.

### Starting the API Server

```bash
# Method 1: Using the CLI command
parsub-api

# Method 2: Using uvicorn directly
uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000

# Method 3: For development with auto-reload
uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### POST /analyze

Analyze LaTeX source and generate code.

**Request Body:**
```json
{
  "latex_source": "\\\\begin{equation} E = mc^2 \\\\end{equation}",
  "output_dir": "./api_results"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Analysis completed successfully",
  "expressions_found": 1,
  "tasks_generated": 1,
  "generated_code_path": "./api_results/generated_computation.py",
  "extracted_info": {
    "goals": ["we aim to compute energy"],
    "methods": ["using mass-energy equivalence"],
    "parameters": [
      {"name": "E", "frequency": 1, "type": "unknown", "suggested_range": {"min": -5, "max": 5}},
      {"name": "m", "frequency": 1, "type": "unknown", "suggested_range": {"min": -5, "max": 5}},
      {"name": "c", "frequency": 1, "type": "constant", "suggested_range": {"min": -5, "max": 5}}
    ]
  }
}
```

#### POST /upload

Upload and analyze a LaTeX file.

**Form Data:**
- `file`: LaTeX file (.tex, .latex, .ltx)
- `output_dir`: Optional output directory (default: "./output")

**Response:** Same format as `/analyze`

#### GET /execute/{code_path}

Execute previously generated code (returns instructions for security reasons).

**Response:**
```json
{
  "message": "Code execution initiated. Check output directory for results.",
  "code_path": "./output/generated_computation.py",
  "instructions": "Run: python ./output/generated_computation.py --output-dir ./output"
}
```

#### GET /download/{file_path}

Download generated files (plots, data, etc.).

**Example:** `GET /download/output/plots/task_1_plot.png`

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "ParSub API"
}
```

### API Security Notes

- All file paths are restricted to the output directory for security
- Generated code execution returns instructions rather than executing directly (to prevent arbitrary code execution)
- In production, use a proper job queue (like Celery) for code execution instead of the simple endpoint provided

## Understanding the Workflow

### Stage 1: LaTeX Parsing

ParSub uses LaTeXWalker to parse LaTeX source and identify:
- Mathematical expressions in `$...$`, `$$...$$`, `\[...\]`, and environments like `equation`, `align`, etc.
- Text content for goal and method detection
- Mathematical macros and structures

### Stage 2: Goal and Context Analysis

The analyzer examines:
- **Explicit goals**: Phrases like "we aim to", "the goal is to", "we want to"
- **Methods**: Phrases like "we use", "by applying", "using"
- **Mathematical context**: Structure of expressions to infer intent
  - Equations (`=`) → likely solving
  - Expressions with trigonometric functions → likely plotting
  - Expressions with `max`/`min` → likely optimization
  - Integral/differential symbols → likely integration/differentiation

### Stage 3: Parameter Inference

For each expression, ParSub identifies:
- **Variables**: Symbols that appear to be inputs (x, y, z, t, theta, etc.)
- **Constants**: Fixed values or parameters (m, g, c, h, etc.)
- **Parameter types**: Inferred from variable names and context
- **Suggested ranges**: Reasonable defaults based on parameter names

### Stage 4: Code Generation

The generator creates Python code that:
- Uses SymPy for symbolic manipulation when beneficial
- Uses NumPy for fast numerical computations
- Uses Matplotlib for publication-quality plotting
- Saves all outputs to organized directories
- Includes error handling and logging

## Advanced Usage

### Custom Output Formats

ParSub supports multiple output formats for data:
- CSV (`.csv`)
- TSV (`.tsv`)
- Excel (`.xlsx`, `.xls`)

The format is determined by the file extension in the `save_data` function calls within the generated code.

### High-Resolution Output

All plots are generated at 300 DPI by default, suitable for publication. To change this:

In the generated code, modify:
```python
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
```

### Parameter Sweeps

For multi-parameter studies, ParSub automatically:
- Creates parameter grids using NumPy's `linspace` and `meshgrid`
- Evaluates expressions across the parameter space
- Saves results in structured formats

### Handling Complex Expressions

ParSub can handle:
- Multi-dimensional arrays and tensors (conceptually)
- Special functions (via SymPy and NumPy)
- Piecewise definitions
- Recursive relations (iterative solutions in generated code)

### Extending ParSub

To add new analysis capabilities:

1. **Add new goal types** in `ExpressionAnalyzer._determine_goal_type()`
2. **Add new code generation templates** in `CodeGenerator` methods
3. **Enhance parameter inference** in `LaTeXParser._infer_parameter_type()` and `_infer_parameter_range()`
4. **Add new LaTeX construct handling** in the parser if needed

## Troubleshooting

### Common Issues

#### "No expressions found"
- Ensure your LaTeX contains mathematical content in math mode (`$...$`, `\[...\]`, etc.)
- Check that you're using standard LaTeX math environments
- Try simplifying your LaTeX to isolate the issue

#### Generated code fails to run
- Check that all dependencies are installed: `numpy`, `scipy`, `matplotlib`, `sympy`, `pandas`
- Ensure you're running the code in the correct environment
- Look for syntax errors in the generated code (rare, but possible with complex LaTeX)

#### Plots not appearing
- Check the `./output/plots/` directory for generated PNG files
- Verify that matplotlib can display plots in your environment (may need backend configuration)
- For headless servers, the Agg backend is used automatically

#### Memory issues with large parameter sweeps
- Reduce the number of points in the sampling (look for `points:` in generated code)
- Consider reducing the parameter ranges
- Use more efficient algorithms for your specific use case

### Getting Help

1. Check the [FAQ](#faq) below
2. Search existing issues on GitHub
3. Open a new issue with detailed information
4. For urgent matters, contact the maintainers

### FAQ

**Q: Do I need to install LaTeX to use ParSub?**
A: No! ParSub only needs to read LaTeX as text. It does not compile LaTeX documents.

**Q: Can ParSub handle my specific LaTeX package or macro?**
A: ParSub handles standard LaTeX math constructs. For custom macros, it will treat them as unknown symbols, which may still work depending on how they're used.

**Q: Is my data safe with ParSub?**
A: Yes. All processing happens locally. No data is sent to external servers unless you explicitly choose to do so.

**Q: Can I use ParSub in a Jupyter notebook?**
A: Yes! You can use the Python API within notebook cells, or execute the generated code and display the results.

**Q: How does ParSub compare to other tools like Mathematica or Maple?**
A: ParSub is focused on the specific workflow of extracting computations from LaTeX and generating Python code. It's not a full computer algebra system, but leverages the excellent Python scientific stack.

**Q: Can I contribute LaTeX macros or domain-specific knowledge to ParSub?**
A: Absolutely! We welcome contributions that improve ParSub's understanding of specific domains (physics, engineering, finance, etc.).

---

*Happy researching with ParSub! If you find this tool useful, please consider starring the repository and sharing it with colleagues.*