"""
Command-line interface for ParSub.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from parsub import __version__
from parsub.core.pipeline import AnalysisResult, analyze_latex, read_run_summary, run_generated_code

app = typer.Typer(
    name="parsub",
    help="Agentic Math/Physics research tool: turn LaTeX mathematics into runnable Python computations.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

DEMO_LATEX = r"""
\documentclass{article}
\begin{document}

We aim to compute the trajectory of a projectile under gravity.

The equation of motion is given by:
\begin{equation}
y = x \tan(\theta) - \frac{g x^2}{2 v_0^2 \cos^2(\theta)}
\end{equation}

where:
\begin{itemize}
\item $y$ is the height
\item $x$ is the horizontal distance
\item $\theta$ is the launch angle
\item $v_0$ is the initial velocity
\item $g$ is the gravitational acceleration ($g = 9.81$)
\end{itemize}

We want to plot the trajectory for different angles and find the maximum range.

The range equation is:
\begin{equation}
R = \frac{v_0^2 \sin(2\theta)}{g}
\end{equation}

\end{document}
"""


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"ParSub v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", help="Show the version and exit.", callback=_version_callback, is_eager=True
    ),
) -> None:
    """ParSub - Agentic Math/Physics research tool."""


def _print_analysis(result: AnalysisResult, source: str, verbose: bool) -> None:
    summary = result.summary()
    console.print("\n[green]Analysis complete![/green]")
    console.print(f"  Input:                 {source}")
    console.print(
        f"  Expressions found:     {summary['expressions_found']} "
        f"({summary['expressions_converted']} converted to SymPy)"
    )
    console.print(f"  Computation tasks:     {summary['tasks_generated']}")
    console.print(f"  Generated code:        {result.code_path}")
    console.print(f"  Analysis details:      {result.analysis_path}")
    if result.poster_path:
        console.print(f"  A0 poster (LaTeX):     {result.poster_path}")
    for warning in result.warnings:
        console.print(f"[yellow]  Warning: {warning}[/yellow]")

    if result.tasks:
        table = Table(title="Computation tasks", show_lines=False)
        table.add_column("#", justify="right")
        table.add_column("Goal")
        table.add_column("Description", overflow="fold")
        for index, task in enumerate(result.tasks, 1):
            description = task.get("description") or task.get("expression", "")
            if not verbose and len(description) > 110:
                description = description[:107] + "..."
            table.add_row(str(index), task["goal_type"], description)
        console.print(table)

    if verbose:
        console.print("\n[yellow]Extracted information[/yellow]")
        console.print(f"  Goals:      {summary['goals'] or '-'}")
        console.print(f"  Methods:    {summary['methods'] or '-'}")
        names = [p["name"] for p in summary["parameters"][:10]]
        console.print(f"  Parameters: {names or '-'}")


def _run(code_file: str, output_dir: Optional[str], timeout: Optional[float], task_timeout: Optional[float]) -> int:
    """Run a generated script, streaming its output. Returns the exit code."""
    code_path = Path(code_file)
    if not code_path.is_file():
        console.print(f"[red]Error: Code file '{code_file}' not found.[/red]")
        return 1
    out_dir = os.path.abspath(output_dir) if output_dir else str(code_path.resolve().parent)
    console.print(Panel.fit("Running ParSub generated code", style="green"))
    try:
        result = run_generated_code(
            str(code_path), out_dir, timeout=timeout, capture_output=False, task_timeout=task_timeout
        )
    except subprocess.TimeoutExpired:
        limit = f" ({timeout:g} s)" if timeout is not None else ""
        console.print(f"[red]Error: Code execution timed out{limit}.[/red]")
        return 1
    except OSError as exc:
        console.print(f"[red]Error running code: {exc}[/red]")
        return 1

    run_summary = read_run_summary(out_dir)
    if result.returncode == 0:
        console.print("[green]Success: all tasks completed.[/green]")
    elif run_summary:
        console.print(
            f"[yellow]Finished with {run_summary.get('failed', '?')} failed task(s) "
            f"and {run_summary.get('succeeded', '?')} successful task(s).[/yellow]"
        )
    else:
        console.print("[red]Error: code execution failed.[/red]")
    console.print(f"Results: {out_dir}")
    return result.returncode


@app.command()
def analyze(
    latex_file: str = typer.Argument(..., help="Path to LaTeX source file"),
    output_dir: str = typer.Option("./output", "--output-dir", "-o", help="Output directory for generated code and results"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    show_code: bool = typer.Option(False, "--show-code", help="Print the generated Python code"),
    run_code: bool = typer.Option(False, "--run", help="Run the generated code immediately"),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Optional overall time limit in seconds"),
):
    """
    Analyze a LaTeX source file and generate Python code for numerical evaluation.
    """
    console.print(Panel.fit("ParSub - Agentic Math/Physics Research Tool", style="blue"))

    try:
        with open(latex_file, "r", encoding="utf-8") as handle:
            latex_source = handle.read()
    except FileNotFoundError:
        console.print(f"[red]Error: File '{latex_file}' not found.[/red]")
        raise typer.Exit(1)
    except (OSError, UnicodeDecodeError) as exc:
        console.print(f"[red]Error reading file: {exc}[/red]")
        raise typer.Exit(1)

    if verbose:
        console.print(f"[dim]Read {len(latex_source)} characters from {latex_file}[/dim]")

    with console.status("Parsing LaTeX, analyzing expressions and generating code..."):
        result = analyze_latex(latex_source, output_dir, source_name=os.path.basename(latex_file))
    _print_analysis(result, latex_file, verbose)

    if show_code:
        code_content = Path(result.code_path).read_text(encoding="utf-8")
        console.print(Panel(Syntax(code_content, "python", line_numbers=True), title="Generated Python Code"))

    if run_code:
        code = _run(result.code_path, output_dir, timeout, None)
        raise typer.Exit(code)
    console.print(f"\nNext: parsub run {result.code_path}")


@app.command()
def run(
    code_file: str = typer.Argument(..., help="Path to generated Python code file"),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Directory where results will be saved [default: the script's directory]"
    ),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Optional overall time limit in seconds"),
    task_timeout: Optional[float] = typer.Option(None, "--task-timeout", help="Time limit per task in seconds"),
):
    """
    Execute generated Python code to compute results and generate plots.
    """
    raise typer.Exit(_run(code_file, output_dir, timeout, task_timeout))


@app.command()
def demo(
    output_dir: str = typer.Option("./demo_output", "--output-dir", "-o", help="Directory for the demo files"),
    run_code: bool = typer.Option(False, "--run", help="Also run the generated code"),
):
    """Run a demonstration with a sample LaTeX document (projectile motion)."""
    console.print(Panel.fit("ParSub Demo: projectile motion", style="magenta"))
    with console.status("Analyzing the demo document..."):
        result = analyze_latex(DEMO_LATEX, output_dir, source_name="demo: projectile motion")
    _print_analysis(result, "built-in projectile motion example", verbose=True)
    if run_code:
        raise typer.Exit(_run(result.code_path, output_dir, None, None))
    console.print("\nTo run the demo:")
    console.print(f"  parsub run {result.code_path}")


@app.command()
def version():
    """Show version information."""
    console.print(f"ParSub v{__version__}")
    console.print("Agentic Math/Physics Research Tool")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
