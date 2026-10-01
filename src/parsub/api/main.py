"""
FastAPI interface for ParSub.

All files are confined to an output root directory (``PARSUB_OUTPUT_ROOT``,
default ``./output``).  The ``output_dir`` given in requests is a sub-directory
of that root, and every path returned by the API is relative to it, so it can
be passed straight back to ``/download``, ``/run`` or ``/execute``.

Start the server with ``parsub-api`` or ``uvicorn parsub.api.main:app``.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from parsub import __version__
from parsub.core.pipeline import AnalysisResult, analyze_latex, read_run_summary, run_generated_code

ALLOWED_EXTENSIONS = (".tex", ".latex", ".ltx")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app = FastAPI(
    title="ParSub API",
    description="Agentic Math/Physics research tool for LaTeX analysis and numerical evaluation",
    version=__version__,
)


# ------------------------------------------------------------------- models
class LaTeXInput(BaseModel):
    latex_source: str = Field(..., description="LaTeX source to analyze")
    output_dir: Optional[str] = Field(
        None, description="Sub-directory of the server's output root (default: the root itself)"
    )


class AnalysisResponse(BaseModel):
    success: bool
    message: str
    expressions_found: int
    tasks_generated: int
    output_dir: Optional[str] = None
    generated_code_path: Optional[str] = None
    analysis_path: Optional[str] = None
    extracted_info: Optional[Dict[str, Any]] = None
    warnings: List[str] = []


class RunInput(BaseModel):
    code_path: str = Field(..., description="Path of a generated script, relative to the output root")
    timeout: float = Field(600, gt=0, le=3600, description="Time limit in seconds")


class ExecutionResponse(BaseModel):
    success: bool
    message: str
    output_files: List[str] = []
    tasks_succeeded: Optional[int] = None
    tasks_failed: Optional[int] = None
    stdout: str = ""
    stderr: str = ""


# ------------------------------------------------------------------ helpers
def output_root() -> Path:
    """The directory that contains everything the API reads or writes."""
    root = Path(os.environ.get("PARSUB_OUTPUT_ROOT", "./output")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_inside_root(relative: Optional[str], must_exist: bool = False) -> Path:
    """Resolve a user-supplied path inside the output root, rejecting escapes."""
    root = output_root()
    text = (relative or "").strip().replace("\\", "/")
    if os.path.isabs(text) or re.match(r"^[A-Za-z]:", text):
        raise HTTPException(status_code=403, detail="Access denied: absolute paths are not allowed")
    candidate = (root / text).resolve()
    if must_exist and not candidate.exists():
        # Also accept paths that start with the root's own name, e.g. "output/plots/x.png"
        parts = Path(text).parts
        if parts and parts[0] in (".", root.name):
            stripped = parts[1:] if parts[0] == root.name else parts
            if stripped and stripped[0] == root.name:
                stripped = stripped[1:]
            candidate = root.joinpath(*stripped).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=403, detail="Access denied: path is outside the output directory")
    if must_exist and not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


def _relative(path: str) -> str:
    return Path(path).resolve().relative_to(output_root()).as_posix()


def _analysis_response(result: AnalysisResult, message: str) -> AnalysisResponse:
    summary = result.summary()
    expressions = [
        {"latex": expr.get("latex"), "sympy": expr.get("sympy_str"), "kind": expr.get("kind"), "label": expr.get("label")}
        for expr in result.expressions
    ]
    return AnalysisResponse(
        success=True,
        message=message,
        expressions_found=summary["expressions_found"],
        tasks_generated=summary["tasks_generated"],
        output_dir=_relative(result.output_dir) if Path(result.output_dir).resolve() != output_root() else ".",
        generated_code_path=_relative(result.code_path),
        analysis_path=_relative(result.analysis_path),
        extracted_info={
            "goals": summary["goals"],
            "methods": summary["methods"],
            "parameters": summary["parameters"][:5],
            "expressions": expressions[:20],
            "tasks": [{"goal_type": t["goal_type"], "description": t["description"]} for t in result.tasks],
        },
        warnings=summary["warnings"],
    )


def _analyze(latex_source: str, output_dir: Optional[str], source_name: str, message: str) -> AnalysisResponse:
    target = resolve_inside_root(output_dir)
    try:
        result = analyze_latex(latex_source, str(target), source_name=source_name)
    except Exception as exc:  # noqa: BLE001 - report as a server error
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
    return _analysis_response(result, message)


def _check_generated_script(path: Path) -> None:
    if path.suffix != ".py" or not path.is_file():
        raise HTTPException(status_code=400, detail="code_path must be a generated .py file")
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        head = handle.read(200)
    if "Generated by ParSub" not in head:
        raise HTTPException(status_code=400, detail="Only scripts generated by ParSub can be run")


# ---------------------------------------------------------------- endpoints
@app.get("/", include_in_schema=False)
async def root():
    """Send browsers to the interactive API documentation."""
    return RedirectResponse(url="/docs")


@app.post("/analyze", response_model=AnalysisResponse)
def analyze_endpoint(input_data: LaTeXInput):
    """
    Analyze LaTeX source and generate Python code for numerical evaluation.
    """
    return _analyze(input_data.latex_source, input_data.output_dir, "api request", "Analysis completed successfully")


@app.post("/upload", response_model=AnalysisResponse)
async def upload_latex_file(file: UploadFile = File(...), output_dir: Optional[str] = Form(None)):
    """
    Upload and analyze a LaTeX file (.tex, .latex, .ltx).
    """
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="File must be a LaTeX file (.tex, .latex, .ltx)")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (limit 5 MB)")
    try:
        latex_source = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    return _analyze(latex_source, output_dir, filename, f"File '{filename}' analyzed successfully")


@app.post("/run", response_model=ExecutionResponse)
def run_endpoint(input_data: RunInput):
    """
    Run a generated script and return the files it produced (relative to the output root).
    """
    script = resolve_inside_root(input_data.code_path, must_exist=True)
    _check_generated_script(script)
    out_dir = script.parent
    try:
        result = run_generated_code(str(script), str(out_dir), timeout=input_data.timeout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"Execution timed out after {input_data.timeout:g} s")
    summary = read_run_summary(str(out_dir)) or {}
    files: List[str] = []
    for task in summary.get("tasks", []):
        files.extend(task.get("files", []))
    root = output_root()
    output_files = [(out_dir / name).resolve().relative_to(root).as_posix() for name in files]
    output_files.append((out_dir / "data" / "summary.json").resolve().relative_to(root).as_posix())
    return ExecutionResponse(
        success=result.returncode == 0,
        message="All tasks completed" if result.returncode == 0 else "Execution finished with errors",
        output_files=output_files if summary else [],
        tasks_succeeded=summary.get("succeeded"),
        tasks_failed=summary.get("failed"),
        stdout=result.stdout[-10000:],
        stderr=result.stderr[-10000:],
    )


@app.get("/execute/{code_path:path}")
def execute_instructions(code_path: str):
    """
    Return the command that runs a generated script (use ``POST /run`` to run it on the server).
    """
    script = resolve_inside_root(code_path, must_exist=True)
    _check_generated_script(script)
    return {
        "message": "Run the generated code with the command below, or POST it to /run.",
        "code_path": _relative(str(script)),
        "instructions": f'parsub run "{script}"',
    }


@app.get("/download/{file_path:path}")
def download_file(file_path: str):
    """
    Download generated files (code, plots, data), addressed relative to the output root.
    """
    path = resolve_inside_root(file_path, must_exist=True)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(path), filename=path.name)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ParSub API", "version": __version__}


def run(host: Optional[str] = None, port: Optional[int] = None) -> None:
    """Console-script entry point (``parsub-api``)."""
    import uvicorn

    uvicorn.run(
        app,
        host=host or os.environ.get("PARSUB_API_HOST", "127.0.0.1"),
        port=port or int(os.environ.get("PARSUB_API_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
