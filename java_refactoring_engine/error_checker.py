"""
Error Checker Module for Java Code
===================================
Provides **real-time, IDE-grade** error detection for Java source code,
comparable to the experience offered by IntelliJ IDEA or Eclipse.

Detection Layers
----------------
1. **Syntax Errors** – Missing semicolons, unmatched braces, undeclared
   variables, type mismatches, and other compilation-level issues.  Detected
   by delegating to ``javac`` when available, with a robust regex-based
   fallback for environments without a JDK.

2. **Runtime-Risk Warnings** – Static heuristics that predict common
   runtime exceptions (``NullPointerException``,
   ``ArrayIndexOutOfBoundsException``, division by zero, integer overflow,
   resource leaks).

3. **Code-Smell / Logical Warnings** – Empty ``catch`` blocks, magic
   numbers, unused variables, deep nesting, naming-convention violations,
   long methods, and more.

Architecture Highlights
-----------------------
* **Debouncer** – A thread-safe class that cancels-and-restarts a timer on
  every keystroke, ensuring the expensive ``check_java_code`` pipeline runs
  only *after* the user pauses typing (configurable delay, default 600 ms).
  This keeps the Electron/Monaco UI fully responsive.

* **Observer / Callback Pattern** – ``ErrorChecker.set_callback()`` lets
  the UI layer register a listener that receives ``List[JavaError]`` on a
  background thread, decoupling detection from rendering.

* **Caching** – Identical source text is never analysed twice in a row;
  a hash-based cache short-circuits repeated checks instantly.

* **Structured Output** – Every finding is a ``JavaError`` dataclass with
  ``line``, ``column``, ``message``, ``severity``, and ``error_type``,
  serialisable to JSON for the FastAPI ``/check-errors`` endpoint.

Author: Java Refactoring Engine – CodeNova IDE
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable, Dict, Set, Tuple


# ──────────────────────────────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────────────────────────────

class ErrorType(Enum):
    """Classification of error types detected by the checker.

    SYNTAX  – Compilation errors caught by ``javac`` or regex heuristics.
    RUNTIME – Errors that would occur during execution.
    WARNING – Code-quality issues and potential bugs.
    INFO    – Informational messages and suggestions.
    """
    SYNTAX  = "syntax"
    RUNTIME = "runtime"
    WARNING = "warning"
    INFO    = "info"


class ErrorSeverity(Enum):
    """Severity levels for prioritising error display.

    ERROR   – Must be fixed for the code to compile / run.
    WARNING – Should be fixed but the code may still work.
    INFO    – Suggestions for improvement.
    """
    ERROR   = "error"
    WARNING = "warning"
    INFO    = "info"


# ──────────────────────────────────────────────────────────────────────
# JavaError dataclass
# ──────────────────────────────────────────────────────────────────────

@dataclass
class JavaError:
    """A single detected error, warning, or informational finding.

    Attributes
    ----------
    line : int
        1-indexed line number where the issue occurs.
    column : int
        1-indexed column number where the issue occurs.
    error_type : ErrorType
        Category of the finding (syntax / runtime / warning / info).
    severity : ErrorSeverity
        How critical the finding is.
    message : str
        Human-readable description of the problem.
    suggestion : str | None
        Optional recommended fix.
    code_snippet : str | None
        The problematic code segment (when available).
    """
    line: int
    column: int
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None

    # ── Serialisation helpers ──────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to a plain dictionary suitable for JSON responses."""
        return {
            "line":        self.line,
            "column":      self.column,
            "type":        self.error_type.value,
            "severity":    self.severity.value,
            "message":     self.message,
            "suggestion":  self.suggestion,
            "code_snippet": self.code_snippet,
        }

    def __str__(self) -> str:
        """Friendly string for the IDE error-panel."""
        icons = {
            ErrorType.SYNTAX:  "❌",
            ErrorType.RUNTIME: "⚠️",
            ErrorType.WARNING: "💡",
            ErrorType.INFO:    "ℹ️",
        }
        return f"{icons.get(self.error_type, '•')} Line {self.line}: {self.message}"


# ──────────────────────────────────────────────────────────────────────
# Debouncer – thread-safe keystroke debouncing
# ──────────────────────────────────────────────────────────────────────

class Debouncer:
    """Cancel-and-restart timer that fires a callback once the user stops typing.

    **Why debouncing matters (supervisor note)**
    Without debouncing, every single keystroke would trigger a full
    ``javac`` compilation + regex + static-analysis pipeline, overwhelming
    the CPU and freezing the UI.  The *Debouncer* ensures only **one**
    analysis run happens per typing pause, dramatically reducing resource
    usage while maintaining sub-second feedback latency.

    Thread-safety is ensured via a ``threading.Lock`` that serialises
    access to the internal ``threading.Timer``.

    Parameters
    ----------
    delay : float
        Seconds to wait after the last call before firing (default 0.6).
    callback : Callable
        The function to invoke when the timer fires.
    """

    def __init__(self, delay: float = 0.6, callback: Optional[Callable] = None):
        self._delay = delay
        self._callback = callback
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    @property
    def delay(self) -> float:
        return self._delay

    @delay.setter
    def delay(self, value: float) -> None:
        self._delay = max(0.1, value)  # floor at 100 ms

    def trigger(self, *args, **kwargs) -> None:
        """Schedule (or reschedule) the callback.

        If a previous timer is pending it is cancelled first, ensuring only
        the **latest** invocation fires after the full delay elapses.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self._delay,
                self._fire,
                args=args,
                kwargs=kwargs,
            )
            self._timer.daemon = True   # don't block process exit
            self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending invocation."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _fire(self, *args, **kwargs) -> None:
        """Internal – invoke the registered callback."""
        if self._callback is not None:
            self._callback(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Comment-stripping utilities
# ──────────────────────────────────────────────────────────────────────

def strip_java_comments(code: str) -> Tuple[str, Dict[int, bool]]:
    """Remove comments from Java code while preserving line numbers.

    Returns
    -------
    tuple[str, dict[int, bool]]
        ``(code_without_comments, comment_line_map)`` where the map marks
        every line number that was wholly a comment.
    """
    lines = code.split("\n")
    result_lines: List[str] = []
    comment_lines: Dict[int, bool] = {}
    in_multiline = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Inside a block comment ─────────────────────────────────
        if in_multiline:
            comment_lines[i] = True
            if "*/" in line:
                in_multiline = False
                after = line[line.index("*/") + 2:]
                result_lines.append(after if after.strip() else "")
            else:
                result_lines.append("")
            continue

        # Start of block comment ─────────────────────────────────
        if "/*" in stripped:
            comment_lines[i] = True
            if "*/" in stripped:
                line = re.sub(r"/\*.*?\*/", "", line)
            else:
                in_multiline = True
                result_lines.append(line[: line.index("/*")])
                continue

        # Full-line single-line comment / Javadoc continuation ───
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/**"):
            comment_lines[i] = True
            result_lines.append("")
            continue

        # Inline // comment (outside strings) ────────────────────
        if "//" in line:
            in_str = False
            for idx, ch in enumerate(line):
                if ch == '"' and (idx == 0 or line[idx - 1] != "\\"):
                    in_str = not in_str
                elif not in_str and line[idx: idx + 2] == "//":
                    line = line[:idx]
                    if not line.strip():
                        comment_lines[i] = True
                    break

        result_lines.append(line)

    return "\n".join(result_lines), comment_lines


def is_comment_line(line: str, in_multiline: bool = False) -> Tuple[bool, bool]:
    """Return ``(is_comment, still_in_multiline)`` for a single line."""
    stripped = line.strip()

    if in_multiline:
        return (True, "*/" not in stripped)

    if stripped.startswith("//"):
        return True, False
    if stripped.startswith("/*"):
        return (True, "*/" not in stripped)
    if stripped.startswith("*") or stripped.startswith("/**"):
        return True, in_multiline

    return False, False


# ──────────────────────────────────────────────────────────────────────
# JavaSyntaxChecker – javac-backed + regex fallback
# ──────────────────────────────────────────────────────────────────────

class JavaSyntaxChecker:
    """Detect compilation-level syntax errors.

    **Primary strategy** – write the source to a temp ``.java`` file and run
    ``javac -Xlint:all``.  This catches the full spectrum of syntax errors
    with zero false positives.

    **Fallback strategy** – when no JDK is installed, a hand-tuned set of
    regex rules checks for the most common issues (unmatched brackets,
    missing semicolons, type mismatches).
    """

    # Shared across instances: a new JavaSyntaxChecker is created per request
    # (and inside BehaviorPreservationProtocol), and per-instance mkdtemp()
    # leaked one orphan directory per check. javac discovery is also cached —
    # it shells out `javac -version` for up to 8 candidate paths otherwise.
    _shared_temp_dir: Optional[str] = None
    _cached_javac: Optional[str] = None
    _javac_searched: bool = False

    def __init__(self) -> None:
        if JavaSyntaxChecker._shared_temp_dir is None:
            JavaSyntaxChecker._shared_temp_dir = tempfile.mkdtemp(prefix="java_checker_")
        self._temp_dir = JavaSyntaxChecker._shared_temp_dir
        if not JavaSyntaxChecker._javac_searched:
            JavaSyntaxChecker._cached_javac = self._find_javac()
            JavaSyntaxChecker._javac_searched = True
        self._javac_path = JavaSyntaxChecker._cached_javac

    # ── JDK discovery ─────────────────────────────────────────────

    def _find_javac(self) -> Optional[str]:
        """Locate ``javac`` on the host, checking JAVA_HOME first."""
        candidates: List[str] = []

        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            candidates.append(os.path.join(java_home, "bin", "javac.exe"))
            candidates.append(os.path.join(java_home, "bin", "javac"))

        candidates += [
            "javac",
            r"C:\Program Files\Java\jdk-21\bin\javac.exe",
            r"C:\Program Files\Java\jdk-17\bin\javac.exe",
            r"C:\Program Files\Java\jdk-11\bin\javac.exe",
            r"C:\Program Files\Java\jdk1.8.0_351\bin\javac.exe",
            "/usr/bin/javac",
            "/usr/local/bin/javac",
        ]

        for path in candidates:
            try:
                result = subprocess.run(
                    [path, "-version"], capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        return None

    # ── Public API ────────────────────────────────────────────────

    def check_syntax(self, code: str, sourcepath: Optional[str] = None) -> List[JavaError]:
        """Return syntax errors for *code*.

        Delegates to ``javac`` when available (with cross-file resolution
        when *sourcepath* is given); otherwise uses the javalang parser for
        exact syntax errors plus regex heuristics for extra detail.
        """
        if not self._javac_path:
            errors = self._javalang_syntax_check(code)
            if errors:
                # Parser pinpointed the failure — regex bracket noise would
                # only duplicate/contradict it.
                errors.extend(self._check_type_mismatches(code.split("\n")))
                return errors
            # Parses cleanly: only run the cheap semantic heuristics.
            return self._check_type_mismatches(code.split("\n"))
        return self._check_syntax_javac(code, sourcepath=sourcepath)

    @staticmethod
    def _javalang_syntax_check(code: str) -> List[JavaError]:
        """Exact syntax validation via the javalang parser (no JDK needed).

        Replaces the old regex-only fallback, which missed malformed
        constructs and mis-flagged valid code. javalang reports the precise
        token where parsing failed.
        """
        try:
            import javalang
            javalang.parse.parse(code)
            return []
        except Exception as exc:
            line, column = 1, 1
            message = "Syntax error"
            at = getattr(exc, "at", None)
            pos = getattr(at, "position", None) if at is not None else None
            if pos is not None:
                line, column = pos[0], pos[1]
            desc = getattr(exc, "description", None) or str(exc)
            if desc:
                message = f"Syntax error: {desc}"
            token_val = getattr(at, "value", None) if at is not None else None
            if token_val:
                message += f" (near '{token_val}')"
            return [JavaError(
                line=line, column=column,
                error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                message=message,
                suggestion="Fix the syntax at the indicated position",
            )]

    def _check_syntax_javac(self, code: str, sourcepath: Optional[str] = None) -> List[JavaError]:
        """javac-backed check. With *sourcepath* (the workspace root), javac
        resolves references to the project's other classes, enabling REAL
        cross-file diagnostics instead of suppressing them."""
        class_name = self._extract_class_name(code)
        if not class_name:
            class_name = "TempClass"
            if "class " not in code:
                code = f"public class {class_name} {{\n{code}\n}}"

        temp_file = os.path.join(self._temp_dir, f"{class_name}.java")
        errors: List[JavaError] = []

        cmd = [self._javac_path, "-Xlint:all"]
        if sourcepath and os.path.isdir(sourcepath):
            cmd += ["-sourcepath", sourcepath, "-implicit:none"]
        cmd.append(temp_file)

        try:
            with open(temp_file, "w", encoding="utf-8") as fh:
                fh.write(code)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            errors.extend(self._parse_javac_output(
                result.stderr, code,
                cross_file_resolved=bool(sourcepath),
            ))

        except subprocess.TimeoutExpired:
            errors.append(JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.WARNING,
                message="Syntax check timed out – code may be too complex",
            ))
        except Exception as exc:
            errors.append(JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING,
                severity=ErrorSeverity.INFO,
                message=f"Syntax check error: {exc}",
            ))
        finally:
            for ext in (".java", ".class"):
                path = temp_file.replace(".java", ext)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass

        return errors

    # ── javac output parser ───────────────────────────────────────

    _JAVAC_ERROR_RE = re.compile(
        r".*\.java:(\d+):\s*(error|warning):\s*(.+)"
    )

    def _parse_javac_output(
        self, output: str, original_code: str,
        cross_file_resolved: bool = False,
    ) -> List[JavaError]:
        """Parse ``javac`` stderr into structured ``JavaError`` objects.

        ``javac`` emits blocks of the form::

            Filename.java:42: error: ';' expected
                    int x = 10
                               ^

        We extract the **line number**, **severity**, **message**, and
        **column** (from the caret position).
        """
        errors: List[JavaError] = []
        lines = output.strip().split("\n")

        i = 0
        while i < len(lines):
            match = self._JAVAC_ERROR_RE.match(lines[i])
            if match:
                line_num = int(match.group(1))
                kind = match.group(2)
                message = match.group(3).strip()

                snippet: Optional[str] = None
                column = 1

                # Next line is usually the source snippet
                if i + 1 < len(lines):
                    snippet = lines[i + 1].strip()
                # Line after that may contain the caret marker
                if i + 2 < len(lines) and "^" in lines[i + 2]:
                    column = lines[i + 2].index("^") + 1

                # Cross-file "cannot find symbol": only suppress when we
                # compiled WITHOUT a sourcepath (single-file mode, where
                # missing project classes are expected). With -sourcepath
                # the reference genuinely doesn't exist — report it.
                if "cannot find symbol" in message and not cross_file_resolved:
                    # Peek ahead for the "symbol: class ..." detail line
                    is_class_dep = False
                    for peek in range(i + 1, min(i + 5, len(lines))):
                        peek_line = lines[peek].strip()
                        if peek_line.startswith("symbol:") and "class " in peek_line:
                            is_class_dep = True
                            break
                        if peek_line.startswith("symbol:") and "variable " in peek_line:
                            # Check if the variable name looks like a class (Uppercase)
                            parts = peek_line.split("variable")
                            if len(parts) > 1 and parts[1].strip()[:1].isupper():
                                is_class_dep = True
                            break
                    if is_class_dep:
                        i += 1
                        continue

                error_type = ErrorType.SYNTAX if kind == "error" else ErrorType.WARNING
                severity = ErrorSeverity.ERROR if kind == "error" else ErrorSeverity.WARNING

                errors.append(JavaError(
                    line=line_num,
                    column=column,
                    error_type=error_type,
                    severity=severity,
                    message=message,
                    suggestion=self._suggest_fix(message),
                    code_snippet=snippet,
                ))
            i += 1

        return errors

    # ── Suggestion engine ─────────────────────────────────────────

    _SUGGESTION_MAP: List[Tuple[str, str]] = [
        ("';' expected",                           "Add a semicolon at the end of the statement"),
        ("cannot find symbol",                     "Check variable / method name spelling or add an import"),
        ("incompatible types",                     "Ensure type compatibility or add an explicit cast"),
        ("missing return statement",               "Add a return statement for all code paths"),
        ("unreachable statement",                  "Remove or restructure unreachable code"),
        (r"variable .* might not have been init",  "Initialise the variable before use"),
        ("illegal start of expression",            "Check for missing braces or incorrect syntax"),
        (r"class .* is public",                    "The class name must match the filename"),
        ("reached end of file while parsing",      "Add missing closing brace '}'"),
        ("unclosed string literal",                "Add the closing quote to the string"),
        ("not a statement",                        "Verify the expression is a valid statement (e.g. method call)"),
        ("already defined",                        "Rename or remove the duplicate declaration"),
        ("non-static .* cannot be referenced",     "Use an instance or mark the member as static"),
    ]

    def _suggest_fix(self, error_message: str) -> Optional[str]:
        """Return a human-readable fix suggestion for *error_message*."""
        for pattern, suggestion in self._SUGGESTION_MAP:
            if re.search(pattern, error_message, re.IGNORECASE):
                return suggestion
        return None

    # ── Class-name extraction ─────────────────────────────────────

    @staticmethod
    def _extract_class_name(code: str) -> Optional[str]:
        m = re.search(r"public\s+class\s+(\w+)", code)
        if m:
            return m.group(1)
        m = re.search(r"class\s+(\w+)", code)
        return m.group(1) if m else None

    # ── Regex-based fallback syntax checker ───────────────────────

    def _regex_syntax_check(self, code: str) -> List[JavaError]:
        """Heuristic syntax check when ``javac`` is unavailable.

        Tracks brace / parenthesis / bracket stacks, detects missing
        semicolons, and catches type mismatches.
        """
        errors: List[JavaError] = []
        lines = code.split("\n")

        brace_stack: List[Tuple[int, int, str]] = []
        paren_stack: List[Tuple[int, int, str]] = []
        square_stack: List[Tuple[int, int]] = []
        in_multiline = False

        for i, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()

            # ── comment handling ──────────────────────────────────
            if in_multiline:
                if "*/" in raw_line:
                    in_multiline = False
                    after = raw_line[raw_line.index("*/") + 2:]
                    if not after.strip():
                        continue
                    stripped = after.strip()
                else:
                    continue

            if "/*" in stripped:
                if "*/" not in stripped:
                    in_multiline = True
                continue

            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/**"):
                continue
            if stripped.startswith("@") or not stripped:
                continue

            # ── strip inline comments ─────────────────────────────
            code_part = stripped
            in_str = False
            for idx, ch in enumerate(code_part):
                if ch == '"' and (idx == 0 or code_part[idx - 1] != "\\"):
                    in_str = not in_str
                elif not in_str and code_part[idx: idx + 2] == "//":
                    code_part = code_part[:idx].strip()
                    break

            # ── remove string/char literals for bracket analysis ──
            bracket_line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code_part)
            bracket_line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", bracket_line)

            for j, char in enumerate(bracket_line):
                if char == "{":
                    ctx = "method" if "(" in bracket_line[:j] else "block"
                    brace_stack.append((i, j + 1, ctx))
                elif char == "}":
                    if brace_stack:
                        brace_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j + 1,
                            error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                            message="Unmatched closing brace '}'",
                            suggestion="Remove extra '}' or add matching '{'",
                        ))

                if char == "(":
                    paren_stack.append((i, j + 1, code_part[:30]))
                elif char == ")":
                    if paren_stack:
                        paren_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j + 1,
                            error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                            message="Unmatched closing parenthesis ')'",
                            suggestion="Remove extra ')' or add matching '('",
                        ))

                if char == "[":
                    square_stack.append((i, j + 1))
                elif char == "]":
                    if square_stack:
                        square_stack.pop()
                    else:
                        errors.append(JavaError(
                            line=i, column=j + 1,
                            error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                            message="Unmatched closing bracket ']'",
                            suggestion="Remove extra ']' or add matching '['",
                        ))

            # ── missing semicolons ────────────────────────────────
            is_continued = False
            if i < len(lines):
                for nxt_idx in range(i, min(i + 3, len(lines))):
                    nxt = lines[nxt_idx].strip()
                    if not nxt or nxt.startswith("//") or nxt.startswith("*"):
                        continue
                    if nxt.startswith(".") or nxt.startswith("+") or nxt.startswith("-"):
                        is_continued = True
                    break

            if code_part and not code_part.endswith(("{", "}", ";", ",", ":", "(", ")")) and not is_continued:
                if re.match(r"^(return|break|continue|throw)\s", code_part):
                    errors.append(JavaError(
                        line=i, column=len(raw_line),
                        error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                        message="Missing semicolon after statement",
                        suggestion="Add ';' at the end of the statement",
                    ))
                elif re.match(r"^\w+\s+\w+\s*=", code_part) and not code_part.endswith("{"):
                    if not re.search(r"[+\-*/&|^]$", code_part):
                        errors.append(JavaError(
                            line=i, column=len(raw_line),
                            error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                            message="Missing semicolon after declaration",
                            suggestion="Add ';' at the end of the declaration",
                        ))
                elif re.match(r"^\w+\[\]\s+\w+\s*=", code_part):
                    if not re.search(r"[+\-*/&|^]$", code_part):
                        errors.append(JavaError(
                            line=i, column=len(raw_line),
                            error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                            message="Missing semicolon after array declaration",
                            suggestion="Add ';' at the end of the declaration",
                        ))

        # ── unclosed delimiters ───────────────────────────────────
        for ln, col, _ in brace_stack:
            errors.append(JavaError(
                line=ln, column=col,
                error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                message=f"Unclosed brace '{{' (opened at line {ln})",
                suggestion="Add matching '}}' to close the block",
            ))
        for ln, col, _ in paren_stack:
            errors.append(JavaError(
                line=ln, column=col,
                error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                message=f"Unclosed parenthesis '(' (opened at line {ln})",
                suggestion="Add matching ')' to close",
            ))
        for ln, col in square_stack:
            errors.append(JavaError(
                line=ln, column=col,
                error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                message=f"Unclosed bracket '[' (opened at line {ln})",
                suggestion="Add matching ']' to close",
            ))

        # ── type-mismatch heuristics ──────────────────────────────
        errors.extend(self._check_type_mismatches(lines))
        return errors

    # ── Type-mismatch helpers ─────────────────────────────────────

    @staticmethod
    def _check_type_mismatches(lines: List[str]) -> List[JavaError]:
        """Detect obvious type mismatches (e.g. ``int x = "hello";``)."""
        errors: List[JavaError] = []

        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue

            # numeric_type var = "string"
            m = re.match(
                r"(int|long|short|byte|float|double|boolean|char)\s+(\w+)\s*=\s*\"[^\"]*\"",
                stripped,
            )
            if m:
                errors.append(JavaError(
                    line=i, column=stripped.index("=") + 1,
                    error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                    message=f"Type mismatch: cannot assign String to {m.group(1)}",
                    suggestion=f"Change type to String or assign a {m.group(1)} value",
                ))

            # String var = bare_number
            m = re.match(r"String\s+(\w+)\s*=\s*(\d+)\s*;", stripped)
            if m:
                errors.append(JavaError(
                    line=i, column=stripped.index("=") + 1,
                    error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                    message="Type mismatch: cannot assign int to String",
                    suggestion=f'Use String.valueOf({m.group(2)}) or "{m.group(2)}"',
                ))

            # boolean var = "true"/"false" (literal string)
            m = re.match(r'boolean\s+(\w+)\s*=\s*"(true|false)"', stripped)
            if m:
                errors.append(JavaError(
                    line=i, column=stripped.index("=") + 1,
                    error_type=ErrorType.SYNTAX, severity=ErrorSeverity.ERROR,
                    message="Type mismatch: cannot assign String to boolean",
                    suggestion=f"Use {m.group(2)} without quotes",
                ))

        return errors


# ──────────────────────────────────────────────────────────────────────
# RuntimeErrorDetector – static heuristics for runtime risks
# ──────────────────────────────────────────────────────────────────────

class RuntimeErrorDetector:
    """Predict common runtime exceptions via **static pattern analysis**.

    This is *not* execution-based; it applies conservative heuristics that
    flag code patterns statistically correlated with runtime failures:

    * **NullPointerException** – method call on a declared-but-uninitialised
      reference.
    * **ArrayIndexOutOfBoundsException** – hardcoded large indices or
      expressions that may yield negative indices.
    * **ArithmeticException** – literal division / modulo by zero.
    * **Integer overflow** – literals exceeding ``Integer.MAX_VALUE``.
    * **Resource leaks** – I/O resources opened outside ``try-with-resources``.
    """

    _WELL_KNOWN_CLASSES: Set[str] = {
        "System", "Math", "String", "Integer", "Arrays", "Collections",
        "Objects", "Optional", "List", "Map", "Set", "Long", "Double",
        "Float", "Boolean", "Character", "Byte", "Short",
    }

    def __init__(self) -> None:
        self._java_path = self._find_java()

    @staticmethod
    def _find_java() -> Optional[str]:
        candidates = ["java", "java.exe"]
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            candidates.insert(0, os.path.join(java_home, "bin", "java"))
            candidates.insert(0, os.path.join(java_home, "bin", "java.exe"))
        for path in candidates:
            try:
                result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        return None

    # ── Public entry ──────────────────────────────────────────────

    _METHOD_START_RE = re.compile(
        r'(?:public|private|protected|static|final|synchronized|\s)+[\w\<\>\[\]]+\s+\w+\s*\([^)]*\)\s*(?:throws[^{]+)?\{'
    )
    _NEW_ARRAY_RE = re.compile(r'(\w+)\s*=\s*new\s+\w+\s*\[\s*(\d+)\s*\]')

    def detect_runtime_errors(self, code: str) -> List[JavaError]:
        """Run all runtime-risk heuristics and return findings.

        Variable state is SCOPED PER METHOD: hitting a new method signature
        resets declaration/initialisation tracking. The previous file-linear
        tracking bled state between methods (a variable declared-but-null in
        method A poisoned an identically named, initialised variable in
        method B), causing false NullPointerException warnings.
        """
        errors: List[JavaError] = []
        lines = code.split("\n")

        declared_vars: Dict[str, int] = {}
        initialised_vars: Set[str] = set()
        array_sizes: Dict[str, int] = {}
        in_multiline = False

        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_comment, in_multiline = is_comment_line(stripped, in_multiline)
            if is_comment:
                continue

            # Strip inline comments for analysis
            line = raw
            if "//" in line:
                line = line[: line.index("//")]

            # New method → fresh scope.
            if self._METHOD_START_RE.search(line):
                declared_vars = {}
                initialised_vars = set()
                array_sizes = {}

            # Track literal array allocations: int[] a = new int[5];
            for m in self._NEW_ARRAY_RE.finditer(line):
                try:
                    array_sizes[m.group(1)] = int(m.group(2))
                except ValueError:
                    pass

            errors.extend(self._check_null_pointer(line, i, declared_vars, initialised_vars))
            errors.extend(self._check_array_bounds(line, i, array_sizes))
            errors.extend(self._check_division_by_zero(line, i))
            errors.extend(self._check_integer_overflow(line, i))
            errors.extend(self._check_resource_leaks(line, i, code))
            self._track_variables(line, i, declared_vars, initialised_vars)

        return errors

    # ── Individual checks ─────────────────────────────────────────

    _METHOD_CALL_RE = re.compile(r"(\w+)\.([\w]+)\s*\(")

    def _check_null_pointer(
        self, line: str, line_num: int,
        declared: Dict[str, int], initialised: Set[str],
    ) -> List[JavaError]:
        """Flag method calls on variables declared but never initialised."""
        errors: List[JavaError] = []
        for m in self._METHOD_CALL_RE.finditer(line):
            var = m.group(1)
            if var in declared and var not in initialised and var not in self._WELL_KNOWN_CLASSES:
                errors.append(JavaError(
                    line=line_num, column=m.start() + 1,
                    error_type=ErrorType.RUNTIME, severity=ErrorSeverity.WARNING,
                    message=f"Potential NullPointerException: '{var}' may be null",
                    suggestion=f"Add null check: if ({var} != null) {{ … }}",
                ))
        return errors

    _ARRAY_ACCESS_RE = re.compile(r"(\w+)\[(\d+)]")
    _NEG_INDEX_RE    = re.compile(r"(\w+)\[(\w+)\s*-\s*\d+]")

    def _check_array_bounds(
        self, line: str, line_num: int,
        array_sizes: Optional[Dict[str, int]] = None,
    ) -> List[JavaError]:
        """Flag literal indices PROVABLY out of bounds for arrays whose size
        is known from a literal `new T[N]` in the same method. The old
        heuristic ("index > 100 is suspicious") produced pure noise: it
        flagged valid accesses and missed real ones like arr[10] on new
        int[5]. This version only reports certainties."""
        errors: List[JavaError] = []
        sizes = array_sizes or {}
        for m in self._ARRAY_ACCESS_RE.finditer(line):
            name, idx = m.group(1), int(m.group(2))
            if name in sizes and idx >= sizes[name]:
                errors.append(JavaError(
                    line=line_num, column=m.start() + 1,
                    error_type=ErrorType.RUNTIME, severity=ErrorSeverity.ERROR,
                    message=(f"ArrayIndexOutOfBoundsException: index {idx} on "
                             f"'{name}' of length {sizes[name]}"),
                    suggestion=f"Valid indices for '{name}' are 0..{sizes[name] - 1}",
                ))
        for m in self._NEG_INDEX_RE.finditer(line):
            errors.append(JavaError(
                line=line_num, column=m.start() + 1,
                error_type=ErrorType.RUNTIME, severity=ErrorSeverity.WARNING,
                message="Potential negative array index",
                suggestion="Add bounds check: if (index >= 0 && index < array.length)",
            ))
        return errors

    @staticmethod
    def _check_division_by_zero(line: str, line_num: int) -> List[JavaError]:
        errors: List[JavaError] = []
        if re.search(r"/\s*0(?![.\d])", line):
            errors.append(JavaError(
                line=line_num, column=line.index("/") + 1,
                error_type=ErrorType.RUNTIME, severity=ErrorSeverity.ERROR,
                message="Division by zero detected",
                suggestion="Ensure divisor is not zero before division",
            ))
        if re.search(r"%\s*0(?![.\d])", line):
            errors.append(JavaError(
                line=line_num, column=line.index("%") + 1,
                error_type=ErrorType.RUNTIME, severity=ErrorSeverity.ERROR,
                message="Modulo by zero detected",
                suggestion="Ensure divisor is not zero before modulo operation",
            ))
        return errors

    _LARGE_INT_RE = re.compile(r"\b(\d{10,})\b")

    def _check_integer_overflow(self, line: str, line_num: int) -> List[JavaError]:
        errors: List[JavaError] = []
        for m in self._LARGE_INT_RE.finditer(line):
            try:
                val = int(m.group(1))
                if val > 2_147_483_647:
                    errors.append(JavaError(
                        line=line_num, column=m.start() + 1,
                        error_type=ErrorType.RUNTIME, severity=ErrorSeverity.WARNING,
                        message=f"Integer overflow: {m.group(1)} exceeds Integer.MAX_VALUE",
                        suggestion=f"Use 'long' type or add 'L' suffix (e.g., {m.group(1)}L)",
                    ))
            except ValueError:
                pass
        return errors

    _RESOURCE_PATTERNS: List[Tuple[str, str]] = [
        (r"new\s+FileInputStream\s*\(",   "FileInputStream"),
        (r"new\s+FileOutputStream\s*\(",  "FileOutputStream"),
        (r"new\s+BufferedReader\s*\(",     "BufferedReader"),
        (r"new\s+BufferedWriter\s*\(",     "BufferedWriter"),
        (r"new\s+Scanner\s*\(",           "Scanner"),
        (r"new\s+PrintWriter\s*\(",       "PrintWriter"),
    ]

    def _check_resource_leaks(self, line: str, line_num: int, full_code: str) -> List[JavaError]:
        errors: List[JavaError] = []
        for pattern, resource in self._RESOURCE_PATTERNS:
            if re.search(pattern, line):
                line_index = full_code.find(line)
                preceding = full_code[max(0, line_index - 200): line_index] if line_index > 0 else ""
                if "try (" not in preceding and "try(" not in preceding:
                    errors.append(JavaError(
                        line=line_num, column=line.index("new") + 1,
                        error_type=ErrorType.RUNTIME, severity=ErrorSeverity.WARNING,
                        message=f"Potential resource leak: {resource} not in try-with-resources",
                        suggestion=(
                            f"Use try-with-resources: try ({resource} r = "
                            f"new {resource}(…)) {{ }}"
                        ),
                    ))
        return errors

    # ── Variable tracking ─────────────────────────────────────────

    _DECL_RE   = re.compile(r"(String|int|long|double|float|boolean|char|byte|short|\w+(?:<[^>]+>)?)\s+(\w+)\s*;")
    _INIT_RE   = re.compile(r"(String|int|long|double|float|boolean|char|byte|short|\w+(?:<[^>]+>)?)\s+(\w+)\s*=")
    _ASSIGN_RE = re.compile(r"^\s*(\w+)\s*=\s*(?!null)")

    def _track_variables(
        self, line: str, line_num: int,
        declared: Dict[str, int], initialised: Set[str],
    ) -> None:
        for m in self._DECL_RE.finditer(line):
            declared[m.group(2)] = line_num
        for m in self._INIT_RE.finditer(line):
            declared[m.group(2)] = line_num
            if "= null" not in line:
                initialised.add(m.group(2))
        m = self._ASSIGN_RE.match(line)
        if m:
            initialised.add(m.group(1))


# ──────────────────────────────────────────────────────────────────────
# StaticAnalyzer – code smells & best-practice warnings
# ──────────────────────────────────────────────────────────────────────

class StaticAnalyzer:
    """Lightweight static analyser (similar to PMD / Checkstyle) in pure Python.

    Detects:
    * Unused / duplicate imports
    * Empty ``catch`` blocks
    * Magic numbers
    * Unused variables
    * Naming-convention violations
    * Long methods (> 50 lines)
    * Deep nesting (> 4 levels)
    """

    def __init__(self) -> None:
        self.warnings: List[JavaError] = []

    # ── Public entry ──────────────────────────────────────────────

    def analyze(self, code: str) -> List[JavaError]:
        """Run all enabled static-analysis checks and return findings."""
        self.warnings = []
        lines = code.split("\n")
        code_stripped, comment_map = strip_java_comments(code)

        self._check_unused_imports(code_stripped, lines, comment_map)
        self._check_empty_catch(code, lines)
        self._check_magic_numbers(code_stripped, lines, comment_map)
        self._check_unused_variables(code_stripped, lines, comment_map)
        self._check_naming_conventions(code_stripped, lines, comment_map)
        self._check_long_methods(code, lines)
        self._check_deep_nesting(code_stripped, lines, comment_map)
        self._check_empty_blocks(code_stripped, lines, comment_map)

        return self.warnings

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _is_comment(line_num: int, cmap: Dict[int, bool]) -> bool:
        return cmap.get(line_num, False)

    # ── unused imports ────────────────────────────────────────────

    _IMPORT_RE = re.compile(r"^import\s+(static\s+)?([a-zA-Z_][\w.]*(?:\.\*)?)\s*;")

    _IMPLICITLY_USED: Set[str] = {
        "List", "ArrayList", "Map", "HashMap", "Set", "HashSet", "LinkedList",
        "TreeMap", "TreeSet", "LinkedHashMap", "LinkedHashSet", "Queue", "Deque",
        "Stack", "Vector", "Collections", "Arrays", "Objects", "Optional",
        "Stream", "Collectors", "Function", "Predicate", "Consumer", "Supplier",
        "BigDecimal", "BigInteger", "Date", "Calendar", "LocalDate",
        "LocalDateTime", "LocalTime", "Instant", "Duration", "Period",
        "ZonedDateTime", "Pattern", "Matcher", "StringBuilder", "StringBuffer",
        "File", "Path", "Paths", "Files", "IOException", "Exception",
        "RuntimeException", "IllegalArgumentException", "NullPointerException",
        "Scanner", "PrintWriter", "BufferedReader", "BufferedWriter",
        "InputStream", "OutputStream", "Reader", "Writer",
        "Thread", "Runnable", "Callable", "Future", "ExecutorService",
        "Comparator", "Comparable", "Iterator", "Iterable",
        "Math", "System", "String", "Integer", "Long", "Double", "Float",
        "Boolean", "Character", "Byte", "Short", "Number", "Object", "Class",
        "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface",
        "Serializable", "Cloneable", "AutoCloseable", "Closeable",
    }

    def _check_unused_imports(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        imports: List[Tuple[int, str, str, bool]] = []
        seen: Set[str] = set()

        for i, raw in enumerate(lines, 1):
            if self._is_comment(i, cmap):
                continue
            m = self._IMPORT_RE.match(raw.strip())
            if not m:
                continue

            is_static = m.group(1) is not None
            full = m.group(2)

            if full in seen:
                self.warnings.append(JavaError(
                    line=i, column=1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                    message=f"Duplicate import: '{full}'",
                    suggestion="Remove the duplicate import statement",
                ))
                continue
            seen.add(full)

            if full.endswith(".*"):
                continue  # can't determine usage for wildcard imports

            class_name = full.split(".")[-1]
            imports.append((i, full, class_name, is_static))

        # Build "body" text (no import lines) for usage scanning
        body_lines = [l for l in lines if not l.strip().startswith("import ")]
        body = "\n".join(body_lines)

        for ln, full_import, cls, _ in imports:
            if cls in self._IMPLICITLY_USED:
                continue
            if not re.search(r"\b" + re.escape(cls) + r"\b", body):
                self.warnings.append(JavaError(
                    line=ln, column=1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                    message=f"Unused import: '{full_import}'",
                    suggestion="Remove the unused import statement",
                ))

    # ── empty catch blocks ────────────────────────────────────────

    _EMPTY_CATCH_RE = re.compile(r"catch\s*\([^)]+\)\s*\{\s*}", re.MULTILINE)

    def _check_empty_catch(self, code: str, lines: List[str]) -> None:
        """Flag ``catch`` blocks that silently swallow exceptions."""
        for m in self._EMPTY_CATCH_RE.finditer(code):
            ln = code[: m.start()].count("\n") + 1
            self.warnings.append(JavaError(
                line=ln, column=1,
                error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                message="Empty catch block – exceptions should be handled",
                suggestion="Log or rethrow: e.printStackTrace() or throw new RuntimeException(e)",
            ))

    # ── magic numbers ─────────────────────────────────────────────

    # Only 3+ digit literals are flagged. The old 2-digit threshold combined
    # with a safelist containing 10 but not 20 produced inconsistent results
    # (`int a = 10;` clean, `int b = 20;` warned) that looked like a bug.
    _MAGIC_RE = re.compile(r"(?<![=\d\w])\b(\d{3,})\b(?![Ll])")
    _SAFE_NUMBERS: Set[str] = {"100", "1000", "1024", "255", "360", "365"}

    def _check_magic_numbers(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        in_ml = False
        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_c, in_ml = is_comment_line(stripped, in_ml)
            if is_c or self._is_comment(i, cmap):
                continue
            if stripped.startswith("import") or "final" in raw or ".length" in raw:
                continue
            for m in self._MAGIC_RE.finditer(raw):
                if m.group(1) not in self._SAFE_NUMBERS:
                    self.warnings.append(JavaError(
                        line=i, column=m.start() + 1,
                        error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                        message=f"Magic number '{m.group(1)}' – consider a named constant",
                        suggestion=f"Extract: private static final int SOME_NAME = {m.group(1)};",
                    ))

    # ── unused variables ──────────────────────────────────────────

    _VAR_DECL_RE = re.compile(
        r"(int|long|double|float|boolean|char|byte|short|String|\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]"
    )
    _SKIP_VARS: Set[str] = {"i", "j", "k", "e", "ex", "args", "_"}

    def _check_unused_variables(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        declared: Dict[str, int] = {}
        in_ml = False
        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_c, in_ml = is_comment_line(stripped, in_ml)
            if is_c or self._is_comment(i, cmap):
                continue
            for m in self._VAR_DECL_RE.finditer(raw):
                name = m.group(2)
                if name not in self._SKIP_VARS:
                    declared[name] = i

        for name, ln in declared.items():
            if len(re.findall(r"\b" + re.escape(name) + r"\b", code)) <= 1:
                self.warnings.append(JavaError(
                    line=ln, column=1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                    message=f"Unused variable: '{name}'",
                    suggestion="Remove unused variable or use it in your code",
                ))

    # ── naming conventions ────────────────────────────────────────

    def _check_naming_conventions(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        in_ml = False
        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_c, in_ml = is_comment_line(stripped, in_ml)
            if is_c or self._is_comment(i, cmap):
                continue

            # class names → PascalCase
            m = re.search(r"class\s+([a-z]\w*)", raw)
            if m:
                self.warnings.append(JavaError(
                    line=i, column=raw.index(m.group(1)) + 1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                    message=f"Class name '{m.group(1)}' should start with uppercase",
                    suggestion=f"Rename to '{m.group(1).capitalize()}'",
                ))

            # constants → UPPER_SNAKE
            m = re.search(r"(static\s+final|final\s+static)\s+\w+\s+([a-z]\w*)\s*=", raw)
            if m and not m.group(2).isupper():
                self.warnings.append(JavaError(
                    line=i, column=raw.index(m.group(2)) + 1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                    message=f"Constant '{m.group(2)}' should be UPPER_SNAKE_CASE",
                    suggestion=f"Rename to '{m.group(2).upper()}'",
                ))

            # methods → camelCase
            m = re.search(r"(public|private|protected)\s+\w+\s+([A-Z]\w*)\s*\(", raw)
            if m and not re.search(rf"class\s+{m.group(2)}", code):
                self.warnings.append(JavaError(
                    line=i, column=raw.index(m.group(2)) + 1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                    message=f"Method name '{m.group(2)}' should start with lowercase",
                    suggestion=f"Rename to '{m.group(2)[0].lower() + m.group(2)[1:]}'",
                ))

    # ── long methods ──────────────────────────────────────────────

    _METHOD_RE = re.compile(
        r"(public|private|protected)\s+\w+\s+(\w+)\s*\([^)]*\)\s*\{"
    )

    def _check_long_methods(self, code: str, lines: List[str]) -> None:
        for m in self._METHOD_RE.finditer(code):
            name = m.group(2)
            start = code[: m.start()].count("\n") + 1
            depth, pos = 1, m.end()
            while pos < len(code) and depth > 0:
                if code[pos] == "{":
                    depth += 1
                elif code[pos] == "}":
                    depth -= 1
                pos += 1
            length = code[:pos].count("\n") + 1 - start

            if length > 50:
                self.warnings.append(JavaError(
                    line=start, column=1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                    message=f"Method '{name}' is too long ({length} lines)",
                    suggestion="Split into smaller methods (recommended < 30 lines)",
                ))
            elif length > 30:
                self.warnings.append(JavaError(
                    line=start, column=1,
                    error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                    message=f"Method '{name}' is getting long ({length} lines)",
                    suggestion="Consider extracting some logic to helper methods",
                ))

    # ── deep nesting ──────────────────────────────────────────────

    def _check_deep_nesting(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        depth = 0
        max_depth = 0
        deep_lines: List[int] = []
        in_ml = False

        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_c, in_ml = is_comment_line(stripped, in_ml)
            if is_c or self._is_comment(i, cmap) or not stripped:
                continue

            depth += raw.count("{") - raw.count("}")
            if depth > 4 and depth > max_depth:
                max_depth = depth
                deep_lines.append(i)

        for ln in deep_lines[:3]:
            self.warnings.append(JavaError(
                line=ln, column=1,
                error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                message=f"Deep nesting detected (depth: {max_depth})",
                suggestion="Use early returns, extract methods, or flatten logic",
            ))

    # ── empty blocks ──────────────────────────────────────────────

    _EMPTY_BLOCK_RE = re.compile(r"\{\s*}")

    def _check_empty_blocks(
        self, code: str, lines: List[str], cmap: Dict[int, bool],
    ) -> None:
        in_ml = False
        for i, raw in enumerate(lines, 1):
            stripped = raw.strip()
            is_c, in_ml = is_comment_line(stripped, in_ml)
            if is_c or self._is_comment(i, cmap):
                continue
            if self._EMPTY_BLOCK_RE.search(raw):
                if "interface" not in raw and "abstract" not in raw:
                    self.warnings.append(JavaError(
                        line=i, column=1,
                        error_type=ErrorType.WARNING, severity=ErrorSeverity.WARNING,
                        message="Empty code block detected",
                        suggestion="Add implementation or remove empty block",
                    ))


# ──────────────────────────────────────────────────────────────────────
# ErrorChecker – orchestrator with debouncing & threading
# ──────────────────────────────────────────────────────────────────────

class ErrorChecker:
    """Central coordinator for all error-detection layers.

    Responsibilities
    ----------------
    1. **Orchestrate** syntax, runtime, and static-analysis sub-checkers.
    2. **Debounce** via the ``Debouncer`` class so that the expensive
       pipeline fires only after the user pauses typing (default 600 ms).
    3. **Background threading** – ``check_code_async`` dispatches work to a
       daemon thread so the Electron / Monaco UI never blocks.
    4. **Caching** – identical source is never analysed twice.
    5. **Observer pattern** – ``set_callback`` lets the UI register a handler
       that receives ``List[JavaError]`` when a check completes.

    Usage
    -----
    ::

        checker = ErrorChecker()
        checker.set_callback(my_update_function)
        checker.check_code_async(java_code)   # non-blocking
    """

    def __init__(self, debounce_delay: float = 0.6) -> None:
        """Initialise all sub-checkers and the debounce infrastructure.

        Parameters
        ----------
        debounce_delay : float
            Seconds to wait after the last keystroke before analysing
            (default 0.6, i.e. 600 ms).
        """
        self.syntax_checker = JavaSyntaxChecker()
        self.runtime_detector = RuntimeErrorDetector()
        self.static_analyzer = StaticAnalyzer()

        # Observer callback for the UI layer
        self.on_errors_detected: Optional[Callable[[List[JavaError]], None]] = None

        # Debouncer – cancels pending timer on every new keystroke
        self._debouncer = Debouncer(delay=debounce_delay, callback=self._debounced_check)

        # Code + arguments waiting to be checked after debounce fires
        self._pending_code: Optional[str] = None
        self._pending_warnings: bool = True

        # Hash-based cache to skip re-analysis of identical source
        self._last_code_hash: Optional[int] = None
        self._cached_errors: List[JavaError] = []

        # Legacy attributes (kept for backward compat)
        self._last_check_time: float = 0
        self._debounce_delay: float = debounce_delay
        self._pending_timer: Optional[threading.Timer] = None

    # ── Callback registration (Observer pattern) ──────────────────

    def set_callback(self, callback: Callable[[List[JavaError]], None]) -> None:
        """Register a listener that receives error lists after each check."""
        self.on_errors_detected = callback

    # ── Synchronous check (public) ────────────────────────────────

    def check_code(
        self, code: str, include_warnings: bool = True,
        sourcepath: Optional[str] = None,
    ) -> List[JavaError]:
        """Synchronously analyse *code* and return all findings.

        Layers executed:
        1. Syntax errors (``javac`` with optional project *sourcepath* for
           cross-file resolution; javalang parser fallback without a JDK).
        2. Runtime-risk warnings (static heuristics).
        3. Code-smell / static-analysis warnings (if *include_warnings*).
        """
        all_errors: List[JavaError] = []

        # Layer 1 – syntax
        all_errors.extend(self.syntax_checker.check_syntax(code, sourcepath=sourcepath))

        # Layer 2 – runtime risk heuristics
        all_errors.extend(self.runtime_detector.detect_runtime_errors(code))

        # Layer 3 – code smells / static analysis
        if include_warnings:
            all_errors.extend(self.static_analyzer.analyze(code))

        # Sort: errors first, then warnings, then info; within each group by line
        all_errors.sort(key=lambda e: (
            0 if e.severity == ErrorSeverity.ERROR else
            1 if e.severity == ErrorSeverity.WARNING else 2,
            e.line,
        ))
        return all_errors

    # ── Debounced asynchronous check (public) ─────────────────────

    def check_code_async(self, code: str, include_warnings: bool = True) -> None:
        """Schedule a debounced, background-threaded analysis of *code*.

        Each call **resets** the debounce timer. The actual analysis runs
        only after the user stops typing for ``debounce_delay`` seconds.

        **Why background threading?**
        ``javac`` compilation can take 1-3 s. Running it on the main /
        renderer thread would freeze the editor. A daemon thread keeps the
        UI responsive while the analysis completes, then delivers results
        via the registered callback.
        """
        # Fast path – identical code returns cached results immediately
        code_hash = hash(code)
        if code_hash == self._last_code_hash:
            if self.on_errors_detected:
                self.on_errors_detected(self._cached_errors)
            return

        # Store pending arguments and (re)start the debounce timer
        self._pending_code = code
        self._pending_warnings = include_warnings
        self._debouncer.trigger()

    # ── Internal debounce callback ────────────────────────────────

    def _debounced_check(self) -> None:
        """Called by the ``Debouncer`` once the delay elapses.

        Spawns a daemon thread for the actual analysis so the timer thread
        is freed immediately.
        """
        code = self._pending_code
        warnings = self._pending_warnings
        if code is None:
            return

        thread = threading.Thread(
            target=self._run_check_in_background,
            args=(code, warnings),
            daemon=True,
            name="ErrorChecker-bg",
        )
        thread.start()

    def _run_check_in_background(self, code: str, include_warnings: bool) -> None:
        """Worker executed on a background daemon thread."""
        try:
            errors = self.check_code(code, include_warnings)

            # Update cache
            self._last_code_hash = hash(code)
            self._cached_errors = errors

            # Deliver results to the UI via the registered observer
            if self.on_errors_detected:
                self.on_errors_detected(errors)

        except Exception as exc:
            fallback = JavaError(
                line=1, column=1,
                error_type=ErrorType.WARNING, severity=ErrorSeverity.INFO,
                message=f"Error checker exception: {exc}",
            )
            if self.on_errors_detected:
                self.on_errors_detected([fallback])

    # ── Summary helper ────────────────────────────────────────────

    @staticmethod
    def get_error_summary(errors: List[JavaError]) -> Dict[str, int]:
        """Return counts of errors grouped by category."""
        summary: Dict[str, int] = {
            "syntax_errors":    0,
            "runtime_warnings": 0,
            "code_warnings":    0,
            "info":             0,
            "total":            len(errors),
        }
        for e in errors:
            if e.error_type == ErrorType.SYNTAX:
                summary["syntax_errors"] += 1
            elif e.error_type == ErrorType.RUNTIME:
                summary["runtime_warnings"] += 1
            elif e.error_type == ErrorType.WARNING:
                summary["code_warnings"] += 1
            else:
                summary["info"] += 1
        return summary


# ──────────────────────────────────────────────────────────────────────
# Convenience function
# ──────────────────────────────────────────────────────────────────────

def check_java_code(code: str) -> List[JavaError]:
    """One-shot convenience wrapper – create a checker, run it, return errors."""
    return ErrorChecker().check_code(code)


# ──────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_code = """\
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
    print("Testing Java Error Checker …")
    print("=" * 60)

    checker = ErrorChecker()
    errors = checker.check_code(test_code)

    for err in errors:
        print(err)

    print("\n" + "=" * 60)
    print(f"Summary: {checker.get_error_summary(errors)}")
