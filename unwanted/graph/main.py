"""
FastAPI Backend for CodeNova AI - Java Refactoring Engine
===========================================================
Exposes the Java refactoring engine through REST API endpoints.
Enables IDE integration for real-time code analysis and refactoring.

Requirements:
- fastapi
- uvicorn
- pydantic

Install: pip install fastapi uvicorn pydantic
Run: python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from pathlib import Path

import sys
from pathlib import Path
#diff view
from uuid import uuid4
from difflib import unified_diff

#dependency graph
from dependency_service import DependencyService

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from refactoring_engine import (
    JavaRefactoringEngine,
    RefactoringResult,
    RefactoringAction,
)
from ast_parser import JavaASTParser, CodeMetrics
from error_checker import ErrorChecker, JavaError, ErrorType, ErrorSeverity

# Initialize FastAPI app
app = FastAPI(
    title="CodeNova AI - Java Refactoring Engine API",
    description="REST API for intelligent Java code refactoring and analysis",
    version="1.1.0"
)

# Enable CORS for VSCodium communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (localhost in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Pydantic Models ====================

class RefactoringRequest(BaseModel):
    """Request model for refactoring endpoint."""
    java_code: str
    apply_all: bool = False
    selected_refactorings: Optional[List[str]] = None
    
    class Config:
        example = {
            "java_code": "public class MyClass { public void longMethod() { ... } }",
            "apply_all": True,
            "selected_refactorings": None
        }


class AnalysisRequest(BaseModel):
    """Request model for code analysis endpoint."""
    java_code: str
    
    class Config:
        example = {
            "java_code": "public class MyClass { public void method() { ... } }"
        }


class ErrorCheckRequest(BaseModel):
    """Request model for error checking endpoint."""
    java_code: str
    
    class Config:
        example = {
            "java_code": "public class MyClass { ... }"
        }


class RefactoringActionResponse(BaseModel):
    """Response model for individual refactoring action."""
    action_type: str
    description: str
    original_code: str
    refactored_code: str
    file_path: Optional[str] = None
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    line_start: int = 0
    line_end: int = 0


class CodeMetricsResponse(BaseModel):
    """Response model for code metrics."""
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    total_methods: int
    total_classes: int
    total_fields: int
    avg_method_length: float
    max_method_length: int
    avg_complexity: float
    max_complexity: int
    max_nesting: int
    duplicate_blocks: int
    long_methods: int
    large_classes: int


class RefactoringResponse(BaseModel):
    """Response model for refactoring operation."""
    success: bool
    original_code: str
    refactored_code: str
    actions: List[RefactoringActionResponse]
    metrics_before: Dict[str, Any]
    metrics_after: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    summary: Dict[str, Any]


class CodeSmell(BaseModel):
    """Model for detected code smell."""
    type: str
    description: str
    severity: str
    class_name: Optional[str] = None
    method_name: Optional[str] = None


class RefactoringOpportunity(BaseModel):
    """Model for refactoring opportunity."""
    type: str
    description: str
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    recommendation: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response model for code analysis."""
    code_smells: List[CodeSmell]
    refactoring_opportunities: List[RefactoringOpportunity]
    metrics: Dict[str, Any]


class JavaErrorResponse(BaseModel):
    """Response model for detected errors."""
    line: int
    column: int
    error_type: str
    severity: str
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None


class ErrorCheckResponse(BaseModel):
    """Response model for error checking."""
    has_errors: bool
    syntax_errors: List[JavaErrorResponse]
    runtime_errors: List[JavaErrorResponse]
    warnings: List[JavaErrorResponse]
    
#diff view    
class ReviewSessionRequest(BaseModel):
    java_code: str
    file_path: str
    selected_refactorings: Optional[List[str]] = None


class ReviewDecisionRequest(BaseModel):
    session_id: str
    action: str  # accept | reject | refactor_again


# ==================== Helper Functions ====================

def convert_metrics_to_dict(metrics: CodeMetrics) -> Dict[str, Any]:
    """Convert CodeMetrics object to dictionary."""
    if isinstance(metrics, dict):
        return metrics
    return metrics.to_dict() if hasattr(metrics, 'to_dict') else {
        'total_lines': 0,
        'code_lines': 0,
        'comment_lines': 0,
        'blank_lines': 0,
        'total_methods': 0,
        'total_classes': 0,
        'total_fields': 0,
        'avg_method_length': 0.0,
        'max_method_length': 0,
        'avg_complexity': 0.0,
        'max_complexity': 0,
        'max_nesting': 0,
        'duplicate_blocks': 0,
        'long_methods': 0,
        'large_classes': 0
    }


def convert_actions_to_response(actions: List[RefactoringAction]) -> List[RefactoringActionResponse]:
    """Convert RefactoringAction objects to response format."""
    response_actions = []
    for action in actions:
        action_dict = action.to_dict() if hasattr(action, 'to_dict') else action.__dict__
        response_actions.append(RefactoringActionResponse(**action_dict))
    return response_actions

#diff view
REVIEW_SESSIONS: Dict[str, Dict[str, Any]] = {}


def generate_diff(old: str, new: str) -> str:
    return "\n".join(
        unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="original",
            tofile="refactored",
            lineterm="",
        )
    )
# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "CodeNova AI - Java Refactoring Engine",
        "version": "1.1.0",
        "status": "running",
        "endpoints": {
            "refactor": "/refactor (POST)",
            "analyze": "/analyze (POST)",
            "check_errors": "/check-errors (POST)",
            "health": "/health (GET)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "engine": "ready",
        "timestamp": str(Path.cwd())
    }


@app.post("/refactor", response_model=RefactoringResponse)
async def refactor_code(request: RefactoringRequest):
    """
    Main refactoring endpoint.
    
    Parameters:
    - java_code: Java source code to refactor
    - apply_all: Apply all suggested refactorings (default: false)
    - selected_refactorings: List of specific refactoring types to apply
    
    Returns:
    - Refactored code with metrics and action details
    """
    try:
        if not request.java_code or len(request.java_code.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Java code cannot be empty"
            )
        
        # Initialize refactoring engine
        engine = JavaRefactoringEngine()
        
        # Perform refactoring
        result: RefactoringResult = engine.refactor(
            code=request.java_code,
            apply_all=request.apply_all,
            selected_refactorings=request.selected_refactorings
        )
        
        # Convert metrics
        metrics_before = convert_metrics_to_dict(result.metrics_before)
        metrics_after = convert_metrics_to_dict(result.metrics_after)
        
        # Convert actions
        response_actions = convert_actions_to_response(result.actions)
        
        # Build response
        summary = result.get_summary() if hasattr(result, 'get_summary') else {}
        
        return RefactoringResponse(
            success=result.success,
            original_code=result.original_code,
            refactored_code=result.refactored_code,
            actions=response_actions,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            warnings=result.warnings,
            errors=result.errors,
            summary=summary
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refactoring error: {str(e)}"
        )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_code(request: AnalysisRequest):
    """
    Analyze Java code for refactoring opportunities.
    
    Parameters:
    - java_code: Java source code to analyze
    
    Returns:
    - Code smells detected
    - Refactoring opportunities
    - Code metrics
    """
    try:
        if not request.java_code or len(request.java_code.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Java code cannot be empty"
            )
        
        # Initialize engine and analyze
        engine = JavaRefactoringEngine()
        analysis = engine.analyze_code(request.java_code)
        
        # Convert code smells
        code_smells_response = []
        for smell in analysis.get('code_smells', []):
            smell_dict = smell if isinstance(smell, dict) else smell.__dict__
            code_smells_response.append(CodeSmell(**smell_dict))
        
        # Convert opportunities
        opportunities_response = []
        for opp in analysis.get('refactoring_opportunities', []):
            opp_dict = opp if isinstance(opp, dict) else opp.__dict__
            opp_dict['class_name'] = opp_dict.get('class')
            opportunities_response.append(RefactoringOpportunity(**opp_dict))
        
        # Convert metrics
        metrics = convert_metrics_to_dict(analysis.get('metrics', {}))
        
        return AnalysisResponse(
            code_smells=code_smells_response,
            refactoring_opportunities=opportunities_response,
            metrics=metrics
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis error: {str(e)}"
        )


@app.post("/check-errors", response_model=ErrorCheckResponse)
async def check_errors(request: ErrorCheckRequest):
    """
    Check Java code for syntax and runtime errors.
    
    Parameters:
    - java_code: Java source code to check
    
    Returns:
    - Detected syntax errors
    - Potential runtime errors
    - Code quality warnings
    """
    try:
        if not request.java_code or len(request.java_code.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Java code cannot be empty"
            )
        
        # Initialize error checker
        error_checker = ErrorChecker()
        
        # Check for errors
        syntax_errors = error_checker.check_syntax(request.java_code)
        runtime_errors = error_checker.check_runtime_errors(request.java_code)
        warnings = error_checker.check_warnings(request.java_code)
        
        # Convert errors
        def convert_errors(errors: List[JavaError]) -> List[JavaErrorResponse]:
            response = []
            for error in errors:
                error_dict = error.to_dict() if hasattr(error, 'to_dict') else error.__dict__
                response.append(JavaErrorResponse(**error_dict))
            return response
        
        syntax_errors_response = convert_errors(syntax_errors)
        runtime_errors_response = convert_errors(runtime_errors)
        warnings_response = convert_errors(warnings)
        
        has_errors = len(syntax_errors_response) > 0 or len(runtime_errors_response) > 0
        
        return ErrorCheckResponse(
            has_errors=has_errors,
            syntax_errors=syntax_errors_response,
            runtime_errors=runtime_errors_response,
            warnings=warnings_response
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking failed: {str(e)}"
        )

# diff view
@app.post("/refactor/review")
async def refactor_review(request: ReviewSessionRequest):
    engine = JavaRefactoringEngine()

    result = engine.refactor(
        code=request.java_code,
        apply_all=True,
        selected_refactorings=request.selected_refactorings,
    )

    session_id = str(uuid4())
    diff = generate_diff(result.original_code, result.refactored_code)

    REVIEW_SESSIONS[session_id] = {
        "file_path": request.file_path,
        "original_code": result.original_code,
        "refactored_code": result.refactored_code,
        "selected_refactorings": request.selected_refactorings,
    }

    return {
        "session_id": session_id,
        "status": "review",
        "diff": diff,
        "refactored_code": result.refactored_code,
    }

#accept/reject endpoint
@app.post("/refactor/decision")
async def review_decision(request: ReviewDecisionRequest):
    session = REVIEW_SESSIONS.get(request.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if request.action == "accept":
        file_path = Path(session["file_path"])
        file_path.write_text(session["refactored_code"], encoding="utf-8")

        final_code = session["refactored_code"]
        del REVIEW_SESSIONS[request.session_id]

        return {
            "status": "accepted",
            "final_code": final_code,
        }

    if request.action == "reject":
        final_code = session["original_code"]
        del REVIEW_SESSIONS[request.session_id]

        return {
            "status": "rejected",
            "final_code": final_code,
        }

    if request.action == "refactor_again":
        engine = JavaRefactoringEngine()
        result = engine.refactor(code=session["original_code"], apply_all=True)

        session["refactored_code"] = result.refactored_code
        diff = generate_diff(result.original_code, result.refactored_code)

        return {
            "status": "review",
            "session_id": request.session_id,
            "diff": diff,
            "refactored_code": result.refactored_code,
        }
        
#dependency graph
@app.post("/dependency-graph")
async def dependency_graph(request: AnalysisRequest):
    parser = JavaASTParser()
    parser.load_code(request.java_code)
    parser.build_ast()

    dependencies = parser.extract_file_dependencies("CurrentFile.java")
    metrics = parser.get_metrics().to_dict()

    service = DependencyService()

    graph_data = service.build_graph_response(
        dependencies,
        {"CurrentFile.java": metrics}
    )

    return {
        "success": True,
        "graph": graph_data
    }
    
#radar chart
@app.post("/file-radar")
async def file_radar(request: AnalysisRequest):
    parser = JavaASTParser()
    parser.load_code(request.java_code)
    parser.build_ast()

    metrics = parser.get_metrics().to_dict()

    return {
        "file": "CurrentFile.java",
        "radar": {
            "maintainability": 100 - metrics.get("avg_complexity", 0),
            "complexity": metrics.get("avg_complexity", 0),
            "loc": metrics.get("code_lines", 0),
            "methods": metrics.get("total_methods", 0)
        }
    }
# ==================== Utility Endpoints ====================

@app.get("/stats")
async def get_stats():
    """Get statistics about the refactoring engine."""
    return {
        "engine": "JavaRefactoringEngine v1.1.0",
        "capabilities": [
            "extract_method",
            "reduce_nesting",
            "remove_duplicates",
            "decompose_behavior",
            "change_structure"
        ],
        "analysis_features": [
            "code_smell_detection",
            "refactoring_opportunities",
            "code_metrics",
            "error_detection"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    # Run with: python main.py
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

