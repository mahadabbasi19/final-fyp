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
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import os
import re
import logging
from pathlib import Path
from uuid import uuid4
from difflib import unified_diff

import sys
from pathlib import Path

logger = logging.getLogger("codenova")

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from refactoring_engine import (
    JavaRefactoringEngine,
    RefactoringResult,
    RefactoringAction,
)
from ast_parser import JavaASTParser, CodeMetrics
from error_checker import ErrorChecker, JavaError, ErrorType, ErrorSeverity
from metrics import (
    HalsteadCalculator,
    MaintainabilityIndexCalculator,
    MetricsCollector,
    CodeHealthDashboard,
    CouplingCohesionCalculator,
)
from git_manager import GitManager, GitManagerError, NotARepoError

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
    safety_score: float = 1.0
    transformation_type: str = "Deterministic"
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


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "CodeNova AI - Java Refactoring Engine",
        "version": "2.0.0",
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
        
        # Engine returns 'opportunities' — split into smells + opportunities for UI
        all_opportunities = analysis.get('opportunities', [])
        
        # Convert code smells (deterministic findings = smells)
        code_smells_response = []
        for opp in all_opportunities:
            smell_dict = dict(opp) if isinstance(opp, dict) else dict(opp.__dict__)
            severity = 'warning'
            if smell_dict.get('safety_score', 0) >= 1.0:
                severity = 'error'
            elif smell_dict.get('safety_score', 0) >= 0.8:
                severity = 'warning'
            else:
                severity = 'info'
            # Remap keys
            if 'class' in smell_dict:
                smell_dict['class_name'] = smell_dict.pop('class')
            if 'method' in smell_dict:
                smell_dict['method_name'] = smell_dict.pop('method')
            if 'description' not in smell_dict:
                smell_dict['description'] = smell_dict.get('recommendation', smell_dict.get('type', 'Code smell detected'))
            smell_dict['severity'] = severity
            valid_keys = {'type', 'description', 'severity', 'class_name', 'method_name'}
            smell_dict = {k: v for k, v in smell_dict.items() if k in valid_keys}
            code_smells_response.append(CodeSmell(**smell_dict))
        
        # Convert opportunities (heuristic findings = refactoring opportunities)
        opportunities_response = []
        for opp in all_opportunities:
            opp_dict = dict(opp) if isinstance(opp, dict) else dict(opp.__dict__)
            if 'class' in opp_dict:
                opp_dict['class_name'] = opp_dict.pop('class')
            if 'method' in opp_dict:
                opp_dict['method_name'] = opp_dict.pop('method')
            if 'description' not in opp_dict:
                opp_dict['description'] = opp_dict.get('recommendation', opp_dict.get('type', 'Refactoring opportunity'))
            valid_keys = {'type', 'description', 'class_name', 'method_name', 'recommendation'}
            opp_dict = {k: v for k, v in opp_dict.items() if k in valid_keys}
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
        
        # Check for all errors at once (ErrorChecker.check_code returns combined list)
        all_errors = error_checker.check_code(request.java_code, include_warnings=True)
        
        # Convert and split by error_type
        def convert_error(error: JavaError) -> JavaErrorResponse:
            error_dict = error.to_dict() if hasattr(error, 'to_dict') else error.__dict__
            # to_dict() uses 'type' key but Pydantic model expects 'error_type'
            if 'type' in error_dict and 'error_type' not in error_dict:
                error_dict['error_type'] = error_dict.pop('type')
            # Ensure enum values are strings
            if hasattr(error_dict.get('error_type'), 'value'):
                error_dict['error_type'] = error_dict['error_type'].value
            if hasattr(error_dict.get('severity'), 'value'):
                error_dict['severity'] = error_dict['severity'].value
            return JavaErrorResponse(**error_dict)
        
        syntax_errors_response = [convert_error(e) for e in all_errors
                                   if getattr(e, 'error_type', None) and
                                   (e.error_type.value if hasattr(e.error_type, 'value') else e.error_type) == 'syntax']
        runtime_errors_response = [convert_error(e) for e in all_errors
                                    if getattr(e, 'error_type', None) and
                                    (e.error_type.value if hasattr(e.error_type, 'value') else e.error_type) == 'runtime']
        warnings_response = [convert_error(e) for e in all_errors
                              if getattr(e, 'error_type', None) and
                              (e.error_type.value if hasattr(e.error_type, 'value') else e.error_type) in ('warning', 'info')]
        
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


# ==================== Diff / Review Session Management ====================

REVIEW_SESSIONS: Dict[str, Dict[str, Any]] = {}


def generate_diff(old: str, new: str) -> str:
    """Generate unified diff between original and refactored code."""
    return "\n".join(
        unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="original",
            tofile="refactored",
            lineterm="",
        )
    )


class ReviewSessionRequest(BaseModel):
    java_code: str
    file_path: Optional[str] = None
    selected_refactorings: Optional[List[str]] = None


class ReviewDecisionRequest(BaseModel):
    session_id: str
    action: str  # "accept" | "reject"


@app.post("/refactor/review")
async def refactor_review(request: ReviewSessionRequest):
    """Create a refactoring review session with diff preview."""
    try:
        if not request.java_code or len(request.java_code.strip()) == 0:
            raise HTTPException(status_code=400, detail="Java code cannot be empty")

        engine = JavaRefactoringEngine()
        result = engine.refactor(
            code=request.java_code,
            apply_all=True,
            selected_refactorings=request.selected_refactorings,
        )

        session_id = str(uuid4())
        diff = generate_diff(result.original_code, result.refactored_code)

        # Convert metrics
        metrics_before = convert_metrics_to_dict(result.metrics_before)
        metrics_after = convert_metrics_to_dict(result.metrics_after)

        # Convert actions
        response_actions = []
        for action in result.actions:
            action_dict = action.to_dict() if hasattr(action, 'to_dict') else action.__dict__
            response_actions.append(action_dict)

        REVIEW_SESSIONS[session_id] = {
            "original_code": result.original_code,
            "refactored_code": result.refactored_code,
        }

        return {
            "session_id": session_id,
            "status": "review",
            "diff": diff,
            "original_code": result.original_code,
            "refactored_code": result.refactored_code,
            "actions": response_actions,
            "metrics_before": metrics_before,
            "metrics_after": metrics_after,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review error: {str(e)}")


@app.post("/refactor/decision")
async def review_decision(request: ReviewDecisionRequest):
    """Accept or reject a refactoring review session."""
    session = REVIEW_SESSIONS.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if request.action == "accept":
        final_code = session["refactored_code"]
        del REVIEW_SESSIONS[request.session_id]
        return {"status": "accepted", "final_code": final_code}

    if request.action == "reject":
        final_code = session["original_code"]
        del REVIEW_SESSIONS[request.session_id]
        return {"status": "rejected", "final_code": final_code}

    raise HTTPException(status_code=400, detail="Invalid action. Use 'accept' or 'reject'.")


# ==================== Dependency Graph Endpoint ====================

class DependencyGraphRequest(BaseModel):
    java_code: str


@app.post("/dependency-graph")
async def dependency_graph(request: DependencyGraphRequest):
    """Analyze Java code and return dependency graph nodes/edges + radar metrics."""
    try:
        if not request.java_code or len(request.java_code.strip()) == 0:
            raise HTTPException(status_code=400, detail="Java code cannot be empty")

        parser = JavaASTParser()
        parser.load_code(request.java_code)
        try:
            parser.build_ast()
            parser.extract_all()
        except Exception:
            pass

        metrics = convert_metrics_to_dict(parser.metrics if hasattr(parser, 'metrics') else {})

        # Build nodes from classes
        nodes = []
        edges = []
        classes = parser.classes if hasattr(parser, 'classes') else []

        for cls in classes:
            cls_name = cls.get('name', cls) if isinstance(cls, dict) else getattr(cls, 'name', str(cls))
            complexity = metrics.get('avg_complexity', 0)
            nodes.append({
                "id": cls_name,
                "label": cls_name,
                "complexity": complexity,
                "maintainability": max(0, 100 - complexity * 10),
                "loc": metrics.get('code_lines', 0),
            })

        # Build edges from method calls / field references between classes
        methods = parser.methods if hasattr(parser, 'methods') else []
        for method in methods:
            m_name = method.get('name', method) if isinstance(method, dict) else getattr(method, 'name', str(method))
            m_class = method.get('class_name', '') if isinstance(method, dict) else getattr(method, 'class_name', '')
            if m_class:
                # self reference for method grouping
                edges.append({"source": m_class, "target": m_name, "type": "has_method"})

        # Radar chart data (Maintainability vs Complexity dims)
        total_lines = metrics.get('total_lines', 0)
        code_lines = metrics.get('code_lines', 0)
        avg_complexity = metrics.get('avg_complexity', 0)
        max_complexity = metrics.get('max_complexity', 0)
        max_nesting = metrics.get('max_nesting', 0)
        total_methods = metrics.get('total_methods', 0)
        long_methods = metrics.get('long_methods', 0)
        duplicate_blocks = metrics.get('duplicate_blocks', 0)

        # Normalize to 0-100 scale for radar chart
        radar = {
            "labels": ["Maintainability", "Simplicity", "Readability", "Modularity", "Duplication Free"],
            "values": [
                max(0, min(100, 100 - avg_complexity * 10)),    # Maintainability
                max(0, min(100, 100 - max_complexity * 5)),      # Simplicity
                max(0, min(100, 100 - max_nesting * 15)),        # Readability
                max(0, min(100, min(total_methods, 10) * 10)),   # Modularity
                max(0, min(100, 100 - duplicate_blocks * 20)),   # Duplication Free
            ]
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": metrics,
            "radar": radar,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")


# ==================== Multi-File Dependency Graph ====================

class MultiFileDependencyRequest(BaseModel):
    files: Dict[str, str]  # { relative_path: java_code }


@app.post("/dependency-graph/multi")
async def multi_file_dependency_graph(request: MultiFileDependencyRequest):
    """
    Analyze multiple Java files and return cross-file dependency graph.
    Detects: extends, implements, type references, method calls between files.
    """
    try:
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided")

        file_classes: Dict[str, List[str]] = {}   # file -> [class names]
        class_to_file: Dict[str, str] = {}        # class_name -> file_path
        all_extends: Dict[str, str] = {}           # class_name -> extends
        all_implements: Dict[str, List[str]] = {}  # class_name -> [implements]
        all_references: Dict[str, set] = {}        # class_name -> {referenced types}
        file_metrics: Dict[str, dict] = {}         # file -> metrics dict

        for file_path, code in request.files.items():
            if not code or not code.strip():
                continue
            try:
                parser = JavaASTParser()
                parser.load_code(code)
                parser.build_ast()
                parser.extract_all()

                classes_in_file = []
                for cls in (parser.classes if hasattr(parser, 'classes') else []):
                    cls_name = cls.get('name') if isinstance(cls, dict) else getattr(cls, 'name', str(cls))
                    classes_in_file.append(cls_name)
                    class_to_file[cls_name] = file_path

                    # Extract extends/implements
                    ext = cls.get('extends') if isinstance(cls, dict) else getattr(cls, 'extends', None)
                    impl = cls.get('implements', []) if isinstance(cls, dict) else getattr(cls, 'implements', [])
                    if ext:
                        all_extends[cls_name] = ext
                    if impl:
                        all_implements[cls_name] = impl

                file_classes[file_path] = classes_in_file

                # Extract type references via regex (field types, parameters, new, instanceof)
                refs = set()
                type_patterns = [
                    r'\bnew\s+([A-Z]\w+)\s*\(',        # new ClassName(
                    r'\b([A-Z]\w+)\s+\w+\s*[=;,)]',     # ClassName varName
                    r'\b([A-Z]\w+)\.\w+\s*\(',           # ClassName.method(
                    r'instanceof\s+([A-Z]\w+)',           # instanceof ClassName
                    r'<([A-Z]\w+)>',                      # generic <ClassName>
                    r'catch\s*\(\s*([A-Z]\w+)',           # catch (ClassName
                ]
                for pat in type_patterns:
                    for m in re.finditer(pat, code):
                        refs.add(m.group(1))

                for cls_name in classes_in_file:
                    all_references[cls_name] = refs - set(classes_in_file) - {
                        'String', 'Integer', 'Double', 'Float', 'Boolean',
                        'Long', 'Short', 'Byte', 'Character', 'Object',
                        'List', 'Map', 'Set', 'ArrayList', 'HashMap',
                        'HashSet', 'Exception', 'Override', 'System',
                        'Math', 'Arrays', 'Collections', 'Scanner',
                    }

                metrics = convert_metrics_to_dict(parser.metrics if hasattr(parser, 'metrics') else {})
                file_metrics[file_path] = metrics

            except Exception:
                file_classes[file_path] = []
                file_metrics[file_path] = {}

        # Build nodes (one per file)
        nodes = []
        for fp, cls_list in file_classes.items():
            m = file_metrics.get(fp, {})
            nodes.append({
                "id": fp,
                "label": fp.split('/')[-1].split('\\')[-1],
                "path": fp,
                "classes": cls_list,
                "loc": m.get('code_lines', 0),
                "methods": m.get('total_methods', 0),
                "complexity": m.get('avg_complexity', 0),
            })

        # Build edges
        edges = []
        seen_edges = set()

        def add_edge(src_file, tgt_file, edge_type, label=""):
            key = (src_file, tgt_file, edge_type)
            if key not in seen_edges and src_file != tgt_file:
                seen_edges.add(key)
                edges.append({
                    "source": src_file,
                    "target": tgt_file,
                    "type": edge_type,
                    "label": label,
                })

        # Extends edges
        for cls_name, parent in all_extends.items():
            src_file = class_to_file.get(cls_name)
            tgt_file = class_to_file.get(parent)
            if src_file and tgt_file:
                add_edge(src_file, tgt_file, "extends", f"{cls_name} extends {parent}")

        # Implements edges
        for cls_name, ifaces in all_implements.items():
            src_file = class_to_file.get(cls_name)
            for iface in ifaces:
                tgt_file = class_to_file.get(iface)
                if src_file and tgt_file:
                    add_edge(src_file, tgt_file, "implements", f"{cls_name} implements {iface}")

        # Reference/usage edges
        for cls_name, refs in all_references.items():
            src_file = class_to_file.get(cls_name)
            if not src_file:
                continue
            for ref in refs:
                tgt_file = class_to_file.get(ref)
                if tgt_file:
                    add_edge(src_file, tgt_file, "uses", f"{cls_name} uses {ref}")

        return {
            "nodes": nodes,
            "edges": edges,
            "file_count": len(nodes),
            "edge_count": len(edges),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-file graph error: {str(e)}")


# ==================== Refactoring History ====================

REFACTORING_HISTORY: List[Dict[str, Any]] = []


class RefactoringHistoryEntry(BaseModel):
    timestamp: str
    file_path: Optional[str] = None
    actions: List[Dict[str, Any]] = []
    original_code: str
    refactored_code: str
    metrics_before: Dict[str, Any] = {}
    metrics_after: Dict[str, Any] = {}


@app.get("/refactoring/history")
async def get_refactoring_history():
    """Return saved refactoring history."""
    return {"history": REFACTORING_HISTORY}


@app.post("/refactoring/history")
async def save_refactoring_history(entry: RefactoringHistoryEntry):
    """Save a refactoring history entry."""
    REFACTORING_HISTORY.insert(0, entry.dict())
    # Keep max 50 entries
    if len(REFACTORING_HISTORY) > 50:
        REFACTORING_HISTORY.pop()
    return {"success": True, "count": len(REFACTORING_HISTORY)}


@app.delete("/refactoring/history")
async def clear_refactoring_history():
    """Clear all refactoring history."""
    REFACTORING_HISTORY.clear()
    return {"success": True}


# ==================== Multi-File Rename ====================

class RenameSymbolRequest(BaseModel):
    root_path: str
    old_name: str
    new_name: str


@app.post("/rename-symbol")
async def rename_symbol(request: RenameSymbolRequest):
    """
    Find & replace a symbol name across all Java files in a project.
    Uses word-boundary matching to avoid partial replacements.
    Returns list of files modified.
    """
    try:
        import glob as glob_mod

        root = request.root_path
        old_name = request.old_name.strip()
        new_name = request.new_name.strip()

        if not old_name or not new_name:
            raise HTTPException(status_code=400, detail="Symbol names cannot be empty")
        if old_name == new_name:
            return {"modified_files": [], "count": 0}

        # Word-boundary regex for the symbol
        pattern = re.compile(r'\b' + re.escape(old_name) + r'\b')

        java_files = glob_mod.glob(os.path.join(root, '**', '*.java'), recursive=True)
        modified = []

        for fp in java_files:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                new_content, count = pattern.subn(new_name, content)
                if count > 0:
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    modified.append({
                        "path": fp,
                        "relative_path": os.path.relpath(fp, root),
                        "replacements": count,
                    })
            except Exception:
                continue

        return {"modified_files": modified, "count": len(modified)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename error: {str(e)}")


# ==================== CodeNova AI Chat ====================

# ---------- OpenAI Configuration ----------

_openai_api_key = os.environ.get("OPENAI_API_KEY", "") or "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"

def _get_openai_client():
    """Return an OpenAI client."""
    from openai import OpenAI
    if not _openai_api_key:
        raise HTTPException(status_code=503, detail="No OpenAI API key available.")
    return OpenAI(api_key=_openai_api_key)


# ---------- System Prompt ----------

CODENOVA_SYSTEM_PROMPT = """\
You are **CodeNova AI**, the built-in intelligent assistant for the CodeNova Java IDE.
Your personality: professional, concise, safety-first.

### CAPABILITIES
1. **CODE GENERATION** – create new classes, methods, boilerplate, or explain logic.
   Always wrap code in ```java blocks.
2. **SECURE REFACTORING (Engine Delegation)** – when the user asks to "clean,"
   "simplify," "refactor," or "fix" *existing* code you MUST tell the user you
   will delegate to the CodeNova Deterministic Refactoring Engine.
   Respond with the exact phrase:
     ENGINE_DELEGATE: <comma-separated refactoring types>
   Valid types: dead_code_removal, unused_import_removal, condition_simplification,
                reduce_nesting, extract_method, remove_duplicates,
                decompose_behavior, change_structure
   Example: ENGINE_DELEGATE: dead_code_removal, unused_import_removal
3. **METRICS-DRIVEN ADVICE** – reference the provided metrics. If
   avg_complexity > 10, recommend "decompose_behavior". If MI < 65, flag
   it as CRITICAL.

### RULES
- ALWAYS prefer behaviour-preserving transforms.
- If the request is ambiguous, ask: "Would you like me to generate a new
  implementation or refactor the existing structure using the safety engine?"
- Never invent metrics – use only the values provided in <METRICS>.
- Keep responses concise.
"""


# ---------- Intent Classifier ----------

_REFACTOR_KEYWORDS = re.compile(
    r'\b(refactor|clean|simplify|optimize|fix|remove\s+dead|unused\s+imports?|'
    r'reduce\s+nesting|extract\s+method|remove\s+duplicates?|decompose|split\s+class|'
    r'change\s+structure)\b',
    re.IGNORECASE,
)

_REFACTORING_TYPE_MAP: Dict[str, str] = {
    'dead': 'dead_code_removal',
    'unused': 'unused_import_removal',
    'simplif': 'condition_simplification',
    'nesting': 'reduce_nesting',
    'extract': 'extract_method',
    'duplicate': 'remove_duplicates',
    'decompose': 'decompose_behavior',
    'split': 'change_structure',
    'structure': 'change_structure',
}


def _detect_refactoring_types(text: str) -> List[str]:
    """Map LLM output or user query to concrete refactoring type keys."""
    types: List[str] = []
    lower = text.lower()
    for keyword, rtype in _REFACTORING_TYPE_MAP.items():
        if keyword in lower and rtype not in types:
            types.append(rtype)
    return types


_METRICS_KEYWORDS = re.compile(
    r'\b(metrics?|health|complexity|maintainab|dashboard|analyz|quality|halstead)\b',
    re.IGNORECASE,
)


# ---------- Pydantic Models ----------

class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""
    user_message: str = Field(..., min_length=1, max_length=10000)
    code: Optional[str] = Field(None, max_length=100000)
    file_path: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the /chat endpoint."""
    reply: str
    mode: str                                 # "generation" | "refactoring" | "advice"
    new_code: Optional[str] = None
    refactoring_actions: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    health_dashboard: Optional[Dict[str, Any]] = None


class HealthDashboardRequest(BaseModel):
    java_code: str


# ---------- /chat Endpoint ----------

@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    Natural-language assistant endpoint.

    Routing priority (Gemini is NEVER required for refactoring/metrics):
      1. REFACTORING intent  → local engine  (no LLM)
      2. METRICS / HEALTH    → local metrics  (no LLM)
      3. Everything else     → Gemini LLM  (requires API key)
    """
    try:
        # --- 1. Analyse provided code (optional) -----------------------
        metrics_dict: Dict[str, Any] = {}
        dashboard: Optional[Dict[str, Any]] = None
        code = (request.code or "").strip()

        if code:
            parser = JavaASTParser()
            parser.load_code(code)
            try:
                parser.build_ast()
                parser.extract_all()
                metrics_dict = convert_metrics_to_dict(parser.metrics)
            except Exception:
                metrics_dict = {}

            # Build health dashboard if we have metrics
            if metrics_dict:
                collector = MetricsCollector()
                snapshot = collector.create_snapshot(metrics_dict, source_code=code)
                coupling = CouplingCohesionCalculator.calculate_coupling(code)
                cohesion = CouplingCohesionCalculator.calculate_cohesion(code)
                dashboard = CodeHealthDashboard.generate(
                    snapshot, coupling=coupling, cohesion=cohesion,
                )

        # --- 2. LOCAL ROUTING: Refactoring intent → engine directly ---
        if code and _REFACTOR_KEYWORDS.search(request.user_message):
            types = _detect_refactoring_types(request.user_message)
            return await _run_engine(
                code, types or [],   # empty list = apply_all
                dashboard,
                preamble=f"Running CodeNova Refactoring Engine ({', '.join(types) or 'all'})...",
            )

        # --- 3. LOCAL ROUTING: Metrics / health intent → dashboard ---
        if code and _METRICS_KEYWORDS.search(request.user_message):
            return _build_metrics_response(
                code, metrics_dict, dashboard, request.user_message,
            )

        # --- 4. LLM ROUTING: everything else → OpenAI ----------------
        try:
            user_parts: List[str] = []
            if code:
                user_parts.append(f"<CODE>\n{code}\n</CODE>")
            if metrics_dict:
                user_parts.append(f"<METRICS>\n{json.dumps(metrics_dict, indent=2)}\n</METRICS>")
            if dashboard:
                user_parts.append(
                    f"<HEALTH category=\"{dashboard['category']}\" "
                    f"MI=\"{dashboard['maintainability_index']}\" "
                    f"health=\"{dashboard['health_score']}\"/>")
            user_parts.append(request.user_message)
            full_user_prompt = "\n\n".join(user_parts)

            client = _get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": CODENOVA_SYSTEM_PROMPT},
                    {"role": "user", "content": full_user_prompt},
                ],
                max_tokens=2048,
            )
            llm_text = response.choices[0].message.content

            # If LLM still says ENGINE_DELEGATE, honour it
            if "ENGINE_DELEGATE" in llm_text and code:
                return await _handle_engine_delegation(llm_text, code, dashboard)

            return ChatResponse(
                reply=llm_text,
                mode="generation" if not code else "advice",
                metrics=metrics_dict or None,
                health_dashboard=dashboard,
            )

        except HTTPException:
            # OpenAI unavailable — provide a helpful local-only reply
            if code:
                return _build_metrics_response(
                    code, metrics_dict, dashboard, request.user_message,
                )
            raise  # no code + no OpenAI = can't help

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def _build_metrics_response(
    code: str,
    metrics_dict: Dict[str, Any],
    dashboard: Optional[Dict[str, Any]],
    user_message: str,
) -> ChatResponse:
    """Build a fully local metrics/advice response (no LLM needed)."""
    lines: List[str] = []

    if dashboard:
        cat = dashboard.get('category', 'UNKNOWN')
        mi = dashboard.get('maintainability_index', 0)
        hs = dashboard.get('health_score', 0)
        lines.append(f"**Code Health: {cat}**  (Health Score: {hs:.1f}, MI: {mi:.1f})")

        if cat == 'CRITICAL':
            lines.append("\n⚠️ This code is in **critical** condition. Consider decomposing large methods and reducing complexity.")
        elif cat == 'WARNING':
            lines.append("\nThis code has some quality concerns. Targeted refactoring could improve maintainability.")
        else:
            lines.append("\nThis code is in good shape!")

    if metrics_dict:
        avg_cc = metrics_dict.get('avg_complexity', 0)
        if avg_cc > 10:
            lines.append(f"\n🔴 **Avg Cyclomatic Complexity: {avg_cc:.1f}** — consider using *Decompose Behavior* to split complex methods.")
        elif avg_cc > 5:
            lines.append(f"\n🟡 **Avg Cyclomatic Complexity: {avg_cc:.1f}** — moderate. Some methods could be simplified.")
        else:
            lines.append(f"\n🟢 **Avg Cyclomatic Complexity: {avg_cc:.1f}** — low complexity, well structured.")

        lines.append(f"\n**Lines of Code:** {metrics_dict.get('total_lines', '-')}")
        lines.append(f"**Methods:** {metrics_dict.get('total_methods', '-')}")
        lines.append(f"**Classes:** {metrics_dict.get('total_classes', '-')}")
        lines.append(f"**Max Nesting:** {metrics_dict.get('max_nesting', '-')}")
        lines.append(f"**Duplicate Blocks:** {metrics_dict.get('duplicate_blocks', '-')}")

    if not lines:
        lines.append("I analysed the code but couldn't compute detailed metrics. Try a different Java file.")

    return ChatResponse(
        reply="\n".join(lines),
        mode="advice",
        metrics=metrics_dict or None,
        health_dashboard=dashboard,
    )


async def _handle_engine_delegation(
    llm_text: str,
    code: str,
    dashboard: Optional[Dict[str, Any]],
) -> ChatResponse:
    """Parse ENGINE_DELEGATE directive and run the refactoring engine."""
    if not code:
        return ChatResponse(
            reply="I would use the refactoring engine, but no code was provided. "
                  "Please paste your Java code and try again.",
            mode="advice",
        )

    # Extract types from the directive line
    match = re.search(r'ENGINE_DELEGATE:\s*(.+)', llm_text)
    types_from_llm = _detect_refactoring_types(match.group(1)) if match else []

    # Strip the directive from the reply sent to the user
    clean_reply = re.sub(
        r'ENGINE_DELEGATE:[^\n]*\n?', '', llm_text
    ).strip()

    return await _run_engine(code, types_from_llm, dashboard,
                             preamble=clean_reply)


async def _run_engine(
    code: str,
    types: List[str],
    dashboard: Optional[Dict[str, Any]],
    preamble: str = "",
) -> ChatResponse:
    """Execute the local refactoring engine and return a ChatResponse."""
    engine = JavaRefactoringEngine()
    result: RefactoringResult = engine.refactor(
        code=code,
        apply_all=len(types) == 0,
        selected_refactorings=types or None,
    )

    actions_dicts = []
    for a in result.actions:
        ad = a.to_dict() if hasattr(a, 'to_dict') else a.__dict__
        actions_dicts.append(ad)

    summary_lines: List[str] = []
    if preamble:
        summary_lines.append(preamble)
    summary_lines.append(
        f"\n**CodeNova Engine** applied **{len(result.actions)}** "
        f"safe refactoring(s) ({', '.join(types) or 'all'})."
    )
    if result.warnings:
        summary_lines.append("\n⚠️ Warnings: " + "; ".join(result.warnings))
    if result.errors:
        summary_lines.append("\n❌ Errors: " + "; ".join(result.errors))

    # Post-refactor metrics
    post_metrics = convert_metrics_to_dict(result.metrics_after)

    return ChatResponse(
        reply="\n".join(summary_lines),
        mode="refactoring",
        new_code=result.refactored_code if result.success else None,
        refactoring_actions=actions_dicts,
        metrics=post_metrics,
        health_dashboard=dashboard,
    )


# ---------- /chat/health-dashboard ----------

@app.post("/chat/health-dashboard")
async def chat_health_dashboard(request: HealthDashboardRequest):
    """
    Standalone endpoint: returns a full Code Health Dashboard (JSON + text)
    for the submitted Java code.
    """
    try:
        code = request.java_code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Java code cannot be empty")

        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            parser.extract_all()
            metrics_dict = convert_metrics_to_dict(parser.metrics)
        except Exception:
            metrics_dict = {}

        collector = MetricsCollector()
        snapshot = collector.create_snapshot(metrics_dict, source_code=code)
        coupling = CouplingCohesionCalculator.calculate_coupling(code)
        cohesion = CouplingCohesionCalculator.calculate_cohesion(code)

        dashboard_json = CodeHealthDashboard.generate(
            snapshot, coupling=coupling, cohesion=cohesion,
        )
        dashboard_text = CodeHealthDashboard.render_text(
            snapshot, coupling=coupling, cohesion=cohesion,
        )

        return {
            "dashboard": dashboard_json,
            "dashboard_text": dashboard_text,
            "snapshot": snapshot.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")


# ========================================================================
# GIT ENDPOINTS
# ========================================================================

# Singleton git manager – repo is opened per request via repo_path
_git_mgr = GitManager()


class GitRepoRequest(BaseModel):
    repo_path: str


class GitStageRequest(BaseModel):
    repo_path: str
    paths: List[str] = ["."]


class GitCommitRequest(BaseModel):
    repo_path: str
    message: str
    author: Optional[str] = None


class GitBranchRequest(BaseModel):
    repo_path: str
    name: str
    checkout: bool = True


class GitSwitchBranchRequest(BaseModel):
    repo_path: str
    name: str


class GitDeleteBranchRequest(BaseModel):
    repo_path: str
    name: str
    force: bool = False


class GitPushRequest(BaseModel):
    repo_path: str
    remote: str = "origin"
    branch: Optional[str] = None
    set_upstream: bool = False


class GitPullRequest(BaseModel):
    repo_path: str
    remote: str = "origin"


class GitDiffRequest(BaseModel):
    repo_path: str
    path: Optional[str] = None
    staged: bool = False


class GitLogRequest(BaseModel):
    repo_path: str
    max_count: int = 50
    file_path: Optional[str] = None


class GitInitRequest(BaseModel):
    path: str


class GitDiscardRequest(BaseModel):
    repo_path: str
    paths: List[str]


class GitStashRequest(BaseModel):
    repo_path: str
    message: Optional[str] = None


def _open_git(repo_path: str) -> GitManager:
    """Open a repo on the singleton GitManager, return it."""
    try:
        _git_mgr.open(repo_path)
        return _git_mgr
    except NotARepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/git/init")
async def git_init(req: GitInitRequest):
    """Initialise a new Git repository."""
    try:
        return _git_mgr.init_repo(req.path)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/status")
async def git_status(req: GitRepoRequest):
    """Get full working-tree status."""
    mgr = _open_git(req.repo_path)
    return mgr.get_status()


@app.post("/git/stage")
async def git_stage(req: GitStageRequest):
    """Stage files."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.stage_files(req.paths)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/stage-all")
async def git_stage_all(req: GitRepoRequest):
    """Stage all changes."""
    mgr = _open_git(req.repo_path)
    return mgr.stage_all()


@app.post("/git/unstage")
async def git_unstage(req: GitStageRequest):
    """Unstage files."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.unstage_files(req.paths)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/discard")
async def git_discard(req: GitDiscardRequest):
    """Discard working-tree changes for files."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.discard_changes(req.paths)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/commit")
async def git_commit(req: GitCommitRequest):
    """Commit staged changes."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.commit(req.message, author=req.author)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/branches")
async def git_branches(req: GitRepoRequest):
    """List branches."""
    mgr = _open_git(req.repo_path)
    return mgr.list_branches()


@app.post("/git/branch/create")
async def git_branch_create(req: GitBranchRequest):
    """Create a new branch."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.create_branch(req.name, checkout=req.checkout)
    except GitManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/git/branch/switch")
async def git_branch_switch(req: GitSwitchBranchRequest):
    """Switch to a branch."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.switch_branch(req.name)
    except GitManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/git/branch/delete")
async def git_branch_delete(req: GitDeleteBranchRequest):
    """Delete a branch."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.delete_branch(req.name, force=req.force)
    except GitManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/git/push")
async def git_push(req: GitPushRequest):
    """Push to remote."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.push_to_remote(req.remote, branch=req.branch, set_upstream=req.set_upstream)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/pull")
async def git_pull(req: GitPullRequest):
    """Pull from remote."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.pull_from_remote(req.remote)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/fetch")
async def git_fetch(req: GitPullRequest):
    """Fetch from remote."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.fetch_remote(req.remote)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/diff")
async def git_diff(req: GitDiffRequest):
    """Get diff of changes."""
    mgr = _open_git(req.repo_path)
    return mgr.get_diff(path=req.path, staged=req.staged)


@app.post("/git/log")
async def git_log(req: GitLogRequest):
    """Get commit log."""
    mgr = _open_git(req.repo_path)
    return mgr.get_log(max_count=req.max_count, file_path=req.file_path)


@app.post("/git/stash/save")
async def git_stash_save(req: GitStashRequest):
    """Stash current changes."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.stash_save(message=req.message)
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/stash/pop")
async def git_stash_pop(req: GitRepoRequest):
    """Pop the most recent stash."""
    mgr = _open_git(req.repo_path)
    try:
        return mgr.stash_pop()
    except GitManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/git/stash/list")
async def git_stash_list(req: GitRepoRequest):
    """List all stash entries."""
    mgr = _open_git(req.repo_path)
    return mgr.stash_list()


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
