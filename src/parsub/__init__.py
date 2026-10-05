"""
ParSub - Agentic Math/Physics research tool.

Turns the mathematics in LaTeX documents into runnable Python computations:
LaTeX -> parsed expressions -> computation tasks -> generated script -> plots/data.
"""

__version__ = "0.2.2"

__all__ = ["__version__", "analyze_latex", "analyze_latex_file", "run_generated_code"]


def analyze_latex(latex_source, output_dir="./output", source_name=None):
    """Parse, analyze and generate code for a LaTeX string. See :mod:`parsub.core.pipeline`."""
    from parsub.core.pipeline import analyze_latex as _analyze_latex

    return _analyze_latex(latex_source, output_dir, source_name=source_name)


def analyze_latex_file(latex_file, output_dir="./output"):
    """Analyze a LaTeX file and return the path of the generated Python code."""
    from parsub.core.pipeline import analyze_latex_file as _analyze_latex_file

    return _analyze_latex_file(latex_file, output_dir)


def run_generated_code(code_path, output_dir=None, timeout=None, capture_output=True):
    """Run a generated computation script. See :func:`parsub.core.pipeline.run_generated_code`."""
    from parsub.core.pipeline import run_generated_code as _run_generated_code

    return _run_generated_code(code_path, output_dir, timeout=timeout, capture_output=capture_output)
