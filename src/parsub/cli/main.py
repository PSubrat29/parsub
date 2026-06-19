"""
Command-line interface for ParSub.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
import sys
from pathlib import Path

# Add src to path so we can import parsub modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

app = typer.Typer(name="parsub", help="Agentic Math/Physics research tool for LaTeX analysis")
console = Console(legacy_windows=True, force_jupyter=False, force_terminal=False)


@app.command()
def analyze(
    latex_file: str = typer.Argument(..., help="Path to LaTeX source file"),
    output_dir: str = typer.Option("./output", help="Output directory for generated code and results"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """
    Analyze LaTeX source file and generate Python code for numerical evaluation.
    """
    console.print(Panel.fit("🔬 ParSub - Agentic Math/Physics Research Tool", style="blue"))

    # Read LaTeX file
    try:
        with open(latex_file, 'r', encoding='utf-8') as f:
            latex_source = f.read()
    except FileNotFoundError:
        console.print(f"[red]Error: File '{latex_file}' not found.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(1)

    if verbose:
        console.print(f"[dim]Read {len(latex_source)} characters from {latex_file}[/dim]")

    # Parse LaTeX
    with Progress(
        SpinnerColumn(spinner_name="dots", style="bold cyan"),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task1 = progress.add_task("Parsing LaTeX...", total=None)
        parsed_result = parse_latex_source(latex_source)
        progress.update(task1, description="✅ LaTeX parsed")

        task2 = progress.add_task("Analyzing expressions...", total=None)
        analyzed_tasks = analyze_expressions(
            parsed_result.get('expressions', []),
            {
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])
            }
        )
        progress.update(task2, description="✅ Expressions analyzed")

        task3 = progress.add_task("Generating Python code...", total=None)
        code_file = generate_code_from_tasks(analyzed_tasks, output_dir)
        progress.update(task3, description="✅ Code generated")

    # Display results
    console.print("\n[green]Analysis Complete![/green]")
    console.print(f"📄 Input file: {latex_file}")
    console.print(f"📝 Expressions found: {len(parsed_result.get('expressions', []))}")
    console.print(f"⚙️  Computation tasks: {len(analyzed_tasks)}")
    console.print(f"💾 Generated code: {code_file}")
    console.print(f"📁 Output directory: {output_dir}")

    if verbose:
        console.print("\n[yellow]Extracted Information:[/yellow]")
        if parsed_result.get('goals'):
            console.print(f"  Goals: {parsed_result['goals']}")
        if parsed_result.get('methods'):
            console.print(f"  Methods: {parsed_result['methods']}")
        if parsed_result.get('parameters'):
            console.print(f"  Parameters: {[p['name'] for p in parsed_result['parameters'][:5]]}")

        console.print("\n[yellow]Computation Tasks:[/yellow]")
        for i, task in enumerate(analyzed_tasks, 1):
            console.print(f"  {i}. {task['goal_type'].title()}: {task['expression'][:50]}...")

    # Show generated code if requested
    if verbose and typer.confirm("\nShow generated code?", default=False):
        try:
            with open(code_file, 'r') as f:
                code_content = f.read()
            syntax = Syntax(code_content, "python", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Generated Python Code"))
        except Exception as e:
            console.print(f"[red]Could not display code: {e}[/red]")


@app.command()
def run(
    code_file: str = typer.Argument(..., help="Path to generated Python code file"),
    output_dir: str = typer.Option("./output", help="Directory where results will be saved")
):
    """
    Execute generated Python code to compute results and generate plots.
    """
    console.print(Panel.fit("🚀 Running ParSub Generated Code", style="green"))

    code_path = Path(code_file)
    if not code_path.exists():
        console.print(f"[red]Error: Code file '{code_file}' not found.[/red]")
        raise typer.Exit(1)

    # Change to output directory and run the code
    import subprocess
    import os

    try:
        # Set output directory in environment
        env = os.environ.copy()
        env['PARSUB_OUTPUT_DIR'] = output_dir

        # Run the code
        result = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=output_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode == 0:
            console.print("[green]✅ Code executed successfully![/green]")
            if result.stdout:
                console.print("\n[blue]Output:[/blue]")
                console.print(result.stdout)
        else:
            console.print("[red]❌ Code execution failed![/red]")
            if result.stderr:
                console.print("[red]Error output:[/red]")
                console.print(result.stderr)
            if result.stdout:
                console.print("[blue]Standard output:[/blue]")
                console.print(result.stdout)

    except subprocess.TimeoutExpired:
        console.print("[red]❌ Code execution timed out (2 minutes)[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error running code: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def demo():
    """Run a demonstration with sample LaTeX input."""
    console.print(Panel.fit("[demo] ParSub Demo", style="magenta"))

    # Sample LaTeX expressions
    sample_latex = r"""
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
    \item $g$ is the gravitational acceleration ($9.81  m/s^2$)
    \end{itemize}

    We want to plot the trajectory for different angles and find the maximum range.

    The range equation is:
    \begin{equation}
    R = \frac{v_0^2 \sin(2\theta)}{g}
    \end{equation}

    \end{document}
    """

    with Progress(
        SpinnerColumn(spinner_name="dots", style="bold cyan"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=True
    ) as progress:
        task1 = progress.add_task("Parsing sample LaTeX...", total=None)
        parsed_result = parse_latex_source(sample_latex)
        progress.update(task1, description="✅ LaTeX parsed")

        task2 = progress.add_task("Analyzing expressions...", total=None)
        analyzed_tasks = analyze_expressions(
            parsed_result.get('expressions', []),
            {
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])
            }
        )
        progress.update(task2, description="✅ Expressions analyzed")

        task3 = progress.add_task("Generating demo code...", total=None)
        demo_dir = "./demo_output"
        code_file = generate_code_from_tasks(analyzed_tasks, demo_dir)
        progress.update(task3, description="✅ Demo code generated")

    console.print(f"\n[green]Demo completed![/green]")
    console.print(f"[folder] Demo files saved to: {demo_dir}")
    console.print(f"[file] Generated code: {code_file}")
    console.print(f"\nTo run the demo:")
    console.print(f"  parsub run {code_file} --output-dir {demo_dir}")

    # Show what was detected
    if parsed_result.get('goals'):
        console.print(f"\n[yellow]Detected Goals:[/yellow] {parsed_result['goals']}")
    if parsed_result.get('parameters'):
        param_names = [p['name'] for p in parsed_result['parameters']]
        console.print(f"[yellow]Detected Parameters:[/yellow] {param_names}")


@app.command()
def version():
    """Show version information."""
    console.print("ParSub v0.1.0")
    console.print("Agentic Math/Physics Research Tool")


if __name__ == "__main__":
    app()