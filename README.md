# ParSub - Agentic Math/Physics Research Tool

![ParSub Logo](docs/logo.png)

**ParSub** is an intelligent research tool that analyzes LaTeX mathematical expressions, extracts computational goals, and automatically generates Python code for numerical evaluation, visualization, and data generation.

## 🔬 Features

- **LaTeX Parsing**: Robustly extracts mathematical expressions from LaTeX source
- **Goal Recognition**: Identifies research objectives (evaluate, solve, plot, optimize, integrate, differentiate)
- **Parameter Inference**: Automatically identifies variables and suggests reasonable ranges
- **Code Generation**: Produces executable Python code with NumPy, SymPy, and Matplotlib
- **High-Quality Output**: Generates publication-ready plots (300 DPI) and data files (CSV/TSV/Excel)
- **Privacy-First**: All processing happens locally - no data leaves your machine
- **CLI & API**: Command-line interface and REST API for flexible usage
- **Well-Tested**: Comprehensive unit test suite

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/parsub.git
cd parsub

# Install in development mode
pip install -e .

# Or install from PyPI (when available)
pip install parsub
```

## 🚀 Quick Start

### Using the Command Line

```bash
# Analyze a LaTeX file
parsub analyze paper.tex --output-dir ./results

# Run the generated code
parsub run ./results/generated_computation.py --output-dir ./results

# Or do both in one step
parsub analyze paper.tex --output-dir ./results && \
parsub run ./results/generated_computation.py --output-dir ./results
```

### Using the Python API

```python
from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

# Read LaTeX source
with open("paper.tex", "r") as f:
    latex_source = f.read()

# Parse and analyze
parsed = parse_latex_source(latex_source)
tasks = analyze_expressions(
    parsed.get('expressions', []),
    {
        'goals': parsed.get('goals', []),
        'methods': parsed.get('methods', []),
        'parameters': parsed.get('parameters', [])
    }
)

# Generate code
code_file = generate_code_from_tasks(tasks, "./output")
print(f"Generated code saved to: {code_file}")
```

### Using the REST API

```bash
# Start the API server
parsub-api

# Or using uvicorn directly
uvicorn parsub.api.main:app --host 0.0.0.0 --port 8000

# Analyze LaTeX via HTTP
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "latex_source": "\\\\begin{equation} E = mc^2 \\\\end{equation}",
    "output_dir": "./api_results"
  }'
```

## 📊 Output

ParSub generates:
- **Python code**: Ready-to-run computation scripts
- **Plots**: High-resolution PNG/JPEG figures (300 DPI)
- **Data**: CSV, TSV, or Excel files with numerical results
- **Metadata**: JSON files with analysis details

All outputs are saved in the specified output directory:
```
output/
├── generated_computation.py    # Generated Python code
├── plots/
│   ├── task_1_plot.png         # 1D plots
│   ├── task_2_surface_plot.png # 2D surface plots
│   └── ...
└── data/
    ├── task_1_evaluation.csv   # Numerical data
    ├── task_2_solutions.json   # Solution details
    └── ...
```

## 📚 Documentation

- [User Guide](docs/user_guide.md) - Detailed usage instructions
- [API Reference](docs/api_reference.md) - REST API documentation
- [Development Guide](docs/development_guide.md) - Contributing to ParSub
- [Examples](examples/) - Sample LaTeX files and expected outputs

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=parsub tests/

# Run specific test module
pytest tests/test_parser.py
```

## 📝 Sample Usage

See the [examples/](examples/) directory for sample LaTeX files.

Try the demo:
```bash
parsub demo
```

This will:
1. Parse a sample LaTeX file on projectile motion
2. Extract equations, goals, and parameters
3. Generate Python code to compute and plot trajectories
4. Show you how to run the generated code

## 🔒 Privacy & Security

ParSub is designed with privacy as a core principle:
- **Local Processing**: All LaTeX parsing, analysis, and code generation happens on your machine
- **No Telemetry**: We don't collect usage data or send information to external servers
- **Secure Sandbox**: Generated code runs in a restricted environment when executed via the CLI
- **File Access Control**: API endpoints restrict file access to designated output directories

## 🛠️ Architecture

```
ParSub/
├── cli/              # Command-line interface
├── api/              # REST API interface
├── parser/           # LaTeX parsing components
├── analyzer/         # Expression analysis and goal detection
├── generator/        # Python code generation
├── tests/            # Unit tests
├── examples/         # Sample LaTeX files
└── docs/             # Documentation
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

ParSub is released under the MIT License. See [LICENSE](LICENSE) for details.

*✅ Publishing complete: ParSub v0.1.0 is now live at https://github.com/PSubrat29/parsub*

## 🙏 Acknowledgements

- Built with [SymPy](https://www.sympy.org/) for symbolic mathematics
- Uses [LaTeXWalker](https://github.com/jeanmichel/LaTeXWalker) for LaTeX parsing
- Plotting powered by [Matplotlib](https://matplotlib.org/) and [Plotly](https://plotly.com/)
- CLI framework built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
- API powered by [FastAPI](https://fastapi.tiangolo.com/)

---

**ParSub** - Turning LaTeX mathematics into computational insights, automatically.