"""
Refactoring Engine Module — Production-Grade Hybrid Model
==========================================================
Implements a two-layer refactoring architecture:

  Layer 1 — Deterministic (AST-based, safety_score = 1.0):
      Dead Code Elimination, Unused Import Removal,
      Condition Simplification (De Morgan's Laws),
      Guard Clause Introduction, Loop Optimization hints.

  Layer 2 — Heuristic (AI-suggested, safety_score < 1.0):
      Extract Method with VariableScopeAnalyzer,
      Decompose Behavior, Change Structure / Split Class,
      Replace Temp with Query.

Single Source of Truth: ast_parser.py (JavaASTParser).
Behavior Preservation: error_checker.py (ErrorChecker).
"""

import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from difflib import SequenceMatcher
import copy
import javalang

from ast_parser import JavaASTParser, ClassInfo, MethodInfo, FieldInfo, CodeMetrics
from error_checker import ErrorChecker


# ---------------------------------------------------------------------------
#  Data Classes
# ---------------------------------------------------------------------------

@dataclass
class RefactoringAction:
    """Represents a single refactoring action with safety metadata."""
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

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RefactoringResult:
    """Result of a refactoring operation."""
    success: bool
    original_code: str
    refactored_code: str
    actions: List[RefactoringAction]
    metrics_before: CodeMetrics
    metrics_after: CodeMetrics
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def get_summary(self) -> Dict:
        return {
            'success': self.success,
            'total_actions': len(self.actions),
            'actions_by_type': self._count_actions_by_type(),
            'loc_before': self.metrics_before.code_lines,
            'loc_after': self.metrics_after.code_lines,
            'loc_change': self.metrics_after.code_lines - self.metrics_before.code_lines,
            'methods_before': self.metrics_before.total_methods,
            'methods_after': self.metrics_after.total_methods,
            'complexity_before': self.metrics_before.avg_complexity,
            'complexity_after': self.metrics_after.avg_complexity,
            'warnings_count': len(self.warnings),
            'errors_count': len(self.errors),
        }

    def _count_actions_by_type(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for action in self.actions:
            counts[action.action_type] += 1
        return dict(counts)


@dataclass
class ScopeAnalysisResult:
    """Result from VariableScopeAnalyzer for extract-method feasibility."""
    in_params: List[Dict[str, str]]       # [{name, type}] — variables read but not declared in slice
    out_params: List[Dict[str, str]]      # [{name, type}] — variables modified and used after slice
    resolution: str                        # "void" | "single_return" | "data_class"
    return_type: Optional[str] = None      # resolved Java type for single_return
    feasible: bool = True
    reason: str = ""


@dataclass
class ResponsibilityBlock:
    """A cohesive block of code identified during behaviour decomposition."""
    responsibility_type: str
    start_line: int
    end_line: int
    code_lines: List[str]
    variables_used: Set[str]
    variables_modified: Set[str]
    method_calls: List[str]
    suggested_method_name: str
    description: str


@dataclass
class DecompositionResult:
    """Result of behavior decomposition of a single method / class."""
    original_method_name: str
    original_line_count: int
    responsibilities: List[ResponsibilityBlock]
    extracted_methods: List[Dict]
    feature_envy_detected: bool
    duplicate_blocks: List[Dict]
    refactored_code: str
    explanation: List[str]


@dataclass
class NewClassDefinition:
    """Describes a class produced by Change Structure refactoring."""
    name: str
    responsibility: str
    fields: List[str]
    methods: List[str]
    original_class: str
    code: str = ""


@dataclass
class StructuralRefactoringResult:
    """Result of a structural / class-split refactoring."""
    success: bool
    original_code: str
    refactored_code: str
    new_classes: List[NewClassDefinition]
    coupling_before: Dict
    coupling_after: Dict
    cohesion_before: Dict
    cohesion_after: Dict
    explanations: List[str]
    principles_applied: List[str]


# ---------------------------------------------------------------------------
#  Behavior Preservation Protocol
# ---------------------------------------------------------------------------

class BehaviorPreservationProtocol:
    """
    Validates that a proposed refactored code preserves behaviour.
    1. Pre-check: original must parse via javalang (compilable proxy).
    2. Post-check: refactored must also parse; error count must not increase.
    """

    def __init__(self):
        self.error_checker = ErrorChecker()

    def pre_check(self, code: str) -> Tuple[bool, List[str]]:
        """Return (ok, list_of_issues) for the original code."""
        errors = self.error_checker.check_code(code, include_warnings=False)
        issues = [e.message for e in errors]
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
        except Exception:
            issues.append("Original code does not parse (javalang AST build failed)")
        return (len(issues) == 0, issues)

    @staticmethod
    def _strip_strings_and_comments(code: str) -> str:
        """Remove Java string/char literals and comments.

        Used by structural sanity checks (bracket balance, signature scraping)
        so that braces inside `String s = "}";` don't trip the safety net.
        """
        # Block comments first (greedy-safe with DOTALL).
        code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
        # Line comments.
        code = re.sub(r'//[^\n]*', ' ', code)
        # String literals (handles escapes).
        code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)
        # Char literals.
        code = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", code)
        return code

    # Declarations only: require an opening `{` after the parameter list.
    # Matching `;` as a terminator caught statement-level CALLS like
    # `System.out.println(1);` and produced false "dropped method println/1"
    # rollbacks. Abstract/interface methods (ending in `;`) are deliberately
    # not tracked — missing a check is safer than false rollbacks.
    _METHOD_SIG_RE = re.compile(
        r'(?:public|protected|private|static|final|abstract|synchronized|native|default\s+)*\s*'
        r'(?:<[^>]+>\s+)?'                         # generic parameters
        r'(?:[\w\<\>\[\],\s\.]+?\s+)?'              # return type (optional for ctors)
        r'(\w+)\s*\(([^)]*)\)\s*(?:throws[^{;]+)?\s*\{'
    )

    def _scrape_signatures(self, code: str) -> set:
        """Return a set of (name, arity) tuples for concrete method declarations.

        Best-effort: it's a regex, not a full parser. Used to verify that a
        refactor didn't accidentally rename or drop a method — anything that
        shifts the set is rolled back.
        """
        cleaned = self._strip_strings_and_comments(code)
        sigs = set()
        for m in self._METHOD_SIG_RE.finditer(cleaned):
            name = m.group(1)
            # Skip qualified calls: `obj.method(...) {` can't happen for a
            # declaration, and the dot means we matched inside an expression.
            if m.start(1) > 0 and cleaned[m.start(1) - 1] == '.':
                continue
            params = m.group(2).strip()
            if name in ('if', 'while', 'for', 'switch', 'catch', 'return', 'synchronized', 'try', 'do'):
                continue
            arity = 0 if not params else len([p for p in params.split(',') if p.strip()])
            sigs.add((name, arity))
        return sigs

    # Hard ceiling on how much larger a refactor may make the file. A
    # legitimate decompose-behavior pass adds maybe 20-30%, never 50%.
    _MAX_GROWTH_RATIO = 1.5

    def post_check(
        self,
        original: str,
        refactored: str,
        allowed_removals: Optional[Set[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Verify a refactor preserves behavior to the extent we can check it:
          1. Bracket balance (on string-and-comment-stripped source).
          2. javalang re-parse must succeed.
          3. Public/method signature set must not shrink or rename —
             except method names listed in `allowed_removals` (deliberate
             dead-code eliminations declared by the engine).
          4. Static error count must not increase.
          5. Size invariant: refactored file must not exceed 1.5x original.
          6. (Optional, best-effort) javac compile-equivalence: if `javac`
             is on PATH AND the original compiles, the refactored version
             MUST also compile.
        """
        # Size invariant — guards against the engine accidentally inlining
        # something into a runaway expansion.
        orig_len = max(1, len(original))
        if len(refactored) > orig_len * self._MAX_GROWTH_RATIO:
            return (False, [
                f"Refactored output is {len(refactored) / orig_len:.1f}x larger "
                f"than the original (max {self._MAX_GROWTH_RATIO}x). Rolling back."
            ])

        clean = self._strip_strings_and_comments(refactored)

        # 1. Bracket balance — checked on the stripped source so `"}"` is OK.
        if clean.count('{') != clean.count('}'):
            return (False, [f"Bracket imbalance: {clean.count('{')} open vs {clean.count('}')} close braces"])
        if clean.count('(') != clean.count(')'):
            return (False, [f"Parenthesis imbalance: {clean.count('(')} open vs {clean.count(')')} close"])

        # 2. javalang re-parse — the strongest single signal that the output
        # is still syntactically valid Java.
        parser = JavaASTParser()
        parser.load_code(refactored)
        try:
            parser.build_ast()
        except Exception as exc:
            return (False, [f"Refactored code does not parse: {exc}"])

        # 3. Signature preservation — refactoring should never drop a method
        # the original code had, EXCEPT methods the engine deliberately
        # removed (dead-code elimination) which the caller declares via
        # `allowed_removals`. Additions (extracted helpers) are always fine.
        try:
            before_sigs = self._scrape_signatures(original)
            after_sigs = self._scrape_signatures(refactored)
            removed = {
                (n, a) for (n, a) in (before_sigs - after_sigs)
                if n not in (allowed_removals or set())
            }
            if removed:
                examples = ', '.join(f'{n}/{a}' for n, a in list(removed)[:3])
                return (False, [f"Refactor dropped methods that existed in the original: {examples}"])
        except Exception:
            pass  # signature scrape is best-effort; don't block on its own bugs

        # 4. Static error delta.
        errors_before = self.error_checker.check_code(original, include_warnings=False)
        errors_after = self.error_checker.check_code(refactored, include_warnings=False)
        before_msgs = {e.message for e in errors_before}
        new_errors = [e.message for e in errors_after if e.message not in before_msgs]

        if len(errors_after) > len(errors_before):
            new_errors.append(f"Error count increased from {len(errors_before)} to {len(errors_after)}")

        # 5. Best-effort compile-equivalence + compiled-API diff. If the
        # original compiled with javac, the refactored must also compile,
        # AND its compiled member surface (via javap) must not lose any
        # member the original had — a bytecode-level guard that catches
        # semantic drift a source-level regex can miss. Skipped silently
        # when no JDK is installed.
        compile_issue = self._javac_compile_equivalence(
            original, refactored, allowed_removals=allowed_removals,
        )
        if compile_issue:
            new_errors.append(compile_issue)

        return (len(new_errors) == 0, new_errors)

    @staticmethod
    def _javac_compile_equivalence(
        original: str,
        refactored: str,
        allowed_removals: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """Compile both versions; compare compiled member surfaces via javap.

        Returns None on equivalence (or when the check cannot run).
        Returns a rollback reason when the refactor (a) broke compilation
        that previously worked, or (b) dropped a compiled member (method /
        field signature) that isn't in *allowed_removals*.
        """
        import os
        import shutil
        import subprocess
        import tempfile

        javac = shutil.which('javac')
        javap = shutil.which('javap')
        if not javac:
            return None  # Tool not installed — can't run the check.

        _MEMBER_RE = re.compile(r'^\s*(?:public|protected|private|static|final|abstract|synchronized|native|\s)+[\w\<\>\[\], \.]+\s[\w$]+\(.*\);\s*$|^\s*(?:public|protected|private|static|final|volatile|transient|\s)+[\w\<\>\[\], \.]+\s[\w$]+;\s*$')

        def _compile_and_api(source: str, tmp: str) -> Tuple[bool, str, Set[str]]:
            m = re.search(r'\b(?:public\s+)?(?:final\s+)?(?:abstract\s+)?class\s+(\w+)', source)
            cls = m.group(1) if m else 'Snippet'
            path = os.path.join(tmp, f'{cls}.java')
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(source)
                proc = subprocess.run(
                    [javac, '-d', tmp, path],
                    capture_output=True, text=True, timeout=15,
                )
                if proc.returncode != 0:
                    return False, proc.stderr or proc.stdout, set()
                api: Set[str] = set()
                if javap:
                    for fn in os.listdir(tmp):
                        if not fn.endswith('.class'):
                            continue
                        jp = subprocess.run(
                            [javap, '-p', os.path.join(tmp, fn)],
                            capture_output=True, text=True, timeout=10,
                        )
                        for line in (jp.stdout or '').splitlines():
                            if _MEMBER_RE.match(line):
                                api.add(line.strip())
                return True, '', api
            except subprocess.TimeoutExpired:
                return False, 'javac timed out', set()
            except Exception as exc:
                return False, str(exc), set()

        try:
            with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
                orig_ok, _, orig_api = _compile_and_api(original, t1)
                if not orig_ok:
                    return None  # Original already broken — out of scope.
                ref_ok, ref_err, ref_api = _compile_and_api(refactored, t2)
                if not ref_ok:
                    tail = (ref_err or '').strip().splitlines()[-1:] or ['javac error']
                    return f"Refactor broke compilation that worked before: {tail[0][:200]}"
                # API-surface diff: additions (extracted helpers) are fine;
                # removals must be explicitly sanctioned.
                if orig_api and ref_api:
                    removed = orig_api - ref_api
                    allowed = allowed_removals or set()
                    removed = {
                        r for r in removed
                        if not any(f' {name}(' in r or f' {name};' in r for name in allowed)
                    }
                    if removed:
                        example = next(iter(removed))
                        return (f"Compiled API lost {len(removed)} member(s), e.g. "
                                f"'{example[:120]}' — rolling back")
        except Exception:
            return None  # Never let the guard's own failure block a refactor.
        return None

    def safe_apply(
        self,
        original: str,
        refactored: str,
        allowed_removals: Optional[Set[str]] = None,
    ) -> Tuple[str, List[str]]:
        """
        If post-check passes, return refactored code.
        Otherwise, roll back to original and return warnings.
        """
        ok, issues = self.post_check(original, refactored, allowed_removals=allowed_removals)
        if ok:
            return refactored, []
        return original, [f"Rolled back — {msg}" for msg in issues]


# ---------------------------------------------------------------------------
#  Variable Scope Analyzer  (for Extract Method)
# ---------------------------------------------------------------------------

class VariableScopeAnalyzer:
    """
    Analyses a code slice to determine:
      - in_params  : variables READ inside the slice but DECLARED outside
      - out_params : variables MODIFIED inside and USED after the slice
      - resolution : "void" | "single_return" | "data_class"
    """

    # Primitive type keywords for resolution hinting
    _JAVA_TYPES = {
        'int', 'long', 'short', 'byte', 'float', 'double', 'char',
        'boolean', 'String', 'Integer', 'Long', 'Short', 'Byte',
        'Float', 'Double', 'Character', 'Boolean',
    }

    def analyze(
        self,
        full_method_lines: List[str],
        slice_start: int,
        slice_end: int,
        method_info: Optional[MethodInfo] = None,
    ) -> ScopeAnalysisResult:
        """
        Analyse variable scope for lines[slice_start:slice_end+1].
        Line indices are 0-based relative to the method body.
        """
        if slice_start < 0 or slice_end >= len(full_method_lines) or slice_start > slice_end:
            return ScopeAnalysisResult(
                in_params=[], out_params=[], resolution="void",
                feasible=False, reason="Invalid slice range"
            )

        slice_lines = full_method_lines[slice_start:slice_end + 1]
        before_lines = full_method_lines[:slice_start]
        after_lines = full_method_lines[slice_end + 1:]

        # Gather declarations and usages
        declared_before = self._extract_declared_vars(before_lines)
        declared_in_slice = self._extract_declared_vars(slice_lines)
        used_in_slice = self._extract_used_vars(slice_lines)
        modified_in_slice = self._extract_modified_vars(slice_lines)
        used_after = self._extract_used_vars(after_lines)

        # Add method parameters as declared-before
        if method_info:
            for p in method_info.params:
                declared_before[p.get('name', '')] = p.get('type', 'Object')

        # in_params: used in slice but not declared in slice (must come from outside)
        in_params = []
        seen = set()
        for var in used_in_slice:
            if var not in declared_in_slice and var not in seen:
                vtype = declared_before.get(var, 'Object')
                in_params.append({'name': var, 'type': vtype})
                seen.add(var)

        # out_params: modified in slice AND used after slice
        out_params = []
        for var in modified_in_slice:
            if var in used_after:
                vtype = declared_before.get(var, declared_in_slice.get(var, 'Object'))
                out_params.append({'name': var, 'type': vtype})

        # Resolution strategy
        if len(out_params) == 0:
            resolution = "void"
            return_type = "void"
        elif len(out_params) == 1:
            resolution = "single_return"
            return_type = out_params[0]['type']
        else:
            resolution = "data_class"
            return_type = None

        return ScopeAnalysisResult(
            in_params=in_params,
            out_params=out_params,
            resolution=resolution,
            return_type=return_type,
            feasible=(resolution != "data_class"),
            reason="" if resolution != "data_class" else "Multiple out-params require wrapper class",
        )

    # --- helpers (AST-first with regex fallback) ---

    _DECL_PATTERN = re.compile(
        r'\b((?:final\s+)?[A-Z]\w*(?:<[^>]+>)?(?:\[\])*)\s+([a-z_]\w*)\s*[=;,)]'
    )
    _ASSIGN_PATTERN = re.compile(r'\b([a-z_]\w*)\s*(?:\+|-|\*|/|%|&|\||\^)?=')
    _IDENT_PATTERN = re.compile(r'\b([a-z_]\w*)\b')

    _JAVA_KEYWORDS = {
        'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
        'continue', 'return', 'try', 'catch', 'finally', 'throw', 'throws',
        'new', 'this', 'super', 'class', 'interface', 'extends', 'implements',
        'import', 'package', 'public', 'private', 'protected', 'static',
        'final', 'abstract', 'synchronized', 'volatile', 'transient',
        'void', 'null', 'true', 'false', 'instanceof',
        'int', 'long', 'short', 'byte', 'float', 'double', 'char',
        'boolean', 'default', 'enum', 'assert', 'native', 'strictfp',
    }

    def _extract_declared_vars(self, lines: List[str]) -> Dict[str, str]:
        """Return {var_name: type_name} for local declarations."""
        decls: Dict[str, str] = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            for m in self._DECL_PATTERN.finditer(stripped):
                vtype, vname = m.group(1).strip(), m.group(2)
                if vname not in self._JAVA_KEYWORDS:
                    decls[vname] = vtype
        return decls

    def _extract_used_vars(self, lines: List[str]) -> Set[str]:
        used: Set[str] = set()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            for m in self._IDENT_PATTERN.finditer(stripped):
                name = m.group(1)
                if name not in self._JAVA_KEYWORDS:
                    used.add(name)
        return used

    def _extract_modified_vars(self, lines: List[str]) -> Set[str]:
        modified: Set[str] = set()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            for m in self._ASSIGN_PATTERN.finditer(stripped):
                name = m.group(1)
                if name not in self._JAVA_KEYWORDS:
                    modified.add(name)
        return modified


# ---------------------------------------------------------------------------
#  Layer 1 — Deterministic Refactorings  (safety_score = 1.0)
# ---------------------------------------------------------------------------

class DeadCodeEliminator:
    """
    Finds private methods / fields with zero references in the same
    compilation unit and removes them.  AST-only analysis.
    """

    def analyze(self, code: str, parsed: Dict[str, Any]) -> List[Dict]:
        """Return list of dead-code items: {kind, name, class, line}."""
        dead_items: List[Dict] = []
        for cls in parsed.get('classes', []):
            class_name = cls['name']
            all_method_calls = set()
            all_field_refs = set()

            # Collect every identifier reference in the class body
            class_start = cls.get('start_line', 0)
            class_end = cls.get('end_line', len(code.split('\n')))
            class_body = '\n'.join(code.split('\n')[max(0, class_start - 1):class_end])

            for method in cls.get('methods', []):
                for call in method.get('method_calls', []):
                    all_method_calls.add(call)
            # Also scan raw identifiers for field access
            for token in re.findall(r'\b(\w+)\b', class_body):
                all_field_refs.add(token)

            # Detect unreferenced private methods
            for method in cls.get('methods', []):
                mods = method.get('modifiers', [])
                mname = method['name']
                if 'private' in mods and mname not in all_method_calls:
                    # constructors and main are exempt
                    if mname == class_name or mname == 'main':
                        continue
                    dead_items.append({
                        'kind': 'method',
                        'name': mname,
                        'class': class_name,
                        'line': method.get('start_line', 0),
                    })

            # Detect unreferenced private fields
            for fld in cls.get('fields', []):
                fmods = fld.get('modifiers', [])
                fname = fld['name']
                if 'private' in fmods:
                    # Count occurrences in class body (excluding declaration itself)
                    occurrences = len(re.findall(r'\b' + re.escape(fname) + r'\b', class_body))
                    if occurrences <= 1:
                        dead_items.append({
                            'kind': 'field',
                            'name': fname,
                            'class': class_name,
                            'line': fld.get('line', 0),
                        })
        return dead_items

    def eliminate(self, code: str, dead_items: List[Dict]) -> Tuple[str, List[RefactoringAction]]:
        """Remove dead code by CHARACTER SPAN and return (new_code, actions).

        The previous implementation removed whole lines, which destroyed any
        other code sharing a line with the dead member — a one-line class
        `class A { void dead() {} void live() {} }` lost `live()` too.
        Character-span removal excises exactly the declaration text.
        """
        actions: List[RefactoringAction] = []
        spans: List[Tuple[int, int, Dict, str]] = []  # (start, end, item, snippet)

        for item in dead_items:
            name = item['name']
            if item['kind'] == 'field':
                # Declaration: modifiers .. type .. name [= initializer] ;
                pat = re.compile(
                    r'(?:(?:private|protected|public|static|final|transient|volatile)\s+)+'
                    r'[\w\<\>\[\],\.\s]+?\b' + re.escape(name) + r'\b\s*(?:=[^;]*)?;'
                )
                m = pat.search(code)
                if m:
                    spans.append((m.start(), m.end(), item, m.group(0)))
            elif item['kind'] == 'method':
                # Signature start: modifiers .. name ( .. ) .. {
                pat = re.compile(
                    r'(?:(?:private|protected|public|static|final|synchronized)\s+)+'
                    r'[\w\<\>\[\],\.\s]*?\b' + re.escape(name) + r'\s*\([^)]*\)\s*(?:throws[^{]+)?\{'
                )
                m = pat.search(code)
                if not m:
                    continue
                # Brace-match from the opening `{` to find the method's end.
                depth = 0
                end = m.end() - 1
                i = m.end() - 1
                while i < len(code):
                    ch = code[i]
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                    i += 1
                spans.append((m.start(), end, item, code[m.start():end]))

        if not spans:
            return code, []

        # Remove from the end backwards so earlier offsets stay valid.
        # Skip overlapping spans (nested/duplicate matches).
        spans.sort(key=lambda s: -s[0])
        new_code = code
        last_start = len(code) + 1
        for start, end, item, snippet in spans:
            if end > last_start:
                continue  # overlaps a span we already removed
            last_start = start
            new_code = new_code[:start] + new_code[end:]
            actions.append(RefactoringAction(
                action_type='dead_code_removal',
                description=f"Removed unused private {item['kind']} '{item['name']}' in {item['class']}",
                original_code=snippet[:300],
                refactored_code='',
                safety_score=1.0,
                transformation_type="Deterministic",
                class_name=item['class'],
                method_name=item['name'] if item['kind'] == 'method' else None,
                line_start=item.get('line', 0),
                line_end=item.get('line', 0),
            ))

        # Tidy: collapse lines left fully blank by the removal.
        new_code = re.sub(r'\n[ \t]*\n[ \t]*\n', '\n\n', new_code)
        return new_code, actions


class UnusedImportRemover:
    """Removes import statements whose type is never referenced in the code body."""

    def remove(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        actions: List[RefactoringAction] = []
        lines = code.split('\n')
        import_lines: List[Tuple[int, str, str]] = []  # (idx, full_line, simple_name)

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') and stripped.endswith(';'):
                fq = stripped[len('import '):].rstrip(';').strip()
                if fq.startswith('static '):
                    fq = fq[len('static '):]
                simple = fq.rsplit('.', 1)[-1]
                if simple != '*':
                    import_lines.append((i, line, simple))

        # Build body text excluding all import lines
        import_indices = {idx for idx, _, _ in import_lines}
        body = '\n'.join(l for i, l in enumerate(lines) if i not in import_indices)

        lines_to_remove: Set[int] = set()
        for idx, full_line, simple_name in import_lines:
            if not re.search(r'\b' + re.escape(simple_name) + r'\b', body):
                lines_to_remove.add(idx)
                actions.append(RefactoringAction(
                    action_type='unused_import_removal',
                    description=f"Removed unused import: {full_line.strip()}",
                    original_code=full_line.rstrip(),
                    refactored_code='',
                    safety_score=1.0,
                    transformation_type="Deterministic",
                    line_start=idx + 1,
                    line_end=idx + 1,
                ))

        if not lines_to_remove:
            return code, []

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        return '\n'.join(new_lines), actions


class ConditionSimplifier:
    """
    Applies De Morgan's Laws and guard-clause introduction.
    Deterministic, AST-informed.
    """

    # Ordered longest-first so `>=` is matched before `>` and `<=` before `<`.
    # Using a dict (insertion-ordered, but iteration tested substring first) caused
    # `a >= b` → `a <= = b` because the `>` rule fired on the leading `>` of `>=`.
    _NEGATE_OP = [
        ('==', '!='),
        ('!=', '=='),
        ('<=', '>'),
        ('>=', '<'),
        ('<', '>='),
        ('>', '<='),
    ]

    def analyze_conditionals(self, code: str) -> List[Dict]:
        """Return a list of simplification opportunities."""
        opportunities: List[Dict] = []
        lines = code.split('\n')

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect negated compound conditions:  if (!(a && b))  →  if (!a || !b)
            m = re.search(r'if\s*\(\s*!\s*\((.+?)\)\s*\)', stripped)
            if m:
                inner = m.group(1)
                if '&&' in inner or '||' in inner:
                    simplified = self._apply_demorgan(inner)
                    if simplified != inner:
                        opportunities.append({
                            'type': 'demorgan',
                            'line': i + 1,
                            'original': stripped,
                            'simplified': stripped.replace(f'!({inner})', simplified),
                            'recommendation': "Apply De Morgan's Law to simplify negated compound condition",
                        })

            # Detect deeply nested if-else that can use early return (guard clause)
            if stripped.startswith('if') and not stripped.startswith('if ('):
                pass  # only match well-formed ifs
            if re.match(r'^if\s*\(', stripped):
                # Check nesting depth at this line
                depth = self._nesting_depth_at(lines, i)
                if depth >= 3:
                    opportunities.append({
                        'type': 'guard_clause',
                        'line': i + 1,
                        'original': stripped,
                        'recommendation': 'Introduce guard clause to reduce nesting depth',
                    })

        return opportunities

    def simplify(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """Apply all deterministic condition simplifications."""
        actions: List[RefactoringAction] = []
        lines = code.split('\n')
        changed = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.search(r'if\s*\(\s*!\s*\((.+?)\)\s*\)', stripped)
            if m:
                inner = m.group(1)
                if '&&' in inner or '||' in inner:
                    simplified = self._apply_demorgan(inner)
                    if simplified != inner:
                        new_line = line.replace(f'!({inner})', simplified)
                        actions.append(RefactoringAction(
                            action_type='condition_simplification',
                            description=f"Applied De Morgan's Law at line {i+1}",
                            original_code=line.rstrip(),
                            refactored_code=new_line.rstrip(),
                            safety_score=1.0,
                            transformation_type="Deterministic",
                            line_start=i + 1,
                            line_end=i + 1,
                        ))
                        lines[i] = new_line
                        changed = True

        if not changed:
            return code, []
        return '\n'.join(lines), actions

    def reduce_nesting(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """Convert deeply nested if-else to guard clauses where safe."""
        actions: List[RefactoringAction] = []
        lines = code.split('\n')
        result_lines: List[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            indent = line[:len(line) - len(line.lstrip())]

            # Detect: if (cond) { <big block> } else { return / throw }
            # → invert: if (!cond) { return/throw; }  <big block without wrapping>
            if re.match(r'^if\s*\(', stripped):
                depth = self._nesting_depth_at(lines, i)
                if depth >= 3:
                    guard_result = self._try_guard_clause(lines, i, indent)
                    if guard_result:
                        original_snippet = '\n'.join(
                            lines[i:i + guard_result['consumed']]
                        )
                        actions.append(RefactoringAction(
                            action_type='reduce_nesting',
                            description=f"Introduced guard clause at line {i+1} (depth {depth}→{depth-1})",
                            original_code=original_snippet,
                            refactored_code='\n'.join(guard_result['new_lines']),
                            safety_score=1.0,
                            transformation_type="Deterministic",
                            line_start=i + 1,
                            line_end=i + guard_result['consumed'],
                        ))
                        result_lines.extend(guard_result['new_lines'])
                        i += guard_result['consumed']
                        continue

            result_lines.append(line)
            i += 1

        if not actions:
            return code, []
        return '\n'.join(result_lines), actions

    # --- internals ---

    def _apply_demorgan(self, expr: str) -> str:
        """!(A && B) → !A || !B  and  !(A || B) → !A && !B.

        Mixed expressions like `a && b || c` carry implicit precedence that
        De Morgan can't safely flatten in one pass — we bail out and let the
        caller leave the original expression untouched.
        """
        has_and = '&&' in expr
        has_or = '||' in expr
        if has_and and has_or:
            # Mixed precedence — not safe to rewrite without a real parser.
            return expr
        if has_and:
            parts = self._split_top_level(expr, '&&')
            return ' || '.join(self._negate_term(p) for p in parts)
        if has_or:
            parts = self._split_top_level(expr, '||')
            return ' && '.join(self._negate_term(p) for p in parts)
        return expr

    def _split_top_level(self, expr: str, sep: str) -> List[str]:
        """Split `expr` on `sep` only at parenthesis depth 0."""
        out: List[str] = []
        depth = 0
        buf = []
        i = 0
        while i < len(expr):
            ch = expr[i]
            if ch == '(':
                depth += 1
                buf.append(ch)
            elif ch == ')':
                depth -= 1
                buf.append(ch)
            elif depth == 0 and expr[i:i + len(sep)] == sep:
                out.append(''.join(buf).strip())
                buf = []
                i += len(sep)
                continue
            else:
                buf.append(ch)
            i += 1
        if buf:
            out.append(''.join(buf).strip())
        return out

    def _negate_term(self, term: str) -> str:
        """Negate a single boolean term."""
        term = term.strip()
        if term.startswith('!'):
            return term[1:].strip()
        # Try to flip comparison operators. _NEGATE_OP is ordered longest-first,
        # so multi-char ops (>=, <=, ==, !=) win before single-char fallbacks.
        for op, neg in self._NEGATE_OP:
            if op in term:
                return term.replace(op, neg, 1)
        return f'!{term}'

    def _nesting_depth_at(self, lines: List[str], line_idx: int) -> int:
        depth = 0
        for i in range(0, line_idx + 1):
            for ch in lines[i]:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
        return depth

    def _try_guard_clause(self, lines: List[str], start: int, indent: str) -> Optional[Dict]:
        """
        Try to invert an if-else into a guard clause.
        Returns {new_lines, consumed} or None.
        """
        stripped = lines[start].strip()

        # Match: if (condition) {
        m = re.match(r'^if\s*\((.+)\)\s*\{', stripped)
        if not m:
            return None

        condition = m.group(1)

        # Find the matching else block
        brace_count = 0
        if_end = start
        for i in range(start, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
            if brace_count == 0:
                if_end = i
                break

        # Check if next non-empty line is 'else {'
        else_start = if_end + 1
        while else_start < len(lines) and lines[else_start].strip() == '':
            else_start += 1

        if else_start >= len(lines):
            return None

        else_stripped = lines[else_start].strip()
        if not (else_stripped.startswith('else') or else_stripped == '} else {'):
            return None

        # Find else block end
        brace_count = 0
        else_end = else_start
        found = False
        for i in range(else_start, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    brace_count += 1
                    found = True
                elif ch == '}':
                    brace_count -= 1
            if found and brace_count == 0:
                else_end = i
                break

        # Check if else block is a simple return/throw (guard candidate)
        else_body = [l.strip() for l in lines[else_start + 1:else_end] if l.strip()]
        if len(else_body) == 1 and (
            else_body[0].startswith('return') or else_body[0].startswith('throw')
        ):
            # Invert: guard is the else body, then unwrap the if body
            negated_cond = self._negate_condition(condition)
            guard_line = f"{indent}if ({negated_cond}) {{"
            guard_body = f"{indent}    {else_body[0]}"
            guard_close = f"{indent}}}"

            # Unwrap the if body — remove one level of indentation. Detects
            # the inner indent unit from the first non-blank body line instead
            # of assuming 4 spaces (was broken for tab-indented code).
            if_body_lines = lines[start + 1:if_end]
            inner_indent = ''
            for bl in if_body_lines:
                if bl.strip():
                    inner_indent = bl[:len(bl) - len(bl.lstrip())]
                    break
            step = inner_indent[len(indent):] if inner_indent.startswith(indent) else '    '
            if not step:
                step = '    '
            unwrapped = []
            for bl in if_body_lines:
                if bl.startswith(indent + step):
                    unwrapped.append(indent + bl[len(indent) + len(step):])
                else:
                    unwrapped.append(bl)

            new_lines = [guard_line, guard_body, guard_close] + unwrapped
            consumed = else_end - start + 1
            return {'new_lines': new_lines, 'consumed': consumed}

        return None

    def _negate_condition(self, cond: str) -> str:
        """Negate a condition string."""
        cond = cond.strip()
        if cond.startswith('!'):
            inner = cond[1:].strip()
            if inner.startswith('(') and inner.endswith(')'):
                return inner[1:-1]
            return inner
        for op, neg in self._NEGATE_OP:
            if f' {op} ' in cond:
                return cond.replace(f' {op} ', f' {neg} ', 1)
        return f'!({cond})'


class LoopOptimizer:
    """
    Detects loop patterns that can be improved:
      - Nested loops that may benefit from Map-based lookup
      - Simple filter/map patterns suggestible as Java 8+ Streams
    """

    def analyze(self, code: str, parsed: Dict[str, Any]) -> List[Dict]:
        """Return loop-optimization suggestions."""
        suggestions: List[Dict] = []
        lines = code.split('\n')

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect nested for loops (potential O(n²) → O(n) with Map)
            if re.match(r'^for\s*\(', stripped):
                inner_for = self._find_inner_for(lines, i)
                if inner_for is not None:
                    suggestions.append({
                        'type': 'nested_loop',
                        'line': i + 1,
                        'inner_line': inner_for + 1,
                        'recommendation': (
                            'Consider using a HashMap for O(n) lookup instead of '
                            'nested iteration (O(n²))'
                        ),
                        'safety_score': 0.7,
                    })

            # Detect simple for-each + if pattern (stream candidate)
            if re.match(r'^for\s*\(\s*\w+', stripped) and ':' in stripped:
                stream_candidate = self._is_stream_candidate(lines, i)
                if stream_candidate:
                    suggestions.append({
                        'type': 'stream_conversion',
                        'line': i + 1,
                        'recommendation': (
                            'This for-each with filter/map pattern can be '
                            'expressed as a Java 8+ Stream pipeline'
                        ),
                        'safety_score': 0.6,
                        'pattern': stream_candidate,
                    })

        return suggestions

    def _find_inner_for(self, lines: List[str], outer_idx: int) -> Optional[int]:
        """If there is a for-loop directly nested inside, return its index."""
        brace_count = 0
        started = False
        for i in range(outer_idx, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    brace_count += 1
                    started = True
                elif ch == '}':
                    brace_count -= 1
            if started and brace_count == 0:
                break
            if i > outer_idx:
                s = lines[i].strip()
                if re.match(r'^for\s*\(', s):
                    return i
        return None

    def _is_stream_candidate(self, lines: List[str], for_idx: int) -> Optional[str]:
        """Check if the for-each body is a simple filter+add pattern."""
        brace_count = 0
        body_lines: List[str] = []
        started = False
        for i in range(for_idx, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    brace_count += 1
                    started = True
                elif ch == '}':
                    brace_count -= 1
            if started and i > for_idx:
                body_lines.append(lines[i].strip())
            if started and brace_count == 0:
                break

        body_text = ' '.join(body_lines)
        if re.search(r'if\s*\(.*\)\s*\{.*\.add\(', body_text):
            return 'filter_collect'
        return None


# ---------------------------------------------------------------------------
#  Layer 2 — Heuristic Refactorings  (safety_score < 1.0)
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """
    Detects duplicate code blocks using token-stream normalization.

    Replaces the previous lowercase-whitespace hash, which collapsed
    `int total = a + b;` and `int sum = x + y;` differently because the
    identifiers differed. The new tokenizer maps every identifier to `ID`,
    every numeric literal to `N`, every string to `S`, and every char to
    `C` — so structurally identical blocks hash to the same fingerprint
    regardless of names.
    """

    # Java keywords kept verbatim — they carry semantics.
    _KEYWORDS = frozenset({
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
        'char', 'class', 'continue', 'default', 'do', 'double', 'else',
        'enum', 'extends', 'final', 'finally', 'float', 'for', 'if',
        'implements', 'import', 'instanceof', 'int', 'interface', 'long',
        'native', 'new', 'null', 'package', 'private', 'protected', 'public',
        'return', 'short', 'static', 'strictfp', 'super', 'switch',
        'synchronized', 'this', 'throw', 'throws', 'transient', 'true',
        'false', 'try', 'void', 'volatile', 'while', 'yield',
    })

    _RE_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')
    _RE_CHAR = re.compile(r"'(?:[^'\\\n]|\\.)*'")
    _RE_NUMBER = re.compile(r'\b\d[\d_.eE+\-fFlLdD]*\b')
    _RE_IDENT = re.compile(r'\b[A-Za-z_$][A-Za-z0-9_$]*\b')
    _RE_LINE_COMMENT = re.compile(r'//[^\n]*')
    _RE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

    def __init__(self, similarity_threshold: float = 0.85, min_block_lines: int = 4):
        self.similarity_threshold = similarity_threshold
        self.min_block_lines = min_block_lines

    # -------- public API --------

    def find_duplicates(self, code_blocks: Dict[str, List[str]]) -> List[Dict]:
        """
        Find duplicate code blocks across methods.

        Strategy:
          1. Tokenise + normalise each method (identifiers→ID, numbers→N, …).
          2. Hash the token stream for an O(1) exact-match bucket pass.
          3. Fall back to SequenceMatcher only on small candidate sets that
             share at least one token n-gram (cheaper than the old O(n²)).

        Caps removed — handles arbitrary method counts.
        """
        methods = list(code_blocks.items())
        if len(methods) < 2:
            return []

        fingerprints: List[Tuple[str, List[str], str]] = []
        for name, lines in methods:
            tokens = self._tokenize_normalized('\n'.join(lines))
            if len(tokens) < 8:  # too small to be a meaningful duplicate
                continue
            fingerprints.append((name, lines, ' '.join(tokens)))

        duplicates: List[Dict] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        # Exact-fingerprint duplicates first (cheapest, highest confidence).
        by_hash: Dict[str, List[int]] = defaultdict(list)
        for idx, (_, _, fp) in enumerate(fingerprints):
            by_hash[fp].append(idx)
        for idxs in by_hash.values():
            if len(idxs) < 2:
                continue
            for i in range(len(idxs)):
                for j in range(i + 1, len(idxs)):
                    a, b = fingerprints[idxs[i]], fingerprints[idxs[j]]
                    pair = tuple(sorted([a[0], b[0]]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    duplicates.append({
                        'method1': a[0],
                        'method2': b[0],
                        'similarity': 1.0,
                        'lines1': a[1],
                        'lines2': b[1],
                    })

        # Near-duplicate pass — restrict to pairs that share an n-gram so we
        # don't do the full O(n²) similarity matrix.
        ngram_buckets: Dict[str, List[int]] = defaultdict(list)
        N = 5
        for idx, (_, _, fp) in enumerate(fingerprints):
            toks = fp.split(' ')
            for k in range(0, max(0, len(toks) - N + 1)):
                ngram_buckets[' '.join(toks[k:k + N])].append(idx)

        candidate_pairs: Set[Tuple[int, int]] = set()
        for bucket in ngram_buckets.values():
            if len(bucket) < 2:
                continue
            uniq = sorted(set(bucket))
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    candidate_pairs.add((uniq[i], uniq[j]))

        for i, j in candidate_pairs:
            a, b = fingerprints[i], fingerprints[j]
            pair = tuple(sorted([a[0], b[0]]))
            if pair in seen_pairs:
                continue
            ratio = SequenceMatcher(None, a[2], b[2]).ratio()
            if ratio >= self.similarity_threshold:
                seen_pairs.add(pair)
                duplicates.append({
                    'method1': a[0],
                    'method2': b[0],
                    'similarity': round(ratio, 3),
                    'lines1': a[1],
                    'lines2': b[1],
                })

        # Reordered-clone pass: same statements, different order. Sequence
        # matching misses these by construction; a statement-multiset
        # comparison is order-insensitive.
        for i in range(len(fingerprints)):
            for j in range(i + 1, len(fingerprints)):
                a, b = fingerprints[i], fingerprints[j]
                pair = tuple(sorted([a[0], b[0]]))
                if pair in seen_pairs:
                    continue
                ms_a = self._statement_multiset(a[2].split(' '))
                ms_b = self._statement_multiset(b[2].split(' '))
                if len(ms_a) >= 3 and self._multiset_similarity(ms_a, ms_b) >= 0.9:
                    seen_pairs.add(pair)
                    duplicates.append({
                        'method1': a[0],
                        'method2': b[0],
                        'similarity': 0.9,
                        'kind': 'reordered',
                        'lines1': a[1],
                        'lines2': b[1],
                    })

        # Highest similarity first.
        duplicates.sort(key=lambda d: -d['similarity'])
        return duplicates

    def find_repeated_patterns(self, code: str, min_length: int = 4) -> List[Dict]:
        """Find repeated structural patterns within a single method/file.

        Slides a `min_length`-line window over the normalised line stream
        and groups by fingerprint. Catches the "same logic copy-pasted three
        times" smell even when the variable names were renamed.
        """
        raw_lines = code.split('\n')
        cleaned = []  # (original_line_idx, normalized_tokens_for_line)
        for idx, ln in enumerate(raw_lines):
            stripped = ln.strip()
            if not stripped or stripped.startswith('//'):
                continue
            toks = self._tokenize_normalized(stripped)
            if not toks:
                continue
            cleaned.append((idx, ' '.join(toks)))

        if len(cleaned) < min_length * 2:
            return []

        buckets: Dict[str, List[int]] = defaultdict(list)
        for start in range(0, len(cleaned) - min_length + 1):
            fp = ' | '.join(c[1] for c in cleaned[start:start + min_length])
            buckets[fp].append(start)

        patterns: List[Dict] = []
        for fp, positions in buckets.items():
            if len(positions) < 2:
                continue
            # Non-overlapping occurrences only.
            non_overlapping = [positions[0]]
            for p in positions[1:]:
                if p - non_overlapping[-1] >= min_length:
                    non_overlapping.append(p)
            if len(non_overlapping) < 2:
                continue
            first = non_overlapping[0]
            sample_lines = [raw_lines[cleaned[first + k][0]] for k in range(min_length)]
            patterns.append({
                'occurrences': len(non_overlapping),
                'positions': [cleaned[p][0] + 1 for p in non_overlapping],  # 1-indexed
                'sample': '\n'.join(sample_lines),
            })

        patterns.sort(key=lambda p: (-p['occurrences'], -len(p['sample'])))
        return patterns

    # -------- internals --------

    def _tokenize_normalized(self, code: str) -> List[str]:
        """Produce a structure-preserving token stream from Java source.

        Identifiers → 'ID' (keywords kept), numbers → 'N', strings → 'S',
        chars → 'C'. Operators and punctuation kept verbatim. Whitespace and
        comments stripped.
        """
        code = self._RE_BLOCK_COMMENT.sub(' ', code)
        code = self._RE_LINE_COMMENT.sub(' ', code)
        code = self._RE_STRING.sub(' S ', code)
        code = self._RE_CHAR.sub(' C ', code)
        code = self._RE_NUMBER.sub(' N ', code)

        # Tokenise: identifiers/keywords + any non-space single char.
        tokens: List[str] = []
        i = 0
        while i < len(code):
            ch = code[i]
            if ch.isspace():
                i += 1
                continue
            m = self._RE_IDENT.match(code, i)
            if m:
                ident = m.group(0)
                if ident in ('for', 'while', 'do'):
                    # Loop-construct normalisation: `for` and `while` clones
                    # with identical bodies now hash the same.
                    tokens.append('LOOP')
                elif ident in self._KEYWORDS:
                    tokens.append(ident)
                elif ident in ('S', 'N', 'C', 'ID'):
                    tokens.append(ident)  # already-normalised marker
                else:
                    tokens.append('ID')
                i = m.end()
                continue
            tokens.append(ch)
            i += 1
        return tokens

    def _statement_multiset(self, tokens: List[str]) -> Dict[str, int]:
        """Split a token stream into `;`/`{`/`}`-terminated statements and
        return their multiset. Order-insensitive: two methods containing the
        same statements in different order produce identical multisets."""
        stmts: Dict[str, int] = defaultdict(int)
        buf: List[str] = []
        for t in tokens:
            buf.append(t)
            if t in (';', '{', '}'):
                s = ' '.join(buf).strip()
                if len(buf) > 1:
                    stmts[s] += 1
                buf = []
        if buf:
            stmts[' '.join(buf)] += 1
        return dict(stmts)

    @staticmethod
    def _multiset_similarity(a: Dict[str, int], b: Dict[str, int]) -> float:
        if not a or not b:
            return 0.0
        inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b))
        union = sum(max(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b))
        return inter / union if union else 0.0


class MethodExtractor:
    """
    Extracts long code blocks into new methods.
    Uses VariableScopeAnalyzer for parameter resolution.
    """

    def __init__(self, max_method_lines: int = 20, max_complexity: int = 10):
        self.max_method_lines = max_method_lines
        self.max_complexity = max_complexity
        self.scope_analyzer = VariableScopeAnalyzer()

    def identify_extraction_candidates(self, code: str, method_info: MethodInfo) -> List[Dict]:
        """Identify code blocks within a method that should be extracted."""
        candidates: List[Dict] = []

        if method_info.body_lines <= self.max_method_lines:
            return candidates

        lines = code.split('\n')
        method_lines = lines[method_info.start_line - 1:method_info.end_line]

        # Strategy 1: Comment-delimited blocks
        comment_blocks = self._find_comment_blocks(method_lines, method_info)
        candidates.extend(comment_blocks)

        # Strategy 2: Loop bodies that are too long
        loop_blocks = self._find_long_loops(method_lines, method_info)
        candidates.extend(loop_blocks)

        # Strategy 3: Consecutive statements forming a logical unit
        if not candidates:
            chunk_blocks = self._find_statement_chunks(method_lines, method_info)
            candidates.extend(chunk_blocks)

        return candidates

    def extract_method(
        self, code: str, candidate: Dict, class_name: str
    ) -> Tuple[str, str]:
        """
        Extract a candidate block into a new method.
        Returns (new_method_code, call_replacement).
        """
        slice_lines = candidate.get('lines', [])
        method_name = candidate.get('suggested_name', 'extractedMethod')
        scope: ScopeAnalysisResult = candidate.get('scope_analysis')

        if scope is None:
            # Fallback: no params, void
            params_str = ''
            return_type = 'void'
            return_stmt = ''
        else:
            params_str = ', '.join(
                f"{p['type']} {p['name']}" for p in scope.in_params
            )
            if scope.resolution == 'void':
                return_type = 'void'
                return_stmt = ''
            elif scope.resolution == 'single_return':
                return_type = scope.return_type or 'Object'
                out_name = scope.out_params[0]['name'] if scope.out_params else 'result'
                return_stmt = f'\n        return {out_name};'
            else:
                return_type = 'void'
                return_stmt = ''

        body = '\n'.join(f'        {l.strip()}' for l in slice_lines)
        new_method = (
            f'\n    private {return_type} {method_name}({params_str}) {{\n'
            f'{body}{return_stmt}\n'
            f'    }}\n'
        )

        # Build call site
        args_str = ', '.join(p['name'] for p in (scope.in_params if scope else []))
        if return_type == 'void':
            call = f'{method_name}({args_str});'
        else:
            out_name = scope.out_params[0]['name'] if scope and scope.out_params else 'result'
            call = f'{return_type} {out_name} = {method_name}({args_str});'

        return new_method, call

    # --- internal helpers ---

    def _find_comment_blocks(self, method_lines: List[str], method_info: MethodInfo) -> List[Dict]:
        """Find blocks preceded by a // comment describing a step."""
        blocks: List[Dict] = []
        i = 0
        while i < len(method_lines):
            stripped = method_lines[i].strip()
            if stripped.startswith('//') and not stripped.startswith('///'):
                comment_text = stripped.lstrip('/ ').strip()
                block_start = i + 1
                if block_start < len(method_lines):
                    block_end = self._find_block_end(method_lines, block_start)
                    if block_end - block_start >= 3:
                        scope = self.scope_analyzer.analyze(
                            method_lines, block_start, block_end, method_info
                        )
                        name = self._comment_to_method_name(comment_text)
                        blocks.append({
                            'suggested_name': name,
                            'lines': method_lines[block_start:block_end + 1],
                            'start': block_start,
                            'end': block_end,
                            'scope_analysis': scope,
                            'reason': f'Comment-delimited block: "{comment_text}"',
                        })
                        i = block_end + 1
                        continue
            i += 1
        return blocks

    def _find_long_loops(self, method_lines: List[str], method_info: MethodInfo) -> List[Dict]:
        blocks: List[Dict] = []
        for i, line in enumerate(method_lines):
            stripped = line.strip()
            if re.match(r'^(for|while)\s*\(', stripped):
                end = self._find_brace_end(method_lines, i)
                if end - i >= 8:
                    scope = self.scope_analyzer.analyze(
                        method_lines, i, end, method_info
                    )
                    blocks.append({
                        'suggested_name': f'process{self._loop_var_name(stripped)}',
                        'lines': method_lines[i:end + 1],
                        'start': i,
                        'end': end,
                        'scope_analysis': scope,
                        'reason': 'Long loop body suitable for extraction',
                    })
        return blocks

    def _find_statement_chunks(self, method_lines: List[str], method_info: MethodInfo) -> List[Dict]:
        """Disabled — blind N-line slicing breaks brace pairs.

        The old behavior split a method body into fixed-size chunks regardless
        of `{`/`}` boundaries, then handed those chunks to Extract Method,
        which then emitted syntactically broken Java. We now refuse to
        suggest chunk-based extractions; comment-delimited and loop-body
        extractions remain (they respect brace boundaries by construction).
        """
        return []

    def _find_block_end(self, lines: List[str], start: int) -> int:
        """Find where a logical block ends (next comment or significant break)."""
        for i in range(start, len(lines)):
            stripped = lines[i].strip()
            if i > start and stripped.startswith('//') and not stripped.startswith('///'):
                return i - 1
            if stripped == '' and i > start + 2:
                next_non_empty = None
                for j in range(i + 1, len(lines)):
                    if lines[j].strip():
                        next_non_empty = j
                        break
                if next_non_empty and lines[next_non_empty].strip().startswith('//'):
                    return i - 1
        return len(lines) - 1

    def _find_brace_end(self, lines: List[str], start: int) -> int:
        depth = 0
        started = False
        for i in range(start, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    depth += 1
                    started = True
                elif ch == '}':
                    depth -= 1
            if started and depth == 0:
                return i
        return len(lines) - 1

    def _comment_to_method_name(self, comment: str) -> str:
        words = re.findall(r'[a-zA-Z]+', comment)
        if not words:
            return 'extractedMethod'
        name = words[0].lower() + ''.join(w.capitalize() for w in words[1:4])
        return name

    def _suggest_method_name(self, prefix: str, code_lines: List[str]) -> str:
        """Suggest a method name based on code content patterns."""
        code = '\n'.join(code_lines).lower()
        if 'validate' in code or 'check' in code:
            return f'{prefix}Validation'
        elif 'calculate' in code or 'compute' in code:
            return f'{prefix}Calculation'
        elif 'process' in code:
            return f'{prefix}Processing'
        elif 'initialize' in code or 'init' in code:
            return f'{prefix}Initialization'
        elif 'update' in code:
            return f'{prefix}Update'
        elif 'get' in code or 'fetch' in code:
            return f'{prefix}Retrieval'
        elif 'set' in code:
            return f'{prefix}Assignment'
        elif 'format' in code or 'render' in code:
            return f'{prefix}Formatting'
        elif 'log' in code or 'print' in code:
            return f'{prefix}Logging'
        elif 'save' in code or 'persist' in code:
            return f'{prefix}Persistence'
        else:
            return f'{prefix}Operation'

    def _loop_var_name(self, loop_line: str) -> str:
        m = re.search(r'(\w+)\s*[=:]', loop_line)
        if m:
            return m.group(1).capitalize()
        return 'Items'


class ConditionalReducer:
    """Reduces conditional complexity using polymorphism detection and simplification."""

    def __init__(self, max_nesting: int = 3):
        self.max_nesting = max_nesting

    def analyze_conditionals(self, code: str) -> List[Dict]:
        """Analyse all conditional structures and suggest improvements."""
        opportunities: List[Dict] = []
        lines = code.split('\n')

        # Detect long if-else chains (→ Strategy / Polymorphism)
        chain_length = 0
        chain_start = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^(if|else\s+if)\s*\(', stripped):
                if chain_start == -1:
                    chain_start = i
                chain_length += 1
            elif stripped.startswith('else') and chain_length > 0:
                chain_length += 1
            else:
                if chain_length >= 4:
                    opportunities.append({
                        'type': 'long_if_else_chain',
                        'line': chain_start + 1,
                        'chain_length': chain_length,
                        'recommendation': (
                            f'Replace {chain_length}-branch if-else chain with '
                            'Strategy pattern or Map-based dispatch'
                        ),
                    })
                chain_length = 0
                chain_start = -1

        # Detect switch with no default
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^switch\s*\(', stripped):
                switch_end = self._find_brace_end(lines, i)
                switch_body = '\n'.join(lines[i:switch_end + 1])
                if 'default:' not in switch_body:
                    opportunities.append({
                        'type': 'switch_no_default',
                        'line': i + 1,
                        'recommendation': 'Switch statement missing default case',
                    })

        return opportunities

    def reduce_nesting(self, code: str) -> str:
        """Apply nesting reduction and return modified code."""
        simplifier = ConditionSimplifier()
        result, _ = simplifier.reduce_nesting(code)
        return result

    def suggest_polymorphism(self, code: str) -> Optional[Dict]:
        """Suggest polymorphism refactoring for type-checking conditionals."""
        lines = code.split('\n')
        instanceof_count = sum(1 for l in lines if 'instanceof' in l)
        if instanceof_count >= 3:
            return {
                'suggestion': 'Replace instanceof checks with polymorphic dispatch',
                'instanceof_count': instanceof_count,
                'pattern': 'Replace Conditional with Polymorphism',
            }
        return None

    def _find_brace_end(self, lines: List[str], start: int) -> int:
        depth = 0
        started = False
        for i in range(start, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    depth += 1
                    started = True
                elif ch == '}':
                    depth -= 1
            if started and depth == 0:
                return i
        return len(lines) - 1


class ClassSplitter:
    """Analyses class cohesion to suggest responsibility-based splits."""

    def __init__(self, max_lines: int = 200, max_methods: int = 15):
        self.max_lines = max_lines
        self.max_methods = max_methods

    def analyze_class(self, class_info: ClassInfo) -> Dict:
        """Return analysis with needs_split, reasons, suggested_splits."""
        reasons: List[str] = []
        suggested_splits: List[Dict] = []

        if class_info.total_lines > self.max_lines:
            reasons.append(f'Class has {class_info.total_lines} lines (max {self.max_lines})')
        if len(class_info.methods) > self.max_methods:
            reasons.append(f'Class has {len(class_info.methods)} methods (max {self.max_methods})')

        # Group methods by field access to find responsibility clusters
        clusters = self._cluster_by_field_access(class_info)
        if len(clusters) >= 2:
            for idx, cluster in enumerate(clusters):
                suggested_splits.append({
                    'name': f'{class_info.name}Part{idx + 1}',
                    'methods': [m.name for m in cluster['methods']],
                    'fields': list(cluster['fields']),
                    'reason': f"Cohesive group around fields: {', '.join(list(cluster['fields'])[:3])}",
                })

        return {
            'needs_split': len(reasons) > 0 and len(suggested_splits) >= 2,
            'reasons': reasons,
            'suggested_splits': suggested_splits,
        }

    def generate_split_classes(
        self, class_info: ClassInfo, splits: List[Dict],
        source_code: str = '',
    ) -> Dict[str, str]:
        """Generate PREVIEW code for suggested split classes.

        Real field declarations (correct types) and real method bodies are
        extracted from the source by the parser's brace-matched line ranges —
        no `// TODO` stubs. The preview is advisory output only: the engine
        NEVER applies it to the user's file (moving bodies across class
        boundaries safely needs semantic analysis), but the user gets
        compilable scaffolding to apply by hand.
        """
        result: Dict[str, str] = {}
        src_lines = source_code.split('\n') if source_code else []

        method_src: Dict[str, str] = {}
        for m in class_info.methods:
            if src_lines and m.start_line > 0 and m.end_line >= m.start_line:
                snippet = '\n'.join(src_lines[m.start_line - 1:m.end_line])
                method_src[m.name] = snippet

        for split in splits:
            out = [f'// PREVIEW — suggested extraction from {class_info.name}',
                   f'public class {split["name"]} {{', '']
            for f_name in split.get('fields', []):
                for fld in class_info.fields:
                    if fld.name == f_name:
                        mods = ' '.join(mod for mod in fld.modifiers) or 'private'
                        out.append(f'    {mods} {fld.type_name} {fld.name};')
            out.append('')
            for m_name in split.get('methods', []):
                body = method_src.get(m_name)
                if body:
                    out.append(body if body.startswith('    ') else
                               '\n'.join('    ' + l for l in body.split('\n')))
                    out.append('')
                else:
                    out.append(f'    // {m_name}: source range unavailable — copy manually')
            out.append('}')
            result[split['name']] = '\n'.join(out)
        return result

    def _cluster_by_field_access(self, class_info: ClassInfo) -> List[Dict]:
        """Cluster methods by which fields they reference."""
        field_names = {f.name for f in class_info.fields}
        method_fields: Dict[str, Set[str]] = {}

        for method in class_info.methods:
            accessed = set()
            for var in method.local_variables:
                if var in field_names:
                    accessed.add(var)
            for call in method.method_calls:
                for fn in field_names:
                    if fn in call:
                        accessed.add(fn)
            method_fields[method.name] = accessed

        # Simple greedy clustering
        used_methods: Set[str] = set()
        clusters: List[Dict] = []

        for method in class_info.methods:
            if method.name in used_methods:
                continue
            cluster_fields = method_fields.get(method.name, set())
            cluster_methods = [method]
            used_methods.add(method.name)

            for other in class_info.methods:
                if other.name in used_methods:
                    continue
                other_fields = method_fields.get(other.name, set())
                if cluster_fields & other_fields:
                    cluster_methods.append(other)
                    cluster_fields |= other_fields
                    used_methods.add(other.name)

            if cluster_methods:
                clusters.append({
                    'methods': cluster_methods,
                    'fields': cluster_fields,
                })

        return clusters


class BehaviorDecomposer:
    """
    Kent Beck-inspired behavior decomposition.
    Identifies responsibility blocks within large methods or classes
    and suggests extraction.

    Targets these Code Smells:
    - Long Method (>20 lines)
    - Large Class (>200 lines or >15 methods)
    - Feature Envy (method uses another class's data more than its own)
    - Duplicate Code (same logic appears multiple times)

    Kent Beck's Principles Applied:
    - Single Responsibility Principle (SRP)
    - Separation of Concerns
    - High Cohesion / Low Coupling
    - Extract Method pattern
    - Behavior Preservation
    """

    # Responsibility type patterns for line classification
    RESPONSIBILITY_PATTERNS = {
        'validation': [
            r'(validate|check|verify|assert|ensure|require)',
            r'(if\s*\(\s*\w+\s*==\s*null)',
            r'(isEmpty|isBlank|isNull|isValid)',
            r'(throw\s+new\s+\w*(Exception|Error))',
        ],
        'calculation': [
            r'(calculate|compute|sum|total|average|count)',
            r'(\+\+|--|\+=|-=|\*=|/=)',
            r'(Math\.\w+)',
            r'(\w+\s*=\s*\w+\s*[\+\-\*\/\%]\s*\w+)',
        ],
        'data_access': [
            r'(get\w+|fetch\w+|load\w+|find\w+|query)',
            r'(save|store|persist|update|delete|insert)',
            r'(Repository|DAO|Database|Connection)',
            r'(SELECT|INSERT|UPDATE|DELETE)',
        ],
        'transformation': [
            r'(convert|transform|map|parse|format)',
            r'(toString|toInt|toDouble|toList)',
            r'(new\s+\w+\()',
        ],
        'output': [
            r'(print|log|write|output|display|render)',
            r'(System\.out|Logger|log\.)',
            r'(return\s+)',
        ],
        'error_handling': [
            r'(try\s*\{)',
            r'(catch\s*\()',
            r'(finally\s*\{)',
            r'(throw\s+)',
        ],
        'iteration': [
            r'(for\s*\()',
            r'(while\s*\()',
            r'(forEach|stream\(\)\.)',
            r'(\.iterator\(\))',
        ],
        'decision': [
            r'(if\s*\()',
            r'(switch\s*\()',
            r'(case\s+\w+:)',
            r'(\?\s*:)',
        ],
    }

    # Method name prefixes for each responsibility type
    METHOD_NAME_PREFIXES = {
        'validation': 'validate',
        'calculation': 'calculate',
        'data_access': 'fetch',
        'transformation': 'convert',
        'output': 'format',
        'error_handling': 'handle',
        'iteration': 'process',
        'decision': 'determine',
        'general': 'perform',
    }

    def __init__(
        self,
        max_method_lines: int = 20,
        max_class_lines: int = 200,
        max_methods_per_class: int = 15,
        min_extraction_lines: int = 5,
    ):
        self.max_method_lines = max_method_lines
        self.max_class_lines = max_class_lines
        self.max_methods_per_class = max_methods_per_class
        self.min_extraction_lines = min_extraction_lines
        self.scope_analyzer = VariableScopeAnalyzer()
        self.duplicate_detector = DuplicateDetector()

    def analyze_for_decomposition(self, code: str) -> Dict[str, Any]:
        """Analyze code and return decomposition opportunities."""
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
        except Exception:
            return {'needs_decomposition': False, 'reasons': [], 'method_details': [], 'class_details': [], 'long_methods': []}

        analysis: Dict[str, Any] = {
            'needs_decomposition': False,
            'reasons': [],
            'method_details': [],
            'class_details': [],
            'long_methods': [],
            'large_classes': [],
            'feature_envy': [],
            'duplicate_code': [],
            'decomposition_suggestions': [],
            'total_responsibilities_found': 0,
        }

        for cls in extracted.get('classes', []):
            cls_reasons: List[str] = []
            if cls.get('total_lines', 0) > self.max_class_lines:
                cls_reasons.append(f"Large Class: '{cls['name']}' has {cls['total_lines']} lines (max: {self.max_class_lines})")
                analysis['large_classes'].append({
                    'name': cls['name'],
                    'lines': cls['total_lines'],
                    'methods': len(cls.get('methods', [])),
                })
            if len(cls.get('methods', [])) > self.max_methods_per_class:
                cls_reasons.append(f"Too Many Methods: '{cls['name']}' has {len(cls['methods'])} methods (max: {self.max_methods_per_class})")

            for method in cls.get('methods', []):
                if method.get('body_lines', 0) > self.max_method_lines:
                    cls_reasons.append(
                        f"Long Method: '{method['name']}' has {method['body_lines']} lines (max: {self.max_method_lines})"
                    )
                    method_detail = {
                        'class': cls['name'],
                        'method': method['name'],
                        'lines': method['body_lines'],
                        'complexity': method.get('complexity', 0),
                    }
                    analysis['method_details'].append(method_detail)
                    analysis['long_methods'].append(method_detail)

                    # Generate decomposition suggestion with responsibility analysis
                    responsibilities = self._identify_responsibilities_from_body(
                        method.get('body', ''), method['name']
                    )
                    analysis['decomposition_suggestions'].append({
                        'method': method['name'],
                        'current_lines': method['body_lines'],
                        'responsibilities': responsibilities,
                        'suggested_extractions': self._suggest_extractions(
                            method['name'], responsibilities
                        ),
                    })
                    analysis['total_responsibilities_found'] += len(responsibilities)

            if cls_reasons:
                analysis['needs_decomposition'] = True
                analysis['reasons'].extend(cls_reasons)
                analysis['class_details'].append({
                    'name': cls['name'],
                    'issues': cls_reasons,
                })

        # Detect Feature Envy
        feature_envy = self._detect_feature_envy_detailed(code, extracted)
        if feature_envy:
            analysis['needs_decomposition'] = True
            analysis['feature_envy'] = feature_envy
            analysis['reasons'].append(
                f"Feature Envy: {len(feature_envy)} method(s) use other class data excessively"
            )

        # Detect Duplicate Code (Rule of Three)
        duplicates = self._detect_duplicate_code(code)
        if duplicates:
            analysis['needs_decomposition'] = True
            analysis['duplicate_code'] = duplicates
            analysis['reasons'].append(
                f"Duplicate Code: {len(duplicates)} repeated pattern(s) found"
            )

        return analysis

    def decompose(self, code: str, method_name: str = None) -> DecompositionResult:
        """
        Decompose a method (or the first long method found) into
        smaller responsibility blocks.
        """
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
        except Exception:
            return DecompositionResult(
                original_method_name='',
                original_line_count=0,
                responsibilities=[],
                extracted_methods=[],
                feature_envy_detected=False,
                duplicate_blocks=[],
                refactored_code=code,
                explanation=['Could not parse code for decomposition'],
            )

        target_method = None
        target_class = None

        for cls in extracted.get('classes', []):
            for method in cls.get('methods', []):
                if method_name and method['name'] != method_name:
                    continue
                if method.get('body_lines', 0) > self.max_method_lines:
                    target_method = method
                    target_class = cls
                    break
            if target_method:
                break

        if not target_method:
            return DecompositionResult(
                original_method_name=method_name or '<none>',
                original_line_count=0,
                responsibilities=[],
                extracted_methods=[],
                feature_envy_detected=False,
                duplicate_blocks=[],
                refactored_code=code,
                explanation=['No method found requiring decomposition'],
            )

        lines = code.split('\n')
        m_start = target_method.get('start_line', 1) - 1
        m_end = target_method.get('end_line', len(lines))
        method_lines = lines[m_start:m_end]

        # Identify responsibilities
        responsibilities = self._identify_responsibilities(method_lines, target_method)

        # Build extracted methods
        extracted_methods: List[Dict] = []
        explanations: List[str] = []
        refactored_lines = list(lines)

        extractor = MethodExtractor(self.max_method_lines)
        new_methods_code: List[str] = []

        call_replacements: List[Tuple[str, str]] = []

        for resp in responsibilities:
            if len(resp.code_lines) >= self.min_extraction_lines:
                # Skip blocks whose braces don't balance internally — replacing
                # them with a call would break the surrounding structure.
                block_text = '\n'.join(resp.code_lines)
                if block_text.count('{') != block_text.count('}'):
                    continue

                method_info_obj = self._dict_to_method_info(target_method)
                scope = self.scope_analyzer.analyze(
                    method_lines,
                    resp.start_line - m_start - 1,
                    resp.end_line - m_start - 1,
                    method_info_obj,
                )
                # Blocks needing a wrapper class for multiple out-params are
                # infeasible for clean extraction.
                if not scope.feasible:
                    continue

                candidate = {
                    'suggested_name': resp.suggested_method_name,
                    'lines': resp.code_lines,
                    'scope_analysis': scope,
                }
                new_method, call = extractor.extract_method(
                    code, candidate, target_class['name']
                )
                new_methods_code.append(new_method)

                # Record the call-site replacement. Without this, the old
                # implementation left the original block in place and merely
                # ADDED the new method — duplicating the logic instead of
                # moving it.
                indent = ''
                for l in resp.code_lines:
                    if l.strip():
                        indent = l[:len(l) - len(l.lstrip())]
                        break
                call_replacements.append((block_text, f'{indent}{call}'))

                extracted_methods.append({
                    'name': resp.suggested_method_name,
                    'responsibility': resp.responsibility_type,
                    'lines': len(resp.code_lines),
                    'params': scope.in_params,
                    'return_type': scope.return_type or 'void',
                })
                explanations.append(
                    f"Extracted '{resp.suggested_method_name}' — {resp.description}"
                )

        # Check for duplicates
        code_blocks = parser.get_code_blocks()
        duplicate_blocks = self.duplicate_detector.find_duplicates(code_blocks)

        # Check feature envy
        feature_envy = self._detect_feature_envy(target_method)

        # Build refactored code: replace extracted blocks with calls FIRST,
        # then append the new methods before the class's closing brace.
        # Any structural damage is caught downstream by
        # BehaviorPreservationProtocol.post_check and rolled back.
        refactored_code = code
        if new_methods_code:
            for original_block, call_line in call_replacements:
                if original_block in refactored_code:
                    refactored_code = refactored_code.replace(original_block, call_line, 1)

            ref_lines = refactored_code.split('\n')
            # Insert before the last closing brace (end of the class).
            insert_point = len(ref_lines) - 1
            for idx in range(len(ref_lines) - 1, -1, -1):
                if ref_lines[idx].strip() == '}':
                    insert_point = idx
                    break
            for nm in new_methods_code:
                ref_lines.insert(insert_point, nm)
                insert_point += 1
            refactored_code = '\n'.join(ref_lines)

        return DecompositionResult(
            original_method_name=target_method['name'],
            original_line_count=target_method.get('body_lines', 0),
            responsibilities=responsibilities,
            extracted_methods=extracted_methods,
            feature_envy_detected=feature_envy,
            duplicate_blocks=[{'method1': d['method1'], 'method2': d['method2'],
                              'similarity': d['similarity']} for d in duplicate_blocks],
            refactored_code=refactored_code,
            explanation=explanations,
        )

    def _identify_responsibilities(
        self, method_lines: List[str], method_dict: Dict
    ) -> List[ResponsibilityBlock]:
        """Split a method body into responsibility blocks."""
        blocks: List[ResponsibilityBlock] = []
        current_lines: List[str] = []
        current_start = 0
        current_type = 'general'
        current_desc = ''

        for i, line in enumerate(method_lines):
            stripped = line.strip()

            # Comment-delimited responsibility
            if stripped.startswith('//') and not stripped.startswith('///'):
                if current_lines and len(current_lines) >= 3:
                    blocks.append(self._make_responsibility_block(
                        current_type, current_start, i - 1 + (method_dict.get('start_line', 1)),
                        current_lines, current_desc,
                    ))
                current_lines = []
                current_start = i
                current_type = 'commented_block'
                current_desc = stripped.lstrip('/ ').strip()
                continue

            # Blank-line separator
            if stripped == '' and current_lines:
                if len(current_lines) >= 3:
                    blocks.append(self._make_responsibility_block(
                        current_type, current_start,
                        current_start + len(current_lines) - 1 + (method_dict.get('start_line', 1)),
                        current_lines, current_desc,
                    ))
                current_lines = []
                current_start = i + 1
                current_type = 'general'
                current_desc = ''
                continue

            current_lines.append(line)

        if current_lines and len(current_lines) >= 3:
            blocks.append(self._make_responsibility_block(
                current_type, current_start,
                current_start + len(current_lines) - 1 + (method_dict.get('start_line', 1)),
                current_lines, current_desc,
            ))

        return blocks

    def _make_responsibility_block(
        self, rtype: str, start: int, end: int,
        code_lines: List[str], desc: str,
    ) -> ResponsibilityBlock:
        all_text = ' '.join(code_lines)
        used = set(re.findall(r'\b([a-z_]\w*)\b', all_text)) - VariableScopeAnalyzer._JAVA_KEYWORDS
        modified = set()
        for line in code_lines:
            for m in re.finditer(r'\b([a-z_]\w*)\s*(?:\+|-|\*|/)?=', line):
                name = m.group(1)
                if name not in VariableScopeAnalyzer._JAVA_KEYWORDS:
                    modified.add(name)
        calls = re.findall(r'\b(\w+)\s*\(', all_text)
        calls = [c for c in calls if c not in ('if', 'for', 'while', 'switch', 'catch')]

        suggested_name = self._generate_method_name(desc, rtype)

        return ResponsibilityBlock(
            responsibility_type=rtype,
            start_line=start,
            end_line=end,
            code_lines=code_lines,
            variables_used=used,
            variables_modified=modified,
            method_calls=calls,
            suggested_method_name=suggested_name,
            description=desc or f'{rtype} block ({len(code_lines)} lines)',
        )

    def _generate_method_name(self, description: str, rtype: str) -> str:
        if description:
            words = re.findall(r'[a-zA-Z]+', description)
            if words:
                return words[0].lower() + ''.join(w.capitalize() for w in words[1:4])
        return f'{rtype}Block'

    def _detect_feature_envy(self, method_dict: Dict) -> bool:
        calls = method_dict.get('method_calls', [])
        if not calls:
            return False
        # Feature envy: more than 60% of calls are on external objects
        external = [c for c in calls if '.' in c]
        return len(external) > len(calls) * 0.6

    # ------------------------------------------------------------------
    #  Helper methods for enhanced analyze_for_decomposition
    # ------------------------------------------------------------------

    def _identify_responsibilities_from_body(
        self, method_body: str, method_name: str
    ) -> List[Dict]:
        """Identify distinct responsibilities within a method body by classifying lines."""
        responsibilities: List[Dict] = []
        lines = method_body.split('\n')

        current_block: List[str] = []
        current_type: Optional[str] = None
        current_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped == '{' or stripped == '}':
                if len(current_block) >= 3 and current_type:
                    responsibilities.append({
                        'type': current_type,
                        'lines': current_block.copy(),
                        'start': current_start,
                        'end': i,
                        'variables': self._extract_variables(current_block),
                    })
                current_block = []
                current_type = None
                continue

            line_type = self._classify_line(line)

            if current_type is None:
                current_type = line_type
                current_start = i
            elif line_type != current_type and len(current_block) >= 3:
                responsibilities.append({
                    'type': current_type,
                    'lines': current_block.copy(),
                    'start': current_start,
                    'end': i - 1,
                    'variables': self._extract_variables(current_block),
                })
                current_block = []
                current_type = line_type
                current_start = i

            current_block.append(line)

        if len(current_block) >= 3 and current_type:
            responsibilities.append({
                'type': current_type,
                'lines': current_block.copy(),
                'start': current_start,
                'end': len(lines) - 1,
                'variables': self._extract_variables(current_block),
            })

        return responsibilities

    def _classify_line(self, line: str) -> str:
        """Classify a line of code by its responsibility type using RESPONSIBILITY_PATTERNS."""
        for resp_type, patterns in self.RESPONSIBILITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return resp_type
        return 'general'

    def _extract_variables(self, lines: List[str]) -> Set[str]:
        """Extract variable names used in a block of code."""
        code = '\n'.join(lines)
        matches = re.findall(r'\b([a-z][a-zA-Z0-9]*)\b', code)
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
                     'continue', 'return', 'try', 'catch', 'finally', 'throw', 'throws',
                     'new', 'this', 'super', 'null', 'true', 'false', 'instanceof',
                     'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short',
                     'void', 'public', 'private', 'protected', 'static', 'final', 'class'}
        return {m for m in matches if m not in keywords}

    def _suggest_extractions(
        self, method_name: str, responsibilities: List[Dict]
    ) -> List[Dict]:
        """Generate extraction suggestions for identified responsibilities."""
        suggestions: List[Dict] = []
        for i, resp in enumerate(responsibilities):
            resp_type = resp['type']
            prefix = self.METHOD_NAME_PREFIXES.get(resp_type, 'process')
            variables = list(resp.get('variables', set()))[:2]
            if variables:
                var_suffix = ''.join(v.capitalize() for v in variables)
                suggested_name = f"{prefix}{var_suffix}"
            else:
                suggested_name = f"{prefix}{method_name.capitalize()}Part{i + 1}"
            suggestions.append({
                'suggested_method_name': suggested_name,
                'responsibility_type': resp_type,
                'line_count': len(resp['lines']),
                'code': '\n'.join(resp['lines']),
                'variables_needed': list(resp.get('variables', set())),
                'rationale': self._get_extraction_rationale(resp_type),
            })
        return suggestions

    def _get_extraction_rationale(self, resp_type: str) -> str:
        """Get explanation for why this extraction improves the code."""
        rationales = {
            'validation': "Isolates input validation logic for reusability and clearer testing",
            'calculation': "Separates computational logic for easier verification and modification",
            'data_access': "Encapsulates data operations for better separation of concerns",
            'transformation': "Isolates data transformation for clearer data flow",
            'output': "Separates presentation logic from business logic",
            'error_handling': "Centralizes error handling for consistent behavior",
            'iteration': "Extracts loop logic for better readability and potential optimization",
            'decision': "Isolates decision logic for easier understanding and modification",
            'general': "Groups related operations for better code organization",
        }
        return rationales.get(resp_type, "Improves code organization and readability")

    def _detect_feature_envy_detailed(
        self, code: str, extracted: Dict
    ) -> List[Dict]:
        """Detect Feature Envy — methods that use other class data more than their own."""
        feature_envy: List[Dict] = []
        for cls in extracted.get('classes', []):
            for method in cls.get('methods', []):
                body = method.get('body', '')
                if not body:
                    continue
                other_refs = len(re.findall(r'(\w+)\.(\w+)\(', body))
                this_refs = len(re.findall(r'this\.(\w+)', body))
                local_refs = len(re.findall(r'\b([a-z][a-zA-Z0-9]*)\s*=', body))
                if other_refs > (this_refs + local_refs) * 1.5 and other_refs > 3:
                    feature_envy.append({
                        'method': method['name'],
                        'class': cls['name'],
                        'external_refs': other_refs,
                        'internal_refs': this_refs + local_refs,
                        'suggestion': "Consider moving this method to the class whose data it uses most",
                    })
        return feature_envy

    def _detect_duplicate_code(self, code: str) -> List[Dict]:
        """Detect duplicate code blocks using Rule of Three."""
        lines = code.split('\n')
        duplicates: List[Dict] = []
        checked_blocks: Set[int] = set()
        min_block_size = 5
        max_lines_to_check = min(100, len(lines) - min_block_size)

        for i in range(max(0, max_lines_to_check)):
            block1 = '\n'.join(lines[i:i + min_block_size])
            if len(block1.strip()) < 50:
                continue
            block1_norm = self._normalize_code_block(block1)
            block1_hash = hash(block1_norm)
            if block1_hash in checked_blocks:
                continue

            occurrences: List[Dict] = []
            for j in range(i + min_block_size, min(i + 50, len(lines) - min_block_size)):
                block2 = '\n'.join(lines[j:j + min_block_size])
                similarity = self._code_block_similarity(block1_norm, self._normalize_code_block(block2))
                if similarity > 0.75:
                    occurrences.append({'line': j + 1, 'similarity': round(similarity * 100, 1)})

            if len(occurrences) >= 2:
                duplicates.append({
                    'original_line': i + 1,
                    'code': block1[:200] + ('...' if len(block1) > 200 else ''),
                    'occurrences': occurrences,
                    'suggestion': "Extract to common method (Rule of Three)",
                })
                checked_blocks.add(block1_hash)
            if len(duplicates) >= 3:
                break

        return duplicates

    def _normalize_code_block(self, code: str) -> str:
        """Normalize code for comparison."""
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'\s+', ' ', code)
        return code.strip().lower()

    def _code_block_similarity(self, norm1: str, norm2: str) -> float:
        """Fast Jaccard similarity between normalized code blocks."""
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _dict_to_method_info(self, d: Dict) -> MethodInfo:
        return MethodInfo(
            name=d.get('name', ''),
            params=d.get('params', []),
            return_type=d.get('return_type', 'void'),
            modifiers=d.get('modifiers', []),
            body_lines=d.get('body_lines', 0),
            start_line=d.get('start_line', 0),
            end_line=d.get('end_line', 0),
            complexity=d.get('complexity', 0),
            nested_depth=d.get('nested_depth', 0),
            local_variables=d.get('local_variables', []),
            method_calls=d.get('method_calls', []),
        )


class StructureChanger:
    """
    High-level class-structure refactoring.
    Divides a God Class into smaller classes by responsibility.
    Uses both field-access clustering (ClassSplitter) and keyword-based grouping.
    """

    RESPONSIBILITY_KEYWORDS = {
        'data_access': ['load', 'save', 'fetch', 'find', 'get', 'set', 'update', 'delete',
                        'insert', 'query', 'repository', 'dao', 'database'],
        'validation': ['validate', 'check', 'verify', 'assert', 'ensure', 'is', 'has'],
        'calculation': ['calculate', 'compute', 'sum', 'total', 'average', 'count', 'math'],
        'formatting': ['format', 'render', 'display', 'print', 'toString', 'convert'],
        'notification': ['notify', 'send', 'email', 'alert', 'message', 'broadcast'],
        'logging': ['log', 'trace', 'debug', 'info', 'warn', 'error'],
        'configuration': ['config', 'setting', 'preference', 'option', 'init', 'setup'],
    }

    def __init__(
        self,
        max_class_lines: int = 200,
        max_methods_per_class: int = 10,
        max_fields_per_class: int = 8,
        min_methods_for_split: int = 3,
    ):
        self.max_class_lines = max_class_lines
        self.max_methods_per_class = max_methods_per_class
        self.max_fields_per_class = max_fields_per_class
        self.min_methods_for_split = min_methods_for_split
        self.class_splitter = ClassSplitter(max_class_lines, max_methods_per_class)

    def analyze_structure(self, code: str) -> Dict[str, Any]:
        """Analyze class structure and suggest improvements."""
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
        except Exception:
            return {'classes': [], 'needs_restructuring': False, 'suggestions': [], 'reasons': []}

        analysis: Dict[str, Any] = {
            'classes': [],
            'needs_restructuring': False,
            'suggestions': [],
            'reasons': [],
            'god_class_detected': False,
            'tight_coupling_detected': False,
            'low_cohesion_detected': False,
            'responsibility_groups': {},
            'suggested_classes': [],
        }

        for cls in extracted.get('classes', []):
            class_info = self._dict_to_class_info(cls)
            split_result = self.class_splitter.analyze_class(class_info)

            total_lines = cls.get('total_lines', 0)
            num_methods = len(cls.get('methods', []))
            num_fields = len(cls.get('fields', []))
            method_names = [m['name'] for m in cls.get('methods', [])]

            class_analysis = {
                'name': cls['name'],
                'lines': total_lines,
                'methods': num_methods,
                'fields': num_fields,
                'needs_split': split_result['needs_split'],
                'reasons': split_result['reasons'],
                'suggested_splits': split_result['suggested_splits'],
            }
            analysis['classes'].append(class_analysis)

            # God Class detection
            if total_lines > self.max_class_lines:
                analysis['needs_restructuring'] = True
                analysis['god_class_detected'] = True
                analysis['reasons'].append(
                    f"God Class: '{cls['name']}' has {total_lines} lines (max: {self.max_class_lines})"
                )
            if num_methods > self.max_methods_per_class:
                analysis['needs_restructuring'] = True
                analysis['god_class_detected'] = True
                analysis['reasons'].append(
                    f"Too many methods: '{cls['name']}' has {num_methods} (max: {self.max_methods_per_class})"
                )
            if num_fields > self.max_fields_per_class:
                analysis['needs_restructuring'] = True
                analysis['reasons'].append(
                    f"Too many fields: '{cls['name']}' has {num_fields} (max: {self.max_fields_per_class})"
                )

            # Responsibility grouping
            resp_groups = self._group_methods_by_responsibility(method_names)
            analysis['responsibility_groups'] = resp_groups

            # Low cohesion detection
            if len(resp_groups) > 2:
                analysis['needs_restructuring'] = True
                analysis['low_cohesion_detected'] = True
                analysis['reasons'].append(
                    f"Low Cohesion: {len(resp_groups)} distinct responsibility groups in '{cls['name']}'"
                )

            if split_result['needs_split']:
                analysis['needs_restructuring'] = True
                analysis['suggestions'].append(
                    f"Split '{cls['name']}' into {len(split_result['suggested_splits'])} classes"
                )

            # Generate suggested class splits from keyword grouping
            if analysis['needs_restructuring']:
                fields = re.findall(
                    r'(private|protected|public)\s+(\w+)\s+(\w+)\s*[;=]', code
                )
                analysis['suggested_classes'] = self._suggest_class_splits(
                    cls['name'], resp_groups, fields, code
                )

        return analysis

    def change_structure(self, code: str) -> StructuralRefactoringResult:
        """Apply structural refactoring to the code."""
        try:
            from java_refactoring_engine.metrics import CouplingCohesionCalculator
        except ImportError:
            from metrics import CouplingCohesionCalculator

        coupling_before = CouplingCohesionCalculator.calculate_coupling(code)
        cohesion_before = CouplingCohesionCalculator.calculate_cohesion(code)

        analysis = self.analyze_structure(code)

        if not analysis['needs_restructuring']:
            return StructuralRefactoringResult(
                success=True,
                original_code=code,
                refactored_code=code,
                new_classes=[],
                coupling_before=coupling_before,
                coupling_after=coupling_before,
                cohesion_before=cohesion_before,
                cohesion_after=cohesion_before,
                explanations=["Code structure is already well-organized."],
                principles_applied=[],
            )

        new_classes: List[NewClassDefinition] = []

        # SUGGESTION-ONLY. The previous implementation replaced original
        # method bodies with delegation calls to generated stub classes whose
        # methods were empty `// TODO` shells. The result compiled and kept
        # every signature — so it slipped past every safety check — but every
        # "moved" method silently became a no-op: a total behavioral
        # regression. Moving method bodies across class boundaries safely
        # requires real semantic analysis (field capture, this-references,
        # visibility) that a regex layer cannot provide. We therefore emit
        # the split plan (class names, method groupings, rationale) without
        # touching the source. refactored_code == original_code, always.
        # Preview code uses REAL method bodies pulled via the parser's
        # brace-matched line ranges (see generate_split_classes) — compilable
        # scaffolding for manual application, never auto-applied.
        parsed_classes = self._get_extracted_classes(code)
        class_infos = {c['name']: self._dict_to_class_info(c) for c in parsed_classes}

        if analysis.get('suggested_classes'):
            for suggestion in analysis['suggested_classes']:
                new_class = self._generate_new_class(suggestion, code)
                ci = class_infos.get(new_class.original_class)
                if ci:
                    preview = self.class_splitter.generate_split_classes(
                        ci,
                        [{'name': new_class.name,
                          'methods': new_class.methods,
                          'fields': new_class.fields}],
                        source_code=code,
                    )
                    new_class.code = preview.get(new_class.name, '')
                new_classes.append(new_class)
        else:
            for cls_analysis in analysis.get('classes', []):
                if not cls_analysis.get('needs_split'):
                    continue
                for cls in parsed_classes:
                    class_info = class_infos[cls['name']]
                    split_result = self.class_splitter.analyze_class(class_info)
                    if not split_result['needs_split']:
                        continue
                    previews = self.class_splitter.generate_split_classes(
                        class_info, split_result['suggested_splits'], source_code=code,
                    )
                    for split in split_result['suggested_splits']:
                        new_classes.append(NewClassDefinition(
                            name=split['name'],
                            responsibility=split.get('reason', ''),
                            fields=split.get('fields', []),
                            methods=split.get('methods', []),
                            original_class=cls['name'],
                            code=previews.get(split['name'], ''),
                        ))

        explanations = self._generate_explanations(analysis, new_classes)
        explanations.append(
            "\nNOTE: Change Structure is advisory — the plan above shows how to "
            "split the class, but the source is left untouched so behavior is "
            "guaranteed to be preserved. Apply the moves manually or with your "
            "IDE's Move Method refactoring."
        )

        principles = [
            "Behavior Preservation - source is never modified by Change Structure",
            "Single Responsibility Principle (SRP) - each suggested class has one responsibility",
            "Separation of Concerns - different concerns in different classes",
            "High Cohesion / Low Coupling - methods grouped by shared data access",
        ]

        return StructuralRefactoringResult(
            success=len(new_classes) > 0,
            original_code=code,
            refactored_code=code,   # advisory: never mutate
            new_classes=new_classes,
            coupling_before=coupling_before,
            coupling_after=coupling_before,
            cohesion_before=cohesion_before,
            cohesion_after=cohesion_before,
            explanations=explanations,
            principles_applied=principles,
        )

    # ------------------------------------------------------------------
    #  Keyword-based responsibility analysis
    # ------------------------------------------------------------------

    def _group_methods_by_responsibility(self, method_names: List[str]) -> Dict[str, List[str]]:
        """Group methods by responsibility type based on naming patterns."""
        groups: Dict[str, List[str]] = defaultdict(list)
        for method in method_names:
            method_lower = method.lower()
            assigned = False
            for responsibility, keywords in self.RESPONSIBILITY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in method_lower:
                        groups[responsibility].append(method)
                        assigned = True
                        break
                if assigned:
                    break
            if not assigned:
                groups['core_logic'].append(method)
        return dict(groups)

    def _suggest_class_splits(
        self, class_name: str, responsibility_groups: Dict[str, List[str]],
        fields: List[tuple], code: str,
    ) -> List[Dict]:
        """Generate suggestions for splitting the class."""
        suggestions: List[Dict] = []
        for responsibility, methods in responsibility_groups.items():
            if len(methods) >= self.min_methods_for_split:
                new_class_name = f"{class_name}{responsibility.replace('_', ' ').title().replace(' ', '')}"
                related_fields = self._find_related_fields(methods, fields, code)
                suggestions.append({
                    'new_class_name': new_class_name,
                    'responsibility': responsibility,
                    'methods': methods,
                    'related_fields': related_fields,
                    'rationale': self._get_split_rationale(responsibility),
                })
        return suggestions

    def _find_related_fields(
        self, methods: List[str], fields: List[tuple], code: str
    ) -> List[str]:
        """Find fields that are used by the given methods."""
        related_fields: List[str] = []
        for method in methods:
            method_pattern = rf'{re.escape(method)}\s*\([^)]*\)\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}'
            match = re.search(method_pattern, code, re.DOTALL)
            if match:
                method_body = match.group(1)
                for field in fields:
                    field_name = field[2] if len(field) > 2 else field[0]
                    if re.search(rf'\b{re.escape(field_name)}\b', method_body):
                        if field_name not in related_fields:
                            related_fields.append(field_name)
        return related_fields

    def _get_split_rationale(self, responsibility: str) -> str:
        """Get explanation for why this split improves design."""
        rationales = {
            'data_access': "Separates data persistence from business logic (SRP)",
            'validation': "Isolates validation rules for reuse and testing",
            'calculation': "Encapsulates computational logic for clarity",
            'formatting': "Separates presentation from domain logic",
            'notification': "Decouples notification mechanism for flexibility",
            'logging': "Centralizes logging for consistent behavior",
            'configuration': "Isolates configuration management",
            'core_logic': "Contains essential business operations",
        }
        return rationales.get(responsibility, "Improves class cohesion and focus")

    # ------------------------------------------------------------------
    #  Code generation
    # ------------------------------------------------------------------

    def _generate_new_class(self, suggestion: Dict, original_code: str) -> NewClassDefinition:
        """Generate code for a new extracted class."""
        class_name = suggestion['new_class_name']
        responsibility = suggestion['responsibility']
        methods = suggestion['methods']
        fields = suggestion.get('related_fields', [])

        class_match = re.search(r'class\s+(\w+)', original_code)
        original_class = class_match.group(1) if class_match else 'Unknown'

        code = f"// {class_name} - Extracted for {responsibility}\n"
        code += f"public class {class_name} {{\n\n"

        if fields:
            for field_name in fields:
                code += f"    private Object {field_name};\n"
            code += "\n"

        code += f"    public {class_name}() {{ }}\n\n"

        for method_name in methods:
            code += f"    public void {method_name}() {{\n"
            code += f"        // TODO: Move {method_name} implementation here\n"
            code += "    }\n\n"

        code += "}\n"

        return NewClassDefinition(
            name=class_name,
            responsibility=responsibility,
            fields=fields,
            methods=methods,
            original_class=original_class,
            code=code,
        )

    def _refactor_main_class(
        self, code: str, analysis: Dict, new_classes: List[NewClassDefinition]
    ) -> str:
        """Refactor the main class to use extracted classes via composition + delegation."""
        class_match = re.search(r'(public\s+class\s+(\w+))', code)
        if not class_match or not new_classes:
            return code

        class_name = class_match.group(2)
        header = "// Refactored using Change Structure - SRP Applied\n\n"
        refactored = code.replace(class_match.group(0), header + class_match.group(0))

        # Add composition fields
        composition_fields = "\n    // Extracted class references\n"
        for new_class in new_classes:
            field_name = new_class.name[0].lower() + new_class.name[1:]
            composition_fields += f"    private final {new_class.name} {field_name} = new {new_class.name}();\n"
        composition_fields += "\n"

        class_brace = refactored.find('{', refactored.find(f'class {class_name}'))
        if class_brace > 0:
            refactored = refactored[:class_brace + 1] + composition_fields + refactored[class_brace + 1:]

        # Add delegation code to moved methods
        for new_class in new_classes:
            field_name = new_class.name[0].lower() + new_class.name[1:]
            for method_name in new_class.methods:
                method_pattern = rf'(public|private|protected)\s+\w+\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{'
                match = re.search(method_pattern, refactored)
                if match:
                    method_body_start = match.end()
                    brace_count = 1
                    pos = method_body_start
                    while pos < len(refactored) and brace_count > 0:
                        if refactored[pos] == '{':
                            brace_count += 1
                        elif refactored[pos] == '}':
                            brace_count -= 1
                        pos += 1
                    delegation_code = f"\n        {field_name}.{method_name}(); // Delegated\n    "
                    refactored = refactored[:method_body_start] + delegation_code + refactored[pos - 1:]

        return refactored

    def _generate_explanations(
        self, analysis: Dict, new_classes: List[NewClassDefinition]
    ) -> List[str]:
        """Generate explanations for the structural changes."""
        explanations = [
            "\n📋 STRUCTURAL REFACTORING REPORT",
            "=" * 50,
        ]

        explanations.append("\n🔍 PROBLEMS IDENTIFIED:")
        for reason in analysis.get('reasons', []):
            explanations.append(f"   • {reason}")

        explanations.append(f"\n✅ NEW CLASSES CREATED ({len(new_classes)}):")
        for new_class in new_classes:
            explanations.append(f"\n   📦 {new_class.name}")
            explanations.append(f"      Responsibility: {new_class.responsibility}")
            explanations.append(f"      Methods: {', '.join(new_class.methods)}")
            explanations.append(f"      Fields: {', '.join(new_class.fields) if new_class.fields else 'None'}")

        explanations.append("\n🎯 KENT BECK TECHNIQUES APPLIED:")
        explanations.append("   • Extract Class - Divided God Class into focused units")
        explanations.append("   • Move Method - Relocated methods to appropriate classes")
        explanations.append("   • Move Field - Moved related fields with methods")
        explanations.append("   • Introduce Interface - Added composition for delegation")

        return explanations

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _get_extracted_classes(self, code: str) -> List[Dict]:
        """Parse and return extracted classes for fallback splitting."""
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
            return extracted.get('classes', [])
        except Exception:
            return []

    def _dict_to_class_info(self, cls_dict: Dict) -> ClassInfo:
        methods = []
        for m in cls_dict.get('methods', []):
            methods.append(MethodInfo(
                name=m['name'],
                params=m.get('params', []),
                return_type=m.get('return_type', 'void'),
                modifiers=m.get('modifiers', []),
                body_lines=m.get('body_lines', 0),
                start_line=m.get('start_line', 0),
                end_line=m.get('end_line', 0),
                complexity=m.get('complexity', 0),
                nested_depth=m.get('nested_depth', 0),
                local_variables=m.get('local_variables', []),
                method_calls=m.get('method_calls', []),
            ))
        fields = []
        for f in cls_dict.get('fields', []):
            fields.append(FieldInfo(
                name=f['name'],
                type_name=f.get('type_name', 'Object'),
                modifiers=f.get('modifiers', []),
                line=f.get('line', 0),
            ))
        return ClassInfo(
            name=cls_dict['name'],
            modifiers=cls_dict.get('modifiers', []),
            extends=cls_dict.get('extends'),
            implements=cls_dict.get('implements', []),
            methods=methods,
            fields=fields,
            inner_classes=[],
            start_line=cls_dict.get('start_line', 0),
            end_line=cls_dict.get('end_line', 0),
            total_lines=cls_dict.get('total_lines', 0),
        )


# ---------------------------------------------------------------------------
#  Main Orchestrator
# ---------------------------------------------------------------------------

class JavaRefactoringEngine:
    """
    Hybrid refactoring engine implementing a two-layer architecture:
      Layer 1 (Deterministic): Dead code, unused imports, condition simplification,
                               guard clauses, loop optimization hints.
      Layer 2 (Heuristic):     Extract method, decompose behavior, change structure,
                               duplicate removal.

    All transformations go through BehaviorPreservationProtocol.
    """

    def __init__(self):
        # Layer 1 — Deterministic
        self.dead_code_eliminator = DeadCodeEliminator()
        self.unused_import_remover = UnusedImportRemover()
        self.condition_simplifier = ConditionSimplifier()
        self.loop_optimizer = LoopOptimizer()

        # Layer 2 — Heuristic
        self.duplicate_detector = DuplicateDetector()
        self.method_extractor = MethodExtractor()
        self.conditional_reducer = ConditionalReducer()
        self.class_splitter = ClassSplitter()
        self.behavior_decomposer = BehaviorDecomposer()
        self.structure_changer = StructureChanger()

        # Safety
        self.behavior_protocol = BehaviorPreservationProtocol()

        # History
        self.history: List[RefactoringResult] = []
        self.parser: Optional[JavaASTParser] = None

    def analyze_code(self, code: str) -> Dict[str, Any]:
        """
        Full analysis: metrics, opportunities (deterministic + heuristic),
        loop-optimisation suggestions, dead-code report.
        """
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
            metrics = copy.deepcopy(parser.metrics)
        except Exception:
            extracted = {'classes': [], 'metrics': CodeMetrics()}
            metrics = CodeMetrics()

        opportunities: List[Dict] = []

        # --- Deterministic opportunities ---

        # Dead code
        dead_items = self.dead_code_eliminator.analyze(code, extracted)
        for item in dead_items:
            opportunities.append({
                'type': 'Dead Code',
                'subtype': item['kind'],
                'name': item['name'],
                'class': item['class'],
                'line': item['line'],
                'safety_score': 1.0,
                'transformation_type': 'Deterministic',
                'description': f"Unused private {item['kind']} '{item['name']}' can be removed",
            })

        # Unused imports
        _, import_actions = self.unused_import_remover.remove(code)
        for act in import_actions:
            opportunities.append({
                'type': 'Unused Import',
                'line': act.line_start,
                'safety_score': 1.0,
                'transformation_type': 'Deterministic',
                'description': act.description,
            })

        # Condition simplification
        cond_opps = self.condition_simplifier.analyze_conditionals(code)
        for co in cond_opps:
            opportunities.append({
                'type': 'Simplify Conditional',
                'analysis': co,
                'safety_score': 1.0,
                'transformation_type': 'Deterministic',
                'recommendation': co.get('recommendation', 'Simplify conditional structure'),
            })

        # Loop optimization
        loop_suggestions = self.loop_optimizer.analyze(code, extracted)
        for ls in loop_suggestions:
            opportunities.append({
                'type': 'Loop Optimization',
                'line': ls['line'],
                'safety_score': ls.get('safety_score', 0.7),
                'transformation_type': 'AI-Suggested',
                'recommendation': ls['recommendation'],
            })

        # --- Heuristic opportunities ---
        for cls in extracted.get('classes', []):
            class_info = self._dict_to_class_info(cls)

            split_analysis = self.class_splitter.analyze_class(class_info)
            if split_analysis['needs_split']:
                opportunities.append({
                    'type': 'Split Class',
                    'class': cls['name'],
                    'reasons': split_analysis['reasons'],
                    'suggested_splits': split_analysis['suggested_splits'],
                    'safety_score': 0.7,
                    'transformation_type': 'AI-Suggested',
                })

            for method in cls.get('methods', []):
                if method.get('body_lines', 0) > 20:
                    opportunities.append({
                        'type': 'Extract Method',
                        'class': cls['name'],
                        'method': method['name'],
                        'description': f"Method '{method['name']}' is {method['body_lines']} lines — extract sub-methods",
                        'safety_score': 0.8,
                        'transformation_type': 'AI-Suggested',
                    })

        cond_analysis = self.conditional_reducer.analyze_conditionals(code)
        for ca in cond_analysis:
            if ca.get('type') == 'long_if_else_chain':
                opportunities.append({
                    'type': 'Replace Conditional with Polymorphism',
                    'analysis': ca,
                    'safety_score': 0.6,
                    'transformation_type': 'AI-Suggested',
                    'recommendation': ca.get('recommendation', ''),
                })

        return {
            'metrics': asdict(metrics) if isinstance(metrics, CodeMetrics) else metrics,
            'opportunities': opportunities,
            'classes': extracted.get('classes', []),
            'total_issues': len(opportunities),
        }

    def refactor(
        self,
        code: str,
        apply_all: bool = False,
        selected_refactorings: Optional[List[str]] = None,
    ) -> RefactoringResult:
        """
        Apply refactoring to Java code.

        Args:
            code: Original Java code
            apply_all: Apply all suggested refactorings
            selected_refactorings: Specific types to apply

        Returns:
            RefactoringResult with refactored code and details
        """
        # Parse original
        self.parser = JavaASTParser()
        self.parser.load_code(code)
        try:
            self.parser.build_ast()
            self.parser.extract_all()
            metrics_before = copy.deepcopy(self.parser.metrics)
        except Exception:
            metrics_before = CodeMetrics()

        actions: List[RefactoringAction] = []
        refactored_code = code
        warnings: List[str] = []
        errors: List[str] = []
        # Method names deliberately removed (dead-code elimination). Passed
        # to the signature-preservation guard so it doesn't roll back
        # intentional removals while still catching accidental ones.
        deliberate_removals: Set[str] = set()

        refactoring_types = selected_refactorings or []
        if apply_all:
            refactoring_types = [
                'dead_code_removal', 'unused_import_removal',
                'condition_simplification', 'reduce_nesting',
                'extract_method', 'remove_duplicates',
                'decompose_behavior', 'change_structure',
            ]

        try:
            # ---- Layer 1: Deterministic (safe, applied first) ----

            if 'dead_code_removal' in refactoring_types:
                refactored_code, dead_actions = self._apply_dead_code_removal(
                    refactored_code
                )
                actions.extend(dead_actions)
                deliberate_removals.update(
                    a.method_name for a in dead_actions if a.method_name
                )

            if 'unused_import_removal' in refactoring_types:
                refactored_code, import_actions = self.unused_import_remover.remove(
                    refactored_code
                )
                actions.extend(import_actions)

            if 'condition_simplification' in refactoring_types:
                refactored_code, cond_actions = self.condition_simplifier.simplify(
                    refactored_code
                )
                actions.extend(cond_actions)

            if 'reduce_nesting' in refactoring_types:
                refactored_code, nest_actions = self._apply_nesting_reduction(
                    refactored_code
                )
                actions.extend(nest_actions)

            # ---- Layer 2: Heuristic (with behavior preservation) ----

            if 'extract_method' in refactoring_types:
                candidate, extract_actions = self._apply_method_extraction(
                    refactored_code
                )
                ok, _ = self.behavior_protocol.post_check(refactored_code, candidate)
                if ok:
                    refactored_code = candidate
                    actions.extend(extract_actions)
                else:
                    warnings.append("extract_method skipped — would introduce errors")

            if 'remove_duplicates' in refactoring_types:
                candidate, dup_actions = self._apply_duplicate_removal(
                    refactored_code
                )
                ok, _ = self.behavior_protocol.post_check(refactored_code, candidate)
                if ok:
                    refactored_code = candidate
                    actions.extend(dup_actions)
                else:
                    warnings.append("remove_duplicates skipped — would introduce errors")

            if 'decompose_behavior' in refactoring_types:
                candidate, decompose_actions = self._apply_behavior_decomposition(
                    refactored_code
                )
                ok, _ = self.behavior_protocol.post_check(refactored_code, candidate)
                if ok:
                    refactored_code = candidate
                    actions.extend(decompose_actions)
                else:
                    warnings.append("decompose_behavior skipped — would introduce errors")

            if 'change_structure' in refactoring_types:
                candidate, struct_actions = self._apply_structure_change(
                    refactored_code
                )
                ok, _ = self.behavior_protocol.post_check(refactored_code, candidate)
                if ok:
                    refactored_code = candidate
                    actions.extend(struct_actions)
                else:
                    warnings.append("change_structure skipped — would introduce errors")

            # Also support legacy names from old engine
            if 'split_class' in refactoring_types and 'change_structure' not in refactoring_types:
                refactored_code, struct_actions = self._apply_structure_change(
                    refactored_code
                )
                actions.extend(struct_actions)

            # ---- Behavior Preservation Final Check ----
            if actions:
                refactored_code, bp_warnings = self.behavior_protocol.safe_apply(
                    code, refactored_code,
                    allowed_removals=deliberate_removals,
                )
                warnings.extend(bp_warnings)
                if bp_warnings:
                    # Rolled back — clear actions
                    actions = []

            # ---- Post-metrics ----
            try:
                parser_after = JavaASTParser()
                parser_after.load_code(refactored_code)
                parser_after.build_ast()
                parser_after.extract_all()
                metrics_after = parser_after.metrics
            except Exception:
                metrics_after = CodeMetrics()

        except Exception as e:
            errors.append(str(e))
            metrics_after = metrics_before

        result = RefactoringResult(
            success=len(errors) == 0 and len(actions) > 0,
            original_code=code,
            refactored_code=refactored_code,
            actions=actions,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            warnings=warnings,
            errors=errors,
        )

        self.history.append(result)
        return result

    def get_history(self) -> List[Dict]:
        """Return refactoring history as dictionaries."""
        return [r.get_summary() for r in self.history]

    def undo_last(self) -> Optional[str]:
        """Return the original code from the last refactoring."""
        if self.history:
            return self.history[-1].original_code
        return None

    def export_report(self) -> str:
        """Export a textual report of all refactorings performed."""
        lines = ['=== Refactoring Report ===\n']
        for i, result in enumerate(self.history, 1):
            summary = result.get_summary()
            lines.append(f'--- Refactoring #{i} ---')
            lines.append(f"  Success: {summary['success']}")
            lines.append(f"  Actions: {summary['total_actions']}")
            lines.append(f"  LOC change: {summary['loc_change']}")
            lines.append(f"  Complexity: {summary['complexity_before']:.1f} → {summary['complexity_after']:.1f}")
            for atype, count in summary['actions_by_type'].items():
                lines.append(f"    {atype}: {count}")
            lines.append('')
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    #  Private apply helpers
    # ------------------------------------------------------------------

    def _apply_dead_code_removal(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Apply dead-code elimination."""
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
        except Exception:
            return code, []

        dead_items = self.dead_code_eliminator.analyze(code, extracted)
        if not dead_items:
            return code, []
        return self.dead_code_eliminator.eliminate(code, dead_items)

    def _apply_nesting_reduction(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Apply guard-clause introduction to reduce nesting."""
        new_code, actions = self.condition_simplifier.reduce_nesting(code)
        # Set heuristic metadata if the transformation was non-trivial
        for a in actions:
            a.safety_score = 0.95
            a.transformation_type = "Deterministic"
        return new_code, actions

    def _apply_method_extraction(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Extract long methods into smaller ones using scope analysis."""
        actions: List[RefactoringAction] = []
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            extracted = parser.extract_all()
        except Exception:
            return code, []

        refactored_code = code
        lines = code.split('\n')

        for cls in extracted.get('classes', []):
            class_name = cls['name']
            for method in cls.get('methods', []):
                method_info = self._dict_to_method_info(method)
                if method_info.body_lines <= self.method_extractor.max_method_lines:
                    continue

                candidates = self.method_extractor.identify_extraction_candidates(
                    refactored_code, method_info
                )
                if not candidates:
                    continue

                new_methods_code = []
                replacements: List[Tuple[str, str]] = []

                for cand in candidates[:3]:  # Limit to 3 extractions per method
                    new_method, call = self.method_extractor.extract_method(
                        refactored_code, cand, class_name
                    )
                    new_methods_code.append(new_method)
                    original_block = '\n'.join(cand['lines'])
                    indent = '        '
                    if cand['lines'] and cand['lines'][0]:
                        indent = cand['lines'][0][:len(cand['lines'][0]) - len(cand['lines'][0].lstrip())]
                    replacements.append((original_block, f'{indent}{call}'))

                    actions.append(RefactoringAction(
                        action_type='extract_method',
                        description=f"Extracted '{cand['suggested_name']}' from '{method['name']}' in {class_name}",
                        original_code=original_block[:200],
                        refactored_code=f'{indent}{call}',
                        safety_score=0.8,
                        transformation_type="AI-Suggested",
                        class_name=class_name,
                        method_name=method['name'],
                        line_start=method.get('start_line', 0),
                        line_end=method.get('end_line', 0),
                    ))

                # Apply replacements
                for orig, repl in replacements:
                    if orig in refactored_code:
                        refactored_code = refactored_code.replace(orig, repl, 1)

                # Insert new methods before class closing brace
                cls_end = cls.get('end_line', len(lines))
                ref_lines = refactored_code.split('\n')
                insert_idx = min(cls_end - 1, len(ref_lines))
                for nm in new_methods_code:
                    ref_lines.insert(insert_idx, nm)
                    insert_idx += 1
                refactored_code = '\n'.join(ref_lines)

        return refactored_code, actions

    def _apply_duplicate_removal(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Detect duplicate methods and repeated in-body patterns.

        DETECTION + REPORTING ONLY — the source is never modified here.
        The previous implementation generated a `commonOperationN()` method
        containing a *copy* of the duplicated code but never replaced the
        original occurrences with calls, so "remove duplicates" actually
        added a third copy (with out-of-scope variables to boot). True clone
        elimination needs call-site rewriting plus parameterization of the
        differing identifiers — and removing a whole duplicate method would
        (correctly) be blocked by the signature-preservation guard anyway.
        We report each clone pair precisely so the user can merge them.
        """
        actions: List[RefactoringAction] = []
        parser = JavaASTParser()
        parser.load_code(code)
        try:
            parser.build_ast()
            parser.extract_all()
            code_blocks = parser.get_code_blocks()
        except Exception:
            return code, []

        duplicates = self.duplicate_detector.find_duplicates(code_blocks)
        for dup in duplicates[:10]:
            exact = dup['similarity'] >= 0.999
            actions.append(RefactoringAction(
                action_type='remove_duplicates',
                description=(
                    f"{'Exact' if exact else 'Near'} duplicate: '{dup['method1']}' and "
                    f"'{dup['method2']}' share {dup['similarity']:.0%} of their structure. "
                    f"{'Delete one and redirect its callers.' if exact else 'Extract the shared logic into a common helper.'}"
                ),
                original_code='\n'.join(dup['lines1'])[:400],
                refactored_code='',   # advisory — no automatic rewrite
                safety_score=0.75,
                transformation_type="Suggestion",
            ))

        # Repeated in-body patterns (same lines pasted 2+ times in one method)
        repeated = self.duplicate_detector.find_repeated_patterns(code)
        for pat in repeated[:5]:
            actions.append(RefactoringAction(
                action_type='remove_duplicates',
                description=(
                    f"Repeated block ({pat['occurrences']}x, at lines "
                    f"{', '.join(str(p) for p in pat['positions'][:4])}) — extract into a helper method"
                ),
                original_code=pat['sample'][:400],
                refactored_code='',
                safety_score=0.75,
                transformation_type="Suggestion",
            ))

        return code, actions

    def _apply_behavior_decomposition(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Apply behavior decomposition to long methods."""
        result = self.behavior_decomposer.decompose(code)

        actions: List[RefactoringAction] = []
        if result.extracted_methods:
            for em in result.extracted_methods:
                actions.append(RefactoringAction(
                    action_type='decompose_behavior',
                    description=(
                        f"Decomposed '{result.original_method_name}' — "
                        f"extracted '{em['name']}' ({em['responsibility']})"
                    ),
                    original_code=code[:200],
                    refactored_code=result.refactored_code[:200],
                    safety_score=0.75,
                    transformation_type="AI-Suggested",
                    method_name=result.original_method_name,
                ))

        return result.refactored_code, actions

    def _apply_structure_change(
        self, code: str
    ) -> Tuple[str, List[RefactoringAction]]:
        """Apply structural class-split refactoring."""
        result = self.structure_changer.change_structure(code)

        actions: List[RefactoringAction] = []
        if result.success:
            for nc in result.new_classes:
                actions.append(RefactoringAction(
                    action_type='change_structure',
                    description=f"Split '{nc.original_class}' → created '{nc.name}'",
                    original_code=code[:200],
                    refactored_code=nc.code[:200] if nc.code else '',
                    safety_score=0.7,
                    transformation_type="AI-Suggested",
                    class_name=nc.original_class,
                ))

        return result.refactored_code, actions

    # ------------------------------------------------------------------
    #  Utility
    # ------------------------------------------------------------------

    def _dict_to_class_info(self, cls_dict: Dict) -> ClassInfo:
        methods = []
        for m in cls_dict.get('methods', []):
            methods.append(MethodInfo(
                name=m['name'],
                params=m.get('params', []),
                return_type=m.get('return_type', 'void'),
                modifiers=m.get('modifiers', []),
                body_lines=m.get('body_lines', 0),
                start_line=m.get('start_line', 0),
                end_line=m.get('end_line', 0),
                complexity=m.get('complexity', 0),
                nested_depth=m.get('nested_depth', 0),
                local_variables=m.get('local_variables', []),
                method_calls=m.get('method_calls', []),
            ))
        fields = []
        for f in cls_dict.get('fields', []):
            fields.append(FieldInfo(
                name=f['name'],
                type_name=f.get('type_name', 'Object'),
                modifiers=f.get('modifiers', []),
                line=f.get('line', 0),
            ))
        return ClassInfo(
            name=cls_dict['name'],
            modifiers=cls_dict.get('modifiers', []),
            extends=cls_dict.get('extends'),
            implements=cls_dict.get('implements', []),
            methods=methods,
            fields=fields,
            inner_classes=[],
            start_line=cls_dict.get('start_line', 0),
            end_line=cls_dict.get('end_line', 0),
            total_lines=cls_dict.get('total_lines', 0),
        )

    def _dict_to_method_info(self, d: Dict) -> MethodInfo:
        return MethodInfo(
            name=d.get('name', ''),
            params=d.get('params', []),
            return_type=d.get('return_type', 'void'),
            modifiers=d.get('modifiers', []),
            body_lines=d.get('body_lines', 0),
            start_line=d.get('start_line', 0),
            end_line=d.get('end_line', 0),
            complexity=d.get('complexity', 0),
            nested_depth=d.get('nested_depth', 0),
            local_variables=d.get('local_variables', []),
            method_calls=d.get('method_calls', []),
        )
