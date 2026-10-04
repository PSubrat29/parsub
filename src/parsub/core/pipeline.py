"""
The complete ParSub workflow, shared by the Python API, the CLI and the REST API.

    LaTeX source --parse--> expressions --analyze--> tasks --generate--> script --run--> plots/data
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from parsub import __version__
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks
from parsub.generator.poster_generator import generate_poster_tex
from parsub.parser.latex_parser import parse_latex_source

ANALYSIS_FILENAME = "analysis.json"


@dataclass
class AnalysisResult:
    """Everything produced by :func:`analyze_latex`."""

    parsed: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    code_path: str
    analysis_path: str
    output_dir: str
    warnings: List[str] = field(default_factory=list)
    poster_path: Optional[str] = None

    @property
    def expressions(self) -> List[Dict[str, Any]]:
        return self.parsed.get("expressions", [])

    def summary(self) -> Dict[str, Any]:
        """JSON-friendly overview (used by the CLI and the REST API)."""
        return {
            "expressions_found": len(self.expressions),
            "expressions_converted": sum(1 for e in self.expressions if e.get("sympy_expr") is not None),
            "tasks_generated": len(self.tasks),
            "goals": self.parsed.get("goals", []),
            "methods": self.parsed.get("methods", []),
            "parameters": self.parsed.get("parameters", []),
            "code_path": self.code_path,
            "analysis_path": self.analysis_path,
            "poster_path": self.poster_path,
            "warnings": list(self.warnings),
        }


def _expression_record(expr: Dict[str, Any]) -> Dict[str, Any]:
    record = {key: value for key, value in expr.items() if key != "sympy_expr"}
    return record


def analyze_latex(latex_source: str, output_dir: str = "./output", source_name: Optional[str] = None) -> AnalysisResult:
    """
    Run the full analysis on a LaTeX string.

    Writes the computation script, analysis summary and an editable A0 poster
    source file into ``output_dir``.
    """
    parsed = parse_latex_source(latex_source)
    context = {
        "goals": parsed.get("goals", []),
        "methods": parsed.get("methods", []),
        "parameters": parsed.get("parameters", []),
        "assignments": parsed.get("assignments", {}),
        "constants": parsed.get("constants", {}),
    }
    tasks = analyze_expressions(parsed.get("expressions", []), context)
    code_path = generate_code_from_tasks(tasks, output_dir, source_name=source_name)
    poster_path = generate_poster_tex(parsed, tasks, output_dir, source_name=source_name)

    warnings: List[str] = []
    if parsed.get("parse_error"):
        warnings.append(f"LaTeX parsing failed: {parsed['parse_error']}")
    if not parsed.get("expressions"):
        warnings.append("No mathematical expressions were found in the input.")
    elif not tasks:
        warnings.append("Expressions were found, but none could be converted into a computation.")

    analysis = {
        "parsub_version": __version__,
        "generated_on": datetime.now().isoformat(timespec="seconds"),
        "source": source_name,
        "statistics": parsed.get("statistics", {}),
        "goals": parsed.get("goals", []),
        "methods": parsed.get("methods", []),
        "assignments": parsed.get("assignments", {}),
        "constants": {name: str(value) for name, value in parsed.get("constants", {}).items()},
        "parameters": parsed.get("parameters", []),
        "expressions": [_expression_record(expr) for expr in parsed.get("expressions", [])],
        "tasks": tasks,
        "generated_code": os.path.basename(code_path),
        "generated_poster": os.path.basename(poster_path),
        "warnings": warnings,
    }
    analysis_path = os.path.join(output_dir, ANALYSIS_FILENAME)
    with open(analysis_path, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, default=str)

    return AnalysisResult(parsed, tasks, code_path, analysis_path, output_dir, warnings, poster_path)


def analyze_latex_file(latex_file: str, output_dir: str = "./output") -> str:
    """Analyze a LaTeX file; returns the path of the generated Python code."""
    with open(latex_file, "r", encoding="utf-8") as handle:
        latex_source = handle.read()
    return analyze_latex(latex_source, output_dir, source_name=os.path.basename(latex_file)).code_path


def run_generated_code(code_path: str, output_dir: Optional[str] = None, timeout: Optional[float] = None,
                       capture_output: bool = True, task_timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """
    Execute a generated script in a separate Python process.

    Results go to ``output_dir`` (default: the directory containing the script).
    Raises ``FileNotFoundError`` if the script does not exist.  Execution is
    unlimited by default; set ``timeout`` or ``task_timeout`` to opt into limits.
    """
    script = os.path.abspath(code_path)
    if not os.path.isfile(script):
        raise FileNotFoundError(code_path)
    out_dir = os.path.abspath(output_dir) if output_dir else os.path.dirname(script)
    os.makedirs(out_dir, exist_ok=True)
    env = os.environ.copy()
    env["PARSUB_OUTPUT_DIR"] = out_dir
    env.setdefault("MPLBACKEND", "Agg")
    command = [sys.executable, script, "--output-dir", out_dir]
    if task_timeout is not None:
        command += ["--timeout", str(task_timeout)]
    return subprocess.run(
        command,
        cwd=out_dir,
        env=env,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )


def read_run_summary(output_dir: str) -> Optional[Dict[str, Any]]:
    """Load ``data/summary.json`` written by a generated script, if present."""
    path = os.path.join(output_dir, "data", "summary.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
