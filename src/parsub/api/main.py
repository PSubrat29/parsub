"""
FastAPI interface for ParSub.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import sys
from pathlib import Path
import json
import os

# Add src to path so we can import parsub modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from parsub.parser.latex_parser import parse_latex_source
from parsub.analyzer.expression_analyzer import analyze_expressions
from parsub.generator.code_generator import generate_code_from_tasks

app = FastAPI(
    title="ParSub API",
    description="Agentic Math/Physics research tool for LaTeX analysis and numerical evaluation",
    version="0.1.0"
)

# Pydantic models
class LaTeXInput(BaseModel):
    latex_source: str
    output_dir: Optional[str] = "./output"

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    expressions_found: int
    tasks_generated: int
    generated_code_path: Optional[str] = None
    extracted_info: Optional[Dict[str, Any]] = None

class ExecutionResponse(BaseModel):
    success: bool
    message: str
    output_files: List[str] = []

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_latex(input_data: LaTeXInput):
    """
    Analyze LaTeX source and generate Python code for numerical evaluation.
    """
    try:
        # Parse LaTeX
        parsed_result = parse_latex_source(input_data.latex_source)

        # Analyze expressions
        analyzed_tasks = analyze_expressions(
            parsed_result.get('expressions', []),
            {
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])
            }
        )

        # Generate code
        code_file = generate_code_from_tasks(analyzed_tasks, input_data.output_dir)

        return AnalysisResponse(
            success=True,
            message="Analysis completed successfully",
            expressions_found=len(parsed_result.get('expressions', [])),
            tasks_generated=len(analyzed_tasks),
            generated_code_path=code_file,
            extracted_info={
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])[:5]  # Limit to first 5
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/upload", response_model=AnalysisResponse)
async def upload_latex_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_dir: str = "./output"
):
    """
    Upload and analyze a LaTeX file.
    """
    try:
        # Check file extension
        if not file.filename.endswith(('.tex', '.latex', '.ltx')):
            raise HTTPException(status_code=400, detail="File must be a LaTeX file (.tex, .latex, .ltx)")

        # Read file content
        content = await file.read()
        latex_source = content.decode('utf-8')

        # Analyze (reuse the analyze endpoint logic)
        parsed_result = parse_latex_source(latex_source)
        analyzed_tasks = analyze_expressions(
            parsed_result.get('expressions', []),
            {
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])
            }
        )
        code_file = generate_code_from_tasks(analyzed_tasks, output_dir)

        return AnalysisResponse(
            success=True,
            message=f"File '{file.filename}' analyzed successfully",
            expressions_found=len(parsed_result.get('expressions', [])),
            tasks_generated=len(analyzed_tasks),
            generated_code_path=code_file,
            extracted_info={
                'goals': parsed_result.get('goals', []),
                'methods': parsed_result.get('methods', []),
                'parameters': parsed_result.get('parameters', [])[:5]
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)}")

@app.get("/execute/{code_path:path}")
async def execute_generated_code(code_path: str, background_tasks: BackgroundTasks):
    """
    Execute previously generated code (for demonstration - in production, use proper job queues).
    """
    try:
        # Security check - only allow files in output directory
        if not code_path.startswith("./output/"):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(code_path):
            raise HTTPException(status_code=404, detail="Code file not found")

        # In a real implementation, this would use a background task queue
        # For now, we'll return instructions
        return {
            "message": "Code execution initiated. Check output directory for results.",
            "code_path": code_path,
            "instructions": f"Run: python {code_path} --output-dir ./output"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """
    Download generated files (plots, data, etc.).
    """
    try:
        # Security check
        if not file_path.startswith("./output/"):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ParSub API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)