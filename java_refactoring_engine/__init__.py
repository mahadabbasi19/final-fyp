# Java Refactoring Engine Package
# A comprehensive Python-based tool for refactoring Java code using AST parsing
# Includes real-time error detection similar to IntelliJ/Eclipse

__version__ = "2.0.0"
__author__ = "Java Refactoring Engine Team"

from error_checker import (
    ErrorChecker,
    JavaError,
    ErrorType,
    ErrorSeverity,
    JavaSyntaxChecker,
    RuntimeErrorDetector,
    StaticAnalyzer
)

from metrics import (
    MetricsCollector,
    MetricsVisualizer,
    VisualizationData,
    CouplingCohesionCalculator,
    HalsteadCalculator,
    MaintainabilityIndexCalculator,
    CodeHealthDashboard,
)

from refactoring_engine import (
    JavaRefactoringEngine,
    BehaviorDecomposer,
    StructureChanger,
    StructuralRefactoringResult,
    NewClassDefinition,
    BehaviorPreservationProtocol,
    VariableScopeAnalyzer,
    DeadCodeEliminator,
    UnusedImportRemover,
    ConditionSimplifier,
    LoopOptimizer,
)
