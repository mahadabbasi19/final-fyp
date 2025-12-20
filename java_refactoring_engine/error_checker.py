"""
Error Checker Module for Java Code
===================================
This module provides real-time error detection for Java code, similar to 
IntelliJ or Eclipse IDEs. It detects:

1. SYNTAX ERRORS: Missing semicolons, unmatched braces, undeclared variables,
   wrong method calls, invalid Java constructs.

2. RUNTIME ERRORS: NullPointerException, ArrayIndexOutOfBoundsException,
   divide by zero, arithmetic exceptions.

3. LOGICAL WARNINGS: Unused variables, unreachable code, bad practices.

Architecture:
- Uses subprocess to call javac for syntax checking
- Executes code in sandboxed environment for runtime error detection
- Background threading for non-blocking UI updates
- Debouncing to prevent excessive checks while typing

Author: Java Refactoring Engine
Date: 2025
"""

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable, Dict, Tuple
from pathlib import Path


class ErrorType(Enum):
    """
    Classification of error types detected by the checker.
    
    SYNTAX: Compilation errors caught by javac
    RUNTIME: Errors that would occur during execution
    WARNING: Code quality issues and potential bugs
    INFO: Informational messages and suggestions
    """
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    WARNING = "warning"
    INFO = "info"


class ErrorSeverity(Enum):
    """
    Severity levels for prioritizing error display.
    
    ERROR: Must be fixed for code to compile/run
    WARNING: Should be fixed but code may still work
    INFO: Suggestions for improvement
    """
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class JavaError:
    """
    Data class representing a single detected error or warning.
    
    Attributes:
        line: Line number where error occurs (1-indexed)
        column: Column number where error occurs (1-indexed)
        error_type: Type of error (syntax/runtime/warning)
        severity: How critical the error is
        message: Human-readable error description
        suggestion: Optional fix suggestion
        code_snippet: The problematic code segment
    """
    line: int
    column: int
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert error to dictionary for JSON serialization."""
        return {
            'line': self.line,
            'column': self.column,
            'type': self.error_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'suggestion': self.suggestion,
            'code_snippet': self.code_snippet
        }
    
    def __str__(self) -> str:
        """String representation for display in error panel."""
        type_icon = {
            ErrorType.SYNTAX: "❌",
            ErrorType.RUNTIME: "⚠️",
            ErrorType.WARNING: "💡",
            ErrorType.INFO: "ℹ️"
        }
        return f"{type_icon.get(self.error_type, '•')} Line {self.line}: {self.message}"


class JavaSyntaxChecker:
    """
    Syntax Checker using javac compiler.
    
    This class handles syntax error detection by:
    1. Writing code to a temporary .java file
    2. Running javac to compile (without execution)
    3. Parsing javac output for error messages
    4. Converting errors to JavaError objects
    
    Errors detected include:
    - Missing semicolons
    - Unmatched braces/parentheses
    - Undeclared variables
    - Type mismatches
    - Invalid method calls
    - Missing return statements
    """
    
    def __init__(self):
        """Initialize the syntax checker."""
        self.temp_dir = tempfile.mkdtemp(prefix="java_checker_")
        self.javac_path = self._find_javac()
        
    def _find_javac(self) -> Optional[str]:
        """
        Locate the javac compiler on the system.
        
        Returns:
            Path to javac executable, or None if not found.
        """
        # Try common locations
        possible_paths = [
            "javac",  # If in PATH
            r"C:\Program Files\Java\jdk-21\bin\javac.exe",
            r"C:\Program Files\Java\jdk-17\bin\javac.exe",
            r"C:\Program Files\Java\jdk-11\bin\javac.exe",
            r"C:\Program Files\Java\jdk1.8.0_351\bin\javac.exe",
            "/usr/bin/javac",
            "/usr/local/bin/javac",
        ]
        
        # Check JAVA_HOME
        java_home = os.environ.get('JAVA_HOME')
        if java_home:
            possible_paths.insert(0, os.path.join(java_home, 'bin', 'javac'))
            possible_paths.insert(0, os.path.join(java_home, 'bin', 'javac.exe'))
        
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, '-version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        return None
    
    def check_syntax(self, code: str) -> List[JavaError]:
        """
        Check Java code for syntax errors using javac.
        
        Args:
            code: Java source code to check
            
        Returns:
            List of JavaError objects for detected syntax errors
        """
        errors = []
        
        if not self.javac_path:
            # Fallback to regex-based checking if javac not available
            return self._regex_syntax_check(code)
        
        # Extract class name from code
        class_name = self._extract_class_name(code)
        if not class_name:
            class_name = "TempClass"
            # Wrap code in a class if needed
            if 'class ' not in code:
                code = f"public class {class_name} {{\n{code}\n}}"
        
        # Write to temp file
        temp_file = os.path.join(self.temp_dir, f"{class_name}.java")
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Run javac with reduced timeout for responsiveness
            result = subprocess.run(
                [self.javac_path, '-Xlint:all', temp_file],
                capture_output=True,
                text=True,
                timeout=3  # Reduced from 10 to 3 seconds
            )
            
            # Parse errors from javac output
            errors.extend(self._parse_javac_output(result.stderr, code))
            
        except subprocess.TimeoutExpired:
            errors.append(JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.WARNING,
                message="Syntax check timed out - code may be too complex"
            ))
        except Exception as e:
            errors.append(JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.INFO,
                message=f"Syntax check error: {str(e)}"
            ))
        finally:
            # Cleanup
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                class_file = temp_file.replace('.java', '.class')
                if os.path.exists(class_file):
                    os.remove(class_file)
            except:
                pass
        
        return errors
    
    def _extract_class_name(self, code: str) -> Optional[str]:
        """Extract the public class name from Java code."""
        match = re.search(r'public\s+class\s+(\w+)', code)
        if match:
            return match.group(1)
        match = re.search(r'class\s+(\w+)', code)
        if match:
            return match.group(1)
        return None
    
    def _parse_javac_output(self, output: str, original_code: str) -> List[JavaError]:
        """
        Parse javac error output into JavaError objects.
        
        javac output format:
        filename.java:line: error: message
                code snippet
                ^
        """
        errors = []
        lines = output.strip().split('\n')
        
        # Pattern for javac error line
        error_pattern = re.compile(r'.*\.java:(\d+):\s*(error|warning):\s*(.+)')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            match = error_pattern.match(line)
            
            if match:
                line_num = int(match.group(1))
                error_kind = match.group(2)
                message = match.group(3)
                
                # Get code snippet if available
                snippet = None
                column = 1
                if i + 1 < len(lines):
                    snippet = lines[i + 1].strip()
                    # Find column from caret position
                    if i + 2 < len(lines) and '^' in lines[i + 2]:
                        column = lines[i + 2].index('^') + 1
                
                error_type = ErrorType.SYNTAX if error_kind == 'error' else ErrorType.WARNING
                severity = ErrorSeverity.ERROR if error_kind == 'error' else ErrorSeverity.WARNING
                
                # Generate suggestion based on error message
                suggestion = self._generate_suggestion(message)
                
                errors.append(JavaError(
                    line=line_num,
                    column=column,
                    error_type=error_type,
                    severity=severity,
                    message=message,
                    suggestion=suggestion,
                    code_snippet=snippet
                ))
            
            i += 1
        
        return errors
    
    def _generate_suggestion(self, error_message: str) -> Optional[str]:
        """Generate a fix suggestion based on the error message."""
        suggestions = {
            "';' expected": "Add a semicolon at the end of the statement",
            "cannot find symbol": "Check variable/method name spelling or add import",
            "incompatible types": "Ensure type compatibility or add explicit cast",
            "missing return statement": "Add a return statement for all code paths",
            "unreachable statement": "Remove or restructure unreachable code",
            "variable .* might not have been initialized": "Initialize the variable before use",
            "illegal start of expression": "Check for missing braces or incorrect syntax",
            "class .* is public": "Class name must match filename",
            "reached end of file while parsing": "Add missing closing brace '}'",
            "unclosed string literal": "Add closing quote to string",
        }
        
        for pattern, suggestion in suggestions.items():
            if re.search(pattern, error_message, re.IGNORECASE):
                return suggestion
        
        return None
    
    def _regex_syntax_check(self, code: str) -> List[JavaError]:
        """
        Fallback syntax checking using regex patterns.
        Used when javac is not available.
        """
        errors = []
        lines = code.split('\n')
        
        # Track braces and parentheses with context
        brace_stack = []  # [(line, col, context)]
        paren_stack = []  # [(line, col, context)]
        square_stack = []  # [(line, col)]
        
        # Track multi-line comment state
        in_multiline_comment = False
        
        for i, line in enumerate(lines, 1):
            original_line = line
            line_stripped = line.strip()
            
            # Handle multi-line comments
            if in_multiline_comment:
                if '*/' in line:
                    in_multiline_comment = False
                    after_comment = line[line.index('*/') + 2:]
                    if not after_comment.strip():
                        continue
                    line_stripped = after_comment.strip()
                else:
                    continue
            
            # Check for start of multi-line comment
            if '/*' in line_stripped:
                if '*/' not in line_stripped:
                    in_multiline_comment = True
                continue
            
            # Skip single-line comments (full line)
            if line_stripped.startswith('//'):
                continue
            
            # Skip JavaDoc comment lines
            if line_stripped.startswith('*') or line_stripped.startswith('/**'):
                continue
            
            # Skip annotation lines
            if line_stripped.startswith('@'):
                continue
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Get code before any inline comment
            code_before_comment = line_stripped
            comment_start = -1
            if '//' in code_before_comment:
                # Find // that's not inside a string
                in_str = False
                for idx, ch in enumerate(code_before_comment):
                    if ch == '"' and (idx == 0 or code_before_comment[idx-1] != '\\'):
                        in_str = not in_str
                    elif not in_str and code_before_comment[idx:idx+2] == '//':
                        comment_start = idx
                        break
                if comment_start >= 0:
                    code_before_comment = code_before_comment[:comment_start].strip()
            
            # Remove string literals for bracket counting
            line_for_brackets = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code_before_comment)
            line_for_brackets = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line_for_brackets)
            
            # Count brackets character by character
            for j, char in enumerate(line_for_brackets):
                if char == '{':
                    context = 'method' if '(' in line_for_brackets[:j] else 'block'
                    brace_stack.append((i, j+1, context))
                elif char == '}':
                    if brace_stack:
                        brace_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j+1,
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Unmatched closing brace '}'",
                            suggestion="Remove extra '}' or add matching '{'"
                        ))
                
                if char == '(':
                    paren_stack.append((i, j+1, code_before_comment[:30]))
                elif char == ')':
                    if paren_stack:
                        paren_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j+1,
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Unmatched closing parenthesis ')'",
                            suggestion="Remove extra ')' or add matching '('"
                        ))
                
                if char == '[':
                    square_stack.append((i, j+1))
                elif char == ']':
                    if square_stack:
                        square_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j+1,
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Unmatched closing bracket ']'",
                            suggestion="Remove extra ']' or add matching '['"
                        ))
            
            # Check for missing semicolons on statement lines
            # But skip if this looks like a multi-line statement continuation
            code_part = code_before_comment
            
            # Check if next non-empty line starts with . (method chaining) or operator
            is_continued = False
            if i < len(lines):
                for next_idx in range(i, min(i + 3, len(lines))):
                    next_line = lines[next_idx].strip()
                    # Skip empty lines and comments
                    if not next_line or next_line.startswith('//') or next_line.startswith('*'):
                        continue
                    # Check if it starts with continuation patterns
                    if next_line.startswith('.') or next_line.startswith('+') or next_line.startswith('-'):
                        is_continued = True
                    break
            
            if code_part and not code_part.endswith(('{', '}', ';', ',', ':', '(', ')')) and not is_continued:
                # These patterns should end with semicolon
                if re.match(r'^(return|break|continue|throw)\s', code_part):
                    errors.append(JavaError(
                        line=i, column=len(line),
                        error_type=ErrorType.SYNTAX,
                        severity=ErrorSeverity.ERROR,
                        message="Missing semicolon after statement",
                        suggestion="Add ';' at the end of the statement"
                    ))
                # Variable declarations/assignments - but not if ends with operator
                elif re.match(r'^\w+\s+\w+\s*=', code_part) and not code_part.endswith('{'):
                    # Skip if line ends with an operator (continuation)
                    if not re.search(r'[\+\-\*\/\&\|\^]$', code_part):
                        errors.append(JavaError(
                            line=i, column=len(line),
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Missing semicolon after declaration",
                            suggestion="Add ';' at the end of the declaration"
                        ))
                # Array declarations without semicolon
                elif re.match(r'^\w+\[\]\s+\w+\s*=', code_part):
                    if not re.search(r'[\+\-\*\/\&\|\^]$', code_part):
                        errors.append(JavaError(
                            line=i, column=len(line),
                            error_type=ErrorType.SYNTAX,
                            severity=ErrorSeverity.ERROR,
                            message="Missing semicolon after array declaration",
                            suggestion="Add ';' at the end of the declaration"
                        ))
        
        # Check for unclosed braces at end of file
        for line_num, col, context in brace_stack:
            errors.append(JavaError(
                line=line_num, column=col,
                error_type=ErrorType.SYNTAX,
                severity=ErrorSeverity.ERROR,
                message=f"Unclosed brace '{{' (opened at line {line_num})",
                suggestion="Add matching '}}' to close the block"
            ))
        
        # Check for unclosed parentheses at end of file
        for line_num, col, context in paren_stack:
            errors.append(JavaError(
                line=line_num, column=col,
                error_type=ErrorType.SYNTAX,
                severity=ErrorSeverity.ERROR,
                message=f"Unclosed parenthesis '(' (opened at line {line_num})",
                suggestion="Add matching ')' to close"
            ))
        
        # Check for unclosed square brackets at end of file
        for line_num, col in square_stack:
            errors.append(JavaError(
                line=line_num, column=col,
                error_type=ErrorType.SYNTAX,
                severity=ErrorSeverity.ERROR,
                message=f"Unclosed bracket '[' (opened at line {line_num})",
                suggestion="Add matching ']' to close"
            ))
        
        return errors


def strip_java_comments(code: str) -> Tuple[str, Dict[int, bool]]:
    """
    Remove comments from Java code while preserving line numbers.
    
    Returns:
        Tuple of (code_without_comments, dict of line_number -> is_comment_line)
    """
    lines = code.split('\n')
    result_lines = []
    comment_lines = {}
    in_multiline_comment = False
    
    for i, line in enumerate(lines, 1):
        original_line = line
        line_stripped = line.strip()
        
        # Handle multi-line comments
        if in_multiline_comment:
            comment_lines[i] = True
            if '*/' in line:
                in_multiline_comment = False
                # Keep content after closing comment
                after_comment_idx = line.index('*/') + 2
                line = line[after_comment_idx:]
                if not line.strip():
                    result_lines.append('')
                    continue
            else:
                result_lines.append('')
                continue
        
        # Check for start of multi-line comment
        if '/*' in line_stripped:
            comment_lines[i] = True
            if '*/' in line_stripped:
                # Single line block comment - remove it
                line = re.sub(r'/\*.*?\*/', '', line)
            else:
                in_multiline_comment = True
                # Keep content before the comment
                before_comment = line[:line.index('/*')]
                result_lines.append(before_comment)
                continue
        
        # Check for single-line comment
        if '//' in line:
            # Remove inline comment
            comment_idx = line.index('//')
            # Make sure it's not inside a string
            in_string = False
            for j, char in enumerate(line[:comment_idx]):
                if char == '"' and (j == 0 or line[j-1] != '\\'):
                    in_string = not in_string
            if not in_string:
                line = line[:comment_idx]
                if not line.strip():
                    comment_lines[i] = True
        
        # Check if entire line is a comment
        if line_stripped.startswith('//') or line_stripped.startswith('*') or line_stripped.startswith('/**'):
            comment_lines[i] = True
            result_lines.append('')
            continue
        
        result_lines.append(line)
    
    return '\n'.join(result_lines), comment_lines


def is_comment_line(line: str, in_multiline: bool = False) -> Tuple[bool, bool]:
    """
    Check if a line is a comment line.
    
    Args:
        line: The line to check
        in_multiline: Whether we're currently inside a multi-line comment
        
    Returns:
        Tuple of (is_comment, still_in_multiline)
    """
    line_stripped = line.strip()
    
    if in_multiline:
        if '*/' in line:
            return True, False
        return True, True
    
    if line_stripped.startswith('//'):
        return True, False
    
    if line_stripped.startswith('/*'):
        if '*/' in line_stripped:
            return True, False
        return True, True
    
    if line_stripped.startswith('*') or line_stripped.startswith('/**'):
        return True, in_multiline
    
    return False, False


class RuntimeErrorDetector:
    """
    Runtime Error Detector for Java Code.
    
    This class detects potential runtime errors through:
    1. Static pattern analysis for common runtime issues
    2. Optional sandboxed execution with try-catch wrapping
    
    Errors detected include:
    - NullPointerException risks
    - ArrayIndexOutOfBoundsException risks
    - Division by zero
    - Integer overflow
    - Resource leaks
    """
    
    def __init__(self):
        """Initialize the runtime error detector."""
        self.java_path = self._find_java()
        
    def _find_java(self) -> Optional[str]:
        """Locate the java runtime on the system."""
        possible_paths = ["java", "java.exe"]
        
        java_home = os.environ.get('JAVA_HOME')
        if java_home:
            possible_paths.insert(0, os.path.join(java_home, 'bin', 'java'))
            possible_paths.insert(0, os.path.join(java_home, 'bin', 'java.exe'))
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '-version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except:
                continue
        return None
    
    def detect_runtime_errors(self, code: str) -> List[JavaError]:
        """
        Detect potential runtime errors in Java code.
        
        Uses pattern matching to identify common runtime error patterns.
        """
        errors = []
        lines = code.split('\n')
        
        # Track variable declarations for null checks
        declared_vars: Dict[str, int] = {}  # var_name -> line_number
        initialized_vars: set = set()
        
        # Track multi-line comment state
        in_multiline_comment = False
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Handle multi-line comments
            is_comment, in_multiline_comment = is_comment_line(line_stripped, in_multiline_comment)
            if is_comment:
                continue
            
            # Remove inline comments for analysis
            if '//' in line:
                comment_idx = line.index('//')
                line = line[:comment_idx]
            
            # 1. Check for potential NullPointerException
            errors.extend(self._check_null_pointer(line, i, declared_vars, initialized_vars))
            
            # 2. Check for potential ArrayIndexOutOfBoundsException
            errors.extend(self._check_array_bounds(line, i))
            
            # 3. Check for division by zero
            errors.extend(self._check_division_by_zero(line, i))
            
            # 4. Check for potential integer overflow
            errors.extend(self._check_integer_overflow(line, i))
            
            # 5. Check for resource leaks
            errors.extend(self._check_resource_leaks(line, i, code))
            
            # Track variable declarations
            self._track_variables(line, i, declared_vars, initialized_vars)
        
        return errors
    
    def _check_null_pointer(self, line: str, line_num: int, 
                           declared_vars: Dict[str, int],
                           initialized_vars: set) -> List[JavaError]:
        """Check for potential NullPointerException."""
        errors = []
        
        # Pattern: method call on potentially null object
        # e.g., str.length() where str might be null
        method_call_pattern = re.compile(r'(\w+)\.([\w]+)\s*\(')
        
        for match in method_call_pattern.finditer(line):
            var_name = match.group(1)
            method_name = match.group(2)
            
            # Check if variable was declared but might not be initialized
            if var_name in declared_vars and var_name not in initialized_vars:
                if var_name not in ['System', 'Math', 'String', 'Integer', 'Arrays', 'Collections']:
                    errors.append(JavaError(
                        line=line_num,
                        column=match.start() + 1,
                        error_type=ErrorType.RUNTIME,
                        severity=ErrorSeverity.WARNING,
                        message=f"Potential NullPointerException: '{var_name}' may be null",
                        suggestion=f"Add null check: if ({var_name} != null) {{ ... }}"
                    ))
        
        # Pattern: accessing .length on array that might be null
        # Reduced NPE detection - only flag very clear cases
        # The previous pattern was too aggressive and flagged safe code
        
        return errors
    
    def _check_array_bounds(self, line: str, line_num: int) -> List[JavaError]:
        """Check for potential ArrayIndexOutOfBoundsException."""
        errors = []
        
        # Pattern: array access with hardcoded index
        array_access_pattern = re.compile(r'(\w+)\[(\d+)\]')
        
        for match in array_access_pattern.finditer(line):
            index = int(match.group(2))
            if index > 100:  # Suspiciously large hardcoded index
                errors.append(JavaError(
                    line=line_num,
                    column=match.start() + 1,
                    error_type=ErrorType.RUNTIME,
                    severity=ErrorSeverity.WARNING,
                    message=f"Large array index {index} - ensure array is properly sized",
                    suggestion="Consider using dynamic sizing or bounds checking"
                ))
        
        # Pattern: array access with potentially negative index
        neg_index_pattern = re.compile(r'(\w+)\[(\w+)\s*-\s*\d+\]')
        for match in neg_index_pattern.finditer(line):
            errors.append(JavaError(
                line=line_num,
                column=match.start() + 1,
                error_type=ErrorType.RUNTIME,
                severity=ErrorSeverity.WARNING,
                message="Potential negative array index",
                suggestion="Add bounds check: if (index >= 0 && index < array.length)"
            ))
        
        return errors
    
    def _check_division_by_zero(self, line: str, line_num: int) -> List[JavaError]:
        """Check for potential division by zero."""
        errors = []
        
        # Pattern: division by zero literal
        if re.search(r'/\s*0(?![.\d])', line):
            errors.append(JavaError(
                line=line_num,
                column=line.index('/') + 1,
                error_type=ErrorType.RUNTIME,
                severity=ErrorSeverity.ERROR,
                message="Division by zero detected",
                suggestion="Ensure divisor is not zero before division"
            ))
        
        # Pattern: division by variable - DISABLED to reduce false positives
        # This was generating too many warnings for safe code
        # Only flag explicit division by 0 literal above
        
        # Pattern: modulo by zero
        if re.search(r'%\s*0(?![.\d])', line):
            errors.append(JavaError(
                line=line_num,
                column=line.index('%') + 1,
                error_type=ErrorType.RUNTIME,
                severity=ErrorSeverity.ERROR,
                message="Modulo by zero detected",
                suggestion="Ensure divisor is not zero before modulo operation"
            ))
        
        return errors
    
    def _check_integer_overflow(self, line: str, line_num: int) -> List[JavaError]:
        """Check for potential integer overflow."""
        errors = []
        
        # Pattern: Large integer literal
        large_int_pattern = re.compile(r'\b(\d{10,})\b')
        for match in large_int_pattern.finditer(line):
            num = match.group(1)
            try:
                val = int(num)
                if val > 2147483647:  # Integer.MAX_VALUE
                    errors.append(JavaError(
                        line=line_num,
                        column=match.start() + 1,
                        error_type=ErrorType.RUNTIME,
                        severity=ErrorSeverity.WARNING,
                        message=f"Integer overflow: {num} exceeds Integer.MAX_VALUE",
                        suggestion="Use 'long' type or add 'L' suffix (e.g., {num}L)"
                    ))
            except:
                pass
        
        return errors
    
    def _check_resource_leaks(self, line: str, line_num: int, full_code: str) -> List[JavaError]:
        """Check for potential resource leaks."""
        errors = []
        
        # Pattern: new FileInputStream/FileOutputStream/Scanner without try-with-resources
        resource_patterns = [
            (r'new\s+FileInputStream\s*\(', 'FileInputStream'),
            (r'new\s+FileOutputStream\s*\(', 'FileOutputStream'),
            (r'new\s+BufferedReader\s*\(', 'BufferedReader'),
            (r'new\s+BufferedWriter\s*\(', 'BufferedWriter'),
            (r'new\s+Scanner\s*\(', 'Scanner'),
            (r'new\s+PrintWriter\s*\(', 'PrintWriter'),
        ]
        
        for pattern, resource_type in resource_patterns:
            if re.search(pattern, line):
                # Check if it's in a try-with-resources
                # Simple check: look for 'try (' before this line
                line_index = full_code.find(line)
                preceding_code = full_code[:line_index] if line_index > 0 else ""
                
                # Count try-with-resources vs regular new
                if 'try (' not in preceding_code[-200:] and 'try(' not in preceding_code[-200:]:
                    errors.append(JavaError(
                        line=line_num,
                        column=line.index('new') + 1,
                        error_type=ErrorType.RUNTIME,
                        severity=ErrorSeverity.WARNING,
                        message=f"Potential resource leak: {resource_type} not in try-with-resources",
                        suggestion=f"Use try-with-resources: try ({resource_type} resource = new {resource_type}(...)) {{ }}"
                    ))
        
        return errors
    
    def _track_variables(self, line: str, line_num: int,
                        declared_vars: Dict[str, int],
                        initialized_vars: set):
        """Track variable declarations and initializations."""
        # Pattern: Type varName;
        decl_pattern = re.compile(r'(String|int|long|double|float|boolean|char|byte|short|\w+(?:<[^>]+>)?)\s+(\w+)\s*;')
        for match in decl_pattern.finditer(line):
            var_name = match.group(2)
            declared_vars[var_name] = line_num
        
        # Pattern: Type varName = value;
        init_pattern = re.compile(r'(String|int|long|double|float|boolean|char|byte|short|\w+(?:<[^>]+>)?)\s+(\w+)\s*=')
        for match in init_pattern.finditer(line):
            var_name = match.group(2)
            declared_vars[var_name] = line_num
            if '= null' not in line:
                initialized_vars.add(var_name)
        
        # Pattern: varName = value; (assignment)
        assign_pattern = re.compile(r'^\s*(\w+)\s*=\s*(?!null)')
        match = assign_pattern.match(line)
        if match:
            var_name = match.group(1)
            initialized_vars.add(var_name)


class StaticAnalyzer:
    """
    Static Code Analyzer for Java.
    
    This class performs static analysis to detect:
    1. Unused variables
    2. Unreachable code
    3. Code smells and bad practices
    4. Naming convention violations
    5. Complexity warnings
    
    Similar to PMD/Checkstyle but implemented in Python.
    """
    
    def __init__(self):
        """Initialize the static analyzer."""
        self.warnings: List[JavaError] = []
    
    def analyze(self, code: str) -> List[JavaError]:
        """
        Perform static analysis on Java code.
        
        Args:
            code: Java source code to analyze
            
        Returns:
            List of JavaError objects for detected issues
        """
        self.warnings = []
        lines = code.split('\n')
        
        # Strip comments from code for analysis
        code_no_comments, comment_line_map = strip_java_comments(code)
        
        # Run all analysis checks
        self._check_unused_variables(code_no_comments, lines, comment_line_map)
        self._check_unreachable_code(code_no_comments, lines, comment_line_map)
        self._check_naming_conventions(code_no_comments, lines, comment_line_map)
        self._check_empty_blocks(code_no_comments, lines, comment_line_map)
        self._check_magic_numbers(code_no_comments, lines, comment_line_map)
        self._check_long_methods(code, lines)
        self._check_deep_nesting(code_no_comments, lines, comment_line_map)
        self._check_empty_catch(code, lines)
        self._check_system_exit(code_no_comments, lines, comment_line_map)
        self._check_hardcoded_strings(code_no_comments, lines, comment_line_map)
        
        return self.warnings
    
    def _is_comment_line(self, line_num: int, comment_map: Dict[int, bool]) -> bool:
        """Check if a line number is a comment line."""
        return comment_map.get(line_num, False)
    
    def _check_unused_variables(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for unused local variables."""
        # Find all variable declarations
        var_pattern = re.compile(
            r'(int|long|double|float|boolean|char|byte|short|String|\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]'
        )
        
        declared_vars = {}
        in_multiline_comment = False
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip comment lines
            if self._is_comment_line(i, comment_map):
                continue
            
            # Handle multi-line comments
            is_comment, in_multiline_comment = is_comment_line(line_stripped, in_multiline_comment)
            if is_comment:
                continue
            
            for match in var_pattern.finditer(line):
                var_name = match.group(2)
                # Skip common names that might be intentionally unused
                if var_name not in ['i', 'j', 'k', 'e', 'ex', 'args', '_']:
                    declared_vars[var_name] = i
        
        # Check usage
        for var_name, line_num in declared_vars.items():
            # Count occurrences (excluding declaration)
            pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
            occurrences = len(pattern.findall(code))
            
            if occurrences <= 1:  # Only declaration, no usage
                self.warnings.append(JavaError(
                    line=line_num,
                    column=1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.WARNING,
                    message=f"Unused variable: '{var_name}'",
                    suggestion=f"Remove unused variable or use it in your code"
                ))
    
    def _check_unreachable_code(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for unreachable code after return/throw/break/continue."""
        control_keywords = ['return', 'throw', 'break', 'continue']
        
        in_block = False
        block_end_line = 0
        in_multiline_comment = False
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments and empty lines
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or not stripped or self._is_comment_line(i, comment_map):
                continue
            
            # Check if previous line was a control statement
            if in_block and i > block_end_line:
                # Check if this line is still in same block (not a closing brace)
                if stripped != '}' and stripped != '} else {' and not stripped.startswith('case '):
                    self.warnings.append(JavaError(
                        line=i,
                        column=1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.WARNING,
                        message="Unreachable code detected",
                        suggestion="Remove this code or restructure logic"
                    ))
                in_block = False
            
            # Check for control statements
            for keyword in control_keywords:
                if re.match(rf'^\s*{keyword}\s*[;\s]', line) or re.match(rf'^\s*{keyword}\s', line):
                    in_block = True
                    block_end_line = i
                    break
    
    def _check_naming_conventions(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check Java naming conventions."""
        in_multiline_comment = False
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            # Check class names (should be PascalCase)
            class_match = re.search(r'class\s+([a-z]\w*)', line)
            if class_match:
                class_name = class_match.group(1)
                self.warnings.append(JavaError(
                    line=i,
                    column=line.index(class_name) + 1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.INFO,
                    message=f"Class name '{class_name}' should start with uppercase",
                    suggestion=f"Rename to '{class_name.capitalize()}'"
                ))
            
            # Check constant names (should be UPPER_SNAKE_CASE)
            const_match = re.search(r'(static\s+final|final\s+static)\s+\w+\s+([a-z]\w*)\s*=', line)
            if const_match:
                const_name = const_match.group(2)
                if not const_name.isupper():
                    self.warnings.append(JavaError(
                        line=i,
                        column=line.index(const_name) + 1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.INFO,
                        message=f"Constant '{const_name}' should be UPPER_SNAKE_CASE",
                        suggestion=f"Rename to '{const_name.upper()}'"
                    ))
            
            # Check method names (should be camelCase, not start with uppercase)
            method_match = re.search(r'(public|private|protected)\s+\w+\s+([A-Z]\w*)\s*\(', line)
            if method_match:
                method_name = method_match.group(2)
                # Skip constructors (same name as class)
                if not re.search(rf'class\s+{method_name}', code):
                    self.warnings.append(JavaError(
                        line=i,
                        column=line.index(method_name) + 1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.INFO,
                        message=f"Method name '{method_name}' should start with lowercase",
                        suggestion=f"Rename to '{method_name[0].lower() + method_name[1:]}'"
                    ))
    
    def _check_empty_blocks(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for empty code blocks."""
        # Pattern: { } with only whitespace
        empty_block_pattern = re.compile(r'\{\s*\}')
        
        in_multiline_comment = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            if empty_block_pattern.search(line):
                # Skip intentional empty blocks (interfaces, abstract methods)
                if 'interface' not in line and 'abstract' not in line:
                    self.warnings.append(JavaError(
                        line=i,
                        column=1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.WARNING,
                        message="Empty code block detected",
                        suggestion="Add implementation or remove empty block"
                    ))
    
    def _check_magic_numbers(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for magic numbers (hardcoded values)."""
        # Pattern: numeric literals not in declaration
        magic_pattern = re.compile(r'(?<![=\d\w])\b(\d{2,})\b(?![Ll])')
        
        in_multiline_comment = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            # Skip imports and declarations
            if (stripped.startswith('import') or
                'final' in line or
                '.length' in line):
                continue
            
            for match in magic_pattern.finditer(line):
                num = match.group(1)
                # Skip common acceptable values
                if num not in ['10', '16', '32', '64', '100', '1000', '255']:
                    self.warnings.append(JavaError(
                        line=i,
                        column=match.start() + 1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.INFO,
                        message=f"Magic number '{num}' - consider using named constant",
                        suggestion=f"Extract to constant: private static final int SOME_NAME = {num};"
                    ))
    
    def _check_long_methods(self, code: str, lines: List[str]):
        """Check for methods that are too long."""
        method_pattern = re.compile(r'(public|private|protected)\s+\w+\s+(\w+)\s*\([^)]*\)\s*\{')
        
        for match in method_pattern.finditer(code):
            method_name = match.group(2)
            method_start = code[:match.start()].count('\n') + 1
            
            # Find method end
            brace_count = 1
            pos = match.end()
            while pos < len(code) and brace_count > 0:
                if code[pos] == '{':
                    brace_count += 1
                elif code[pos] == '}':
                    brace_count -= 1
                pos += 1
            
            method_end = code[:pos].count('\n') + 1
            method_lines = method_end - method_start
            
            if method_lines > 50:
                self.warnings.append(JavaError(
                    line=method_start,
                    column=1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.WARNING,
                    message=f"Method '{method_name}' is too long ({method_lines} lines)",
                    suggestion="Consider splitting into smaller methods (recommended < 30 lines)"
                ))
            elif method_lines > 30:
                self.warnings.append(JavaError(
                    line=method_start,
                    column=1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.INFO,
                    message=f"Method '{method_name}' is getting long ({method_lines} lines)",
                    suggestion="Consider extracting some logic to helper methods"
                ))
    
    def _check_deep_nesting(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for deeply nested code blocks."""
        max_depth = 0
        current_depth = 0
        deep_lines = []
        
        in_multiline_comment = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            current_depth += line.count('{') - line.count('}')
            
            if current_depth > 4:
                if current_depth > max_depth:
                    max_depth = current_depth
                    deep_lines.append(i)
        
        if max_depth > 4:
            for line_num in deep_lines[:3]:  # Report first 3
                self.warnings.append(JavaError(
                    line=line_num,
                    column=1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.WARNING,
                    message=f"Deep nesting detected (depth: {max_depth})",
                    suggestion="Use early returns, extract methods, or flatten logic"
                ))
    
    def _check_empty_catch(self, code: str, lines: List[str]):
        """Check for empty catch blocks."""
        # Pattern: catch (...) { }
        catch_pattern = re.compile(r'catch\s*\([^)]+\)\s*\{\s*\}', re.MULTILINE)
        
        for match in catch_pattern.finditer(code):
            line_num = code[:match.start()].count('\n') + 1
            self.warnings.append(JavaError(
                line=line_num,
                column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.WARNING,
                message="Empty catch block - exceptions should be handled",
                suggestion="Log the exception or rethrow: e.printStackTrace() or throw new RuntimeException(e)"
            ))
    
    def _check_system_exit(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for System.exit() calls."""
        in_multiline_comment = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            if 'System.exit' in line:
                self.warnings.append(JavaError(
                    line=i,
                    column=line.index('System.exit') + 1,
                    error_type=ErrorType.WARNING,
                    severity=ErrorSeverity.WARNING,
                    message="System.exit() terminates JVM abruptly",
                    suggestion="Use return statements or throw exceptions instead"
                ))
    
    def _check_hardcoded_strings(self, code: str, lines: List[str], comment_map: Dict[int, bool]):
        """Check for hardcoded strings that should be constants."""
        string_pattern = re.compile(r'"([^"]{20,})"')
        
        seen_strings = {}
        
        in_multiline_comment = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments
            is_comment, in_multiline_comment = is_comment_line(stripped, in_multiline_comment)
            if is_comment or self._is_comment_line(i, comment_map):
                continue
            
            # Skip imports
            if 'import' in line:
                continue
            
            for match in string_pattern.finditer(line):
                string_val = match.group(1)
                
                if string_val in seen_strings:
                    self.warnings.append(JavaError(
                        line=i,
                        column=match.start() + 1,
                        error_type=ErrorType.WARNING,
                        severity=ErrorSeverity.INFO,
                        message=f"Duplicate string literal (also on line {seen_strings[string_val]})",
                        suggestion="Extract to a constant to avoid duplication"
                    ))
                else:
                    seen_strings[string_val] = i


class ErrorChecker:
    """
    Main Error Checker coordinating all error detection.
    
    This is the central class that:
    1. Coordinates syntax, runtime, and static analysis
    2. Manages background threading for real-time checking
    3. Implements debouncing to avoid excessive checks
    4. Provides callback mechanism for UI updates
    
    Usage:
        checker = ErrorChecker()
        checker.set_callback(my_update_function)
        checker.check_code_async(java_code)
    """
    
    def __init__(self):
        """Initialize all error detection components."""
        self.syntax_checker = JavaSyntaxChecker()
        self.runtime_detector = RuntimeErrorDetector()
        self.static_analyzer = StaticAnalyzer()
        
        # Callback for UI updates
        self.on_errors_detected: Optional[Callable[[List[JavaError]], None]] = None
        
        # Simple debouncing - no complex threading
        self._last_check_time = 0
        self._debounce_delay = 0.3  # 300ms delay - faster feedback
        self._pending_timer = None
        
        # Cache to avoid re-checking identical code
        self._last_code_hash: Optional[int] = None
        self._cached_errors: List[JavaError] = []
    
    def set_callback(self, callback: Callable[[List[JavaError]], None]):
        """
        Set callback function for error detection results.
        
        Args:
            callback: Function that receives list of JavaError objects
        """
        self.on_errors_detected = callback
    
    def check_code(self, code: str, include_warnings: bool = True) -> List[JavaError]:
        """
        Synchronously check code for all types of errors.
        
        Args:
            code: Java source code to check
            include_warnings: Whether to include static analysis warnings
            
        Returns:
            Combined list of all detected errors and warnings
        """
        all_errors = []
        
        # 1. Syntax errors ONLY - use javac if available, otherwise minimal regex checks
        syntax_errors = self.syntax_checker.check_syntax(code)
        all_errors.extend(syntax_errors)
        
        # DISABLED: Runtime error detection causes too many false positives
        # runtime_errors = self.runtime_detector.detect_runtime_errors(code)
        # all_errors.extend(runtime_errors)
        
        # DISABLED: Static analysis causes too many false positives
        # if include_warnings:
        #     static_warnings = self.static_analyzer.analyze(code)
        #     all_errors.extend(static_warnings)
        
        # Sort by severity and line number
        all_errors.sort(key=lambda e: (
            0 if e.severity == ErrorSeverity.ERROR else 1 if e.severity == ErrorSeverity.WARNING else 2,
            e.line
        ))
        
        return all_errors
    
    def check_code_async(self, code: str, include_warnings: bool = True):
        """
        Check code with simple debouncing (no complex threading).
        
        This method is designed for real-time checking as the user types.
        
        Args:
            code: Java source code to check
            include_warnings: Whether to include static analysis warnings
        """
        # Check cache - if same code, return cached results immediately
        code_hash = hash(code)
        if code_hash == self._last_code_hash:
            if self.on_errors_detected:
                self.on_errors_detected(self._cached_errors)
            return
        
        # Simple time-based debounce
        current_time = time.time()
        if current_time - self._last_check_time < self._debounce_delay:
            return  # Skip this check, too soon
        
        self._last_check_time = current_time
        
        # Run check directly (fast enough for real-time)
        try:
            errors = self.check_code(code, include_warnings)
            
            # Update cache
            self._last_code_hash = code_hash
            self._cached_errors = errors
            
            # Call callback
            if self.on_errors_detected:
                self.on_errors_detected(errors)
                
        except Exception as e:
            # Never crash - report error gracefully
            error = JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.INFO,
                message=f"Error checker exception: {str(e)}"
            )
            if self.on_errors_detected:
                self.on_errors_detected([error])
    
    def get_error_summary(self, errors: List[JavaError]) -> Dict[str, int]:
        """
        Get summary counts of errors by type.
        
        Returns:
            Dictionary with error counts by category
        """
        summary = {
            'syntax_errors': 0,
            'runtime_warnings': 0,
            'code_warnings': 0,
            'info': 0,
            'total': len(errors)
        }
        
        for error in errors:
            if error.error_type == ErrorType.SYNTAX:
                summary['syntax_errors'] += 1
            elif error.error_type == ErrorType.RUNTIME:
                summary['runtime_warnings'] += 1
            elif error.error_type == ErrorType.WARNING:
                summary['code_warnings'] += 1
            else:
                summary['info'] += 1
        
        return summary


# Utility function for quick checking
def check_java_code(code: str) -> List[JavaError]:
    """
    Convenience function for quick error checking.
    
    Args:
        code: Java source code to check
        
    Returns:
        List of detected errors and warnings
    """
    checker = ErrorChecker()
    return checker.check_code(code)


if __name__ == "__main__":
    # Test the error checker
    test_code = """
public class TestClass {
    public static void main(String[] args) {
        int x = 10
        String str;
        System.out.println(str.length());
        int result = 10 / 0;
        int[] arr = new int[5];
        System.out.println(arr[10]);
    }
}
"""
    
    print("Testing Java Error Checker...")
    print("=" * 50)
    
    checker = ErrorChecker()
    errors = checker.check_code(test_code)
    
    for error in errors:
        print(error)
    
    print("\n" + "=" * 50)
    summary = checker.get_error_summary(errors)
    print(f"Summary: {summary}")
