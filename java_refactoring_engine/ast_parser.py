"""
AST Parser Module
=================
Enhanced AST parsing for Java code using javalang library.
Provides comprehensive code structure extraction and analysis.
"""

import javalang
import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class MethodInfo:
    """Stores information about a Java method."""
    name: str
    params: List[Dict[str, str]]
    return_type: str
    modifiers: List[str]
    body_lines: int
    start_line: int
    end_line: int
    complexity: int  # Cyclomatic complexity
    nested_depth: int
    local_variables: List[str]
    method_calls: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FieldInfo:
    """Stores information about a class field."""
    name: str
    type_name: str
    modifiers: List[str]
    line: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ClassInfo:
    """Stores information about a Java class."""
    name: str
    modifiers: List[str]
    extends: Optional[str]
    implements: List[str]
    methods: List[MethodInfo]
    fields: List[FieldInfo]
    inner_classes: List['ClassInfo']
    start_line: int
    end_line: int
    total_lines: int
    
    def to_dict(self) -> Dict:
        result = {
            'name': self.name,
            'modifiers': self.modifiers,
            'extends': self.extends,
            'implements': self.implements,
            'methods': [m.to_dict() for m in self.methods],
            'fields': [f.to_dict() for f in self.fields],
            'inner_classes': [c.to_dict() for c in self.inner_classes],
            'start_line': self.start_line,
            'end_line': self.end_line,
            'total_lines': self.total_lines
        }
        return result


@dataclass
class CodeMetrics:
    """Stores code quality metrics."""
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    total_methods: int = 0
    total_classes: int = 0
    total_fields: int = 0
    avg_method_length: float = 0.0
    max_method_length: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    max_nesting: int = 0
    duplicate_blocks: int = 0
    long_methods: int = 0  # Methods > 20 lines
    large_classes: int = 0  # Classes > 200 lines
    
    def to_dict(self) -> Dict:
        return asdict(self)


class JavaASTParser:
    """
    Enhanced Java AST Parser
    ========================
    Parses Java source code and extracts comprehensive structural information
    including classes, methods, fields, and code metrics.
    """
    
    def __init__(self, file_path: Optional[str] = None):
        """
        Initialize the parser.
        
        Args:
            file_path: Optional path to a Java source file
        """
        self.file_path = file_path
        self.code = ""
        self.lines = []
        self.tree = None
        self.classes: List[ClassInfo] = []
        self.metrics = CodeMetrics()
        
    def load_file(self, file_path: Optional[str] = None) -> bool:
        """
        Load Java code from a file.
        
        Args:
            file_path: Path to Java file (uses self.file_path if not provided)
            
        Returns:
            True if successful
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = file_path or self.file_path
        if not path:
            raise ValueError("No file path provided")
            
        if not os.path.exists(path):
            raise FileNotFoundError(f"Java file not found: {path}")
            
        with open(path, "r", encoding='utf-8') as f:
            self.code = f.read()
        
        self.lines = self.code.split('\n')
        self.file_path = path
        return True
    
    def load_code(self, code: str) -> bool:
        """
        Load Java code from a string.
        
        Args:
            code: Java source code string
            
        Returns:
            True if successful
        """
        self.code = code
        self.lines = code.split('\n')
        return True
    
    def build_ast(self) -> bool:
        """
        Parse the loaded code and build the AST.
        
        Returns:
            True if parsing successful
            
        Raises:
            Exception: If there's a syntax error in the code
        """
        try:
            self.tree = javalang.parse.parse(self.code)
            return True
        except javalang.parser.JavaSyntaxError as e:
            raise Exception(f"Syntax error in Java code: {e}")
    
    def _calculate_complexity(self, node) -> int:
        """
        Calculate cyclomatic complexity for a method.
        Counts decision points: if, for, while, case, catch, &&, ||, ?:
        
        Args:
            node: AST node (method body)
            
        Returns:
            Cyclomatic complexity score
        """
        complexity = 1  # Base complexity
        
        if node is None:
            return complexity
            
        # Count decision points recursively
        for _, child in node.filter(javalang.tree.IfStatement):
            complexity += 1
        for _, child in node.filter(javalang.tree.ForStatement):
            complexity += 1
        for _, child in node.filter(javalang.tree.WhileStatement):
            complexity += 1
        for _, child in node.filter(javalang.tree.DoStatement):
            complexity += 1
        for _, child in node.filter(javalang.tree.SwitchStatementCase):
            complexity += 1
        for _, child in node.filter(javalang.tree.CatchClause):
            complexity += 1
        for _, child in node.filter(javalang.tree.TernaryExpression):
            complexity += 1
            
        # Count logical operators in conditions
        for _, child in node.filter(javalang.tree.BinaryOperation):
            if hasattr(child, 'operator') and child.operator in ('&&', '||'):
                complexity += 1
                
        return complexity
    
    def _calculate_nesting_depth(self, node, current_depth: int = 0) -> int:
        """
        Calculate maximum nesting depth in a method.
        
        Args:
            node: AST node
            current_depth: Current nesting level
            
        Returns:
            Maximum nesting depth
        """
        max_depth = current_depth
        
        if node is None:
            return max_depth
            
        nesting_nodes = (
            javalang.tree.IfStatement,
            javalang.tree.ForStatement,
            javalang.tree.WhileStatement,
            javalang.tree.DoStatement,
            javalang.tree.TryStatement,
            javalang.tree.SwitchStatement
        )
        
        for _, child in node.filter(nesting_nodes):
            nested_depth = self._calculate_nesting_depth(child, current_depth + 1)
            max_depth = max(max_depth, nested_depth)
            
        return max_depth
    
    def _extract_method_calls(self, node) -> List[str]:
        """
        Extract all method calls from a method body.
        
        Args:
            node: AST node (method body)
            
        Returns:
            List of method call names
        """
        calls = []
        if node is None:
            return calls
            
        for _, child in node.filter(javalang.tree.MethodInvocation):
            calls.append(child.member)
            
        return calls
    
    def _extract_local_variables(self, node) -> List[str]:
        """
        Extract local variable names from a method body.
        
        Args:
            node: AST node (method body)
            
        Returns:
            List of local variable names
        """
        variables = []
        if node is None:
            return variables
            
        for _, child in node.filter(javalang.tree.LocalVariableDeclaration):
            for decl in child.declarators:
                variables.append(decl.name)
                
        return variables
    
    def _estimate_method_lines(self, method) -> Tuple[int, int, int]:
        """
        Locate the line range of a method by matching braces in source.

        The original implementation guessed end-line as
        `start + len(body_statements) + 2`, which propagated wildly wrong
        sizes into long-method detection and slice extraction. We instead
        find `start_line` from the AST, then walk the source string with a
        brace counter (skipping strings/comments) to find the real `}`.
        """
        start_line = method.position.line if method.position else 0
        if start_line <= 0 or start_line > len(self.lines):
            return 0, 0, 0

        end_line = self._find_block_end_line(start_line)
        body_lines = max(0, end_line - start_line - 1)
        return start_line, end_line, body_lines

    def _find_block_end_line(self, start_line: int) -> int:
        """
        Given a 1-indexed line where a Java declaration starts, return the
        1-indexed line of its closing `}`. Returns `start_line` if no `{` is
        found on the declaration (e.g. abstract method).
        """
        in_block_comment = False
        in_line_comment = False
        in_string = False
        in_char = False
        escape = False
        depth = 0
        seen_open = False

        for line_idx in range(start_line - 1, len(self.lines)):
            line = self.lines[line_idx]
            in_line_comment = False
            i = 0
            while i < len(line):
                ch = line[i]
                nxt = line[i + 1] if i + 1 < len(line) else ''

                if in_line_comment:
                    break
                if in_block_comment:
                    if ch == '*' and nxt == '/':
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                    i += 1
                    continue
                if in_char:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == "'":
                        in_char = False
                    i += 1
                    continue

                if ch == '/' and nxt == '/':
                    in_line_comment = True
                    break
                if ch == '/' and nxt == '*':
                    in_block_comment = True
                    i += 2
                    continue
                if ch == '"':
                    in_string = True
                    i += 1
                    continue
                if ch == "'":
                    in_char = True
                    i += 1
                    continue
                if ch == '{':
                    depth += 1
                    seen_open = True
                elif ch == '}':
                    depth -= 1
                    if seen_open and depth == 0:
                        return line_idx + 1  # 1-indexed
                i += 1

            if seen_open and depth == 0:
                return line_idx + 1

        # No matching close found — declaration is incomplete; fall back to start.
        return start_line
    
    def _extract_method_info(self, method) -> MethodInfo:
        """
        Extract detailed information about a method.

        Now routes complexity, nesting depth, local-variable extraction, and
        method-call extraction through the real recursive helpers
        (`_calculate_complexity`, `_calculate_nesting_depth`,
        `_extract_local_variables`, `_extract_method_calls`) instead of the
        previous "top-level statements only" approximations. Those helpers
        existed but were never called for methods — every metric downstream
        (MI, radar chart, long-method detection, opportunity ranking) was
        being driven by an under-counted value.
        """
        params = []
        for param in method.parameters:
            param_info = {
                'name': param.name,
                'type': str(param.type.name) if param.type else 'Object'
            }
            params.append(param_info)

        return_type = str(method.return_type.name) if method.return_type else "void"
        modifiers = list(method.modifiers) if method.modifiers else []

        start_line, end_line, body_lines = self._estimate_method_lines(method)

        complexity = 1
        nested_depth = 0
        local_vars: List[str] = []
        method_calls: List[str] = []

        if method.body is not None:
            # `method` itself is filterable in javalang, so route the whole
            # subtree through the proper helpers.
            try:
                complexity = self._calculate_complexity(method)
            except Exception:
                complexity = 1
            try:
                nested_depth = self._calculate_nesting_depth(method)
            except Exception:
                nested_depth = 0
            try:
                local_vars = self._extract_local_variables(method)
            except Exception:
                local_vars = []
            try:
                method_calls = self._extract_method_calls(method)
            except Exception:
                method_calls = []

        return MethodInfo(
            name=method.name,
            params=params,
            return_type=return_type,
            modifiers=modifiers,
            body_lines=body_lines,
            start_line=start_line,
            end_line=end_line,
            complexity=complexity,
            nested_depth=nested_depth,
            local_variables=local_vars,
            method_calls=method_calls
        )
    
    def _extract_field_info(self, field, line: int = 0) -> List[FieldInfo]:
        """
        Extract information about class fields.
        
        Args:
            field: Field AST node
            line: Line number
            
        Returns:
            List of FieldInfo objects (multiple if field has multiple declarators)
        """
        fields = []
        modifiers = list(field.modifiers) if field.modifiers else []
        type_name = str(field.type.name) if field.type else "Object"
        
        for decl in field.declarators:
            field_info = FieldInfo(
                name=decl.name,
                type_name=type_name,
                modifiers=modifiers,
                line=field.position.line if field.position else line
            )
            fields.append(field_info)
            
        return fields
    
    def _extract_class_info(self, node, depth: int = 0) -> ClassInfo:
        """
        Extract comprehensive information about a class.
        
        Args:
            node: Class declaration AST node
            depth: Nesting depth (for inner classes)
            
        Returns:
            ClassInfo object with class details
        """
        # Extract basic class info
        name = node.name
        modifiers = list(node.modifiers) if node.modifiers else []
        extends = node.extends.name if node.extends else None
        implements = [impl.name for impl in node.implements] if node.implements else []
        
        # Extract methods
        methods = []
        for method in node.methods:
            method_info = self._extract_method_info(method)
            methods.append(method_info)
        
        # Extract fields
        fields = []
        for field in node.fields:
            field_infos = self._extract_field_info(field)
            fields.extend(field_infos)
        
        # Extract inner classes
        inner_classes = []
        for member in node.body:
            if isinstance(member, javalang.tree.ClassDeclaration):
                inner_class = self._extract_class_info(member, depth + 1)
                inner_classes.append(inner_class)
        
        # Real line range via brace matching (was a guess based on method
        # body lengths, which inflated class size massively).
        start_line = node.position.line if node.position else 0
        if start_line > 0:
            end_line = self._find_block_end_line(start_line)
            total_lines = max(0, end_line - start_line + 1)
        else:
            end_line = 0
            total_lines = 0
        
        return ClassInfo(
            name=name,
            modifiers=modifiers,
            extends=extends,
            implements=implements,
            methods=methods,
            fields=fields,
            inner_classes=inner_classes,
            start_line=start_line,
            end_line=end_line,
            total_lines=total_lines
        )
    
    def extract_all(self) -> Dict[str, Any]:
        """
        Extract all structural information from the parsed code.
        
        Returns:
            Dictionary containing classes, interfaces, and metrics
        """
        if not self.tree:
            raise Exception("AST not built. Call build_ast() first.")
        
        self.classes = []
        
        # Extract all classes
        for path, node in self.tree.filter(javalang.tree.ClassDeclaration):
            # Only extract top-level classes (not inner classes)
            if len(path) <= 2:  # CompilationUnit -> ClassDeclaration
                class_info = self._extract_class_info(node)
                self.classes.append(class_info)
        
        # Calculate metrics
        self._calculate_metrics()
        
        return {
            'classes': [c.to_dict() for c in self.classes],
            'metrics': self.metrics.to_dict()
        }
    
    def _calculate_metrics(self):
        """Calculate code quality metrics from extracted information."""
        # Line counts
        self.metrics.total_lines = len(self.lines)
        self.metrics.blank_lines = sum(1 for line in self.lines if line.strip() == '')
        self.metrics.comment_lines = sum(1 for line in self.lines 
                                         if line.strip().startswith('//') or 
                                         line.strip().startswith('/*') or
                                         line.strip().startswith('*'))
        self.metrics.code_lines = (self.metrics.total_lines - 
                                   self.metrics.blank_lines - 
                                   self.metrics.comment_lines)
        
        # Class and method counts
        self.metrics.total_classes = len(self.classes)
        
        total_methods = 0
        total_fields = 0
        total_complexity = 0
        max_complexity = 0
        max_method_length = 0
        total_method_length = 0
        max_nesting = 0
        long_methods = 0
        large_classes = 0
        
        for cls in self.classes:
            total_fields += len(cls.fields)
            
            if cls.total_lines > 200:
                large_classes += 1
            
            for method in cls.methods:
                total_methods += 1
                total_complexity += method.complexity
                total_method_length += method.body_lines
                
                if method.complexity > max_complexity:
                    max_complexity = method.complexity
                if method.body_lines > max_method_length:
                    max_method_length = method.body_lines
                if method.nested_depth > max_nesting:
                    max_nesting = method.nested_depth
                if method.body_lines > 20:
                    long_methods += 1
        
        self.metrics.total_methods = total_methods
        self.metrics.total_fields = total_fields
        self.metrics.max_complexity = max_complexity
        self.metrics.max_method_length = max_method_length
        self.metrics.max_nesting = max_nesting
        self.metrics.long_methods = long_methods
        self.metrics.large_classes = large_classes
        
        if total_methods > 0:
            self.metrics.avg_complexity = round(total_complexity / total_methods, 2)
            self.metrics.avg_method_length = round(total_method_length / total_methods, 2)
    
    def get_json(self, indent: int = 4) -> str:
        """
        Get extracted information as JSON string.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        structure = self.extract_all()
        return json.dumps(structure, indent=indent)
    
    def get_code_blocks(self) -> Dict[str, List[str]]:
        """
        Extract code blocks for duplicate detection.
        
        Returns:
            Dictionary mapping block identifiers to code lines
        """
        blocks = {}
        
        for cls in self.classes:
            for method in cls.methods:
                start = method.start_line - 1
                end = min(method.end_line, len(self.lines))
                if start >= 0 and end > start:
                    block_key = f"{cls.name}.{method.name}"
                    blocks[block_key] = self.lines[start:end]
        
        return blocks


def parse_java_file(file_path: str) -> Tuple[Dict[str, Any], CodeMetrics]:
    """
    Convenience function to parse a Java file and return structure and metrics.
    
    Args:
        file_path: Path to Java file
        
    Returns:
        Tuple of (extracted structure dict, CodeMetrics object)
    """
    parser = JavaASTParser(file_path)
    parser.load_file()
    parser.build_ast()
    structure = parser.extract_all()
    return structure, parser.metrics


def parse_java_code(code: str) -> Tuple[Dict[str, Any], CodeMetrics]:
    """
    Convenience function to parse Java code string and return structure and metrics.
    
    Args:
        code: Java source code string
        
    Returns:
        Tuple of (extracted structure dict, CodeMetrics object)
    """
    parser = JavaASTParser()
    parser.load_code(code)
    parser.build_ast()
    structure = parser.extract_all()
    return structure, parser.metrics
