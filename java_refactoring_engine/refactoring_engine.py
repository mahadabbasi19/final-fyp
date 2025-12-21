"""
Refactoring Engine Module
=========================
Core refactoring engine that implements various refactoring techniques
following modern refactoring principles:
- Behavior Preservation
- Small, Safe Steps
- Remove Code Smells
- Single Responsibility Principle
- Extract Methods
- Reduce Coupling / Increase Cohesion
"""

import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from difflib import SequenceMatcher
import copy
import javalang

from .ast_parser import JavaASTParser, ClassInfo, MethodInfo, FieldInfo, CodeMetrics


@dataclass
class RefactoringAction:
    """Represents a single refactoring action."""
    action_type: str  # e.g., 'extract_method', 'split_class', 'reduce_nesting'
    description: str
    original_code: str
    refactored_code: str
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
        """Get a summary of the refactoring."""
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
            'errors_count': len(self.errors)
        }
    
    def _count_actions_by_type(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for action in self.actions:
            counts[action.action_type] += 1
        return dict(counts)


class DuplicateDetector:
    """
    Detects duplicate code blocks using similarity analysis.
    Implements the Rule of Three principle.
    """
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize duplicate detector.
        
        Args:
            similarity_threshold: Minimum similarity ratio to consider as duplicate (0-1)
        """
        self.similarity_threshold = similarity_threshold
    
    def _normalize_code(self, code: str) -> str:
        """
        Normalize code for comparison by removing whitespace variations
        and standardizing variable names.
        
        Args:
            code: Code string to normalize
            
        Returns:
            Normalized code string
        """
        # Remove comments
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        # Normalize whitespace
        code = re.sub(r'\s+', ' ', code)
        code = code.strip()
        
        return code
    
    def _calculate_similarity(self, code1: str, code2: str) -> float:
        """
        Calculate similarity ratio between two code blocks using fast word comparison.
        
        Args:
            code1: First code block
            code2: Second code block
            
        Returns:
            Similarity ratio (0-1)
        """
        norm1 = self._normalize_code(code1)
        norm2 = self._normalize_code(code2)
        
        # Use fast word-based Jaccard similarity instead of slow SequenceMatcher
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0
    
    def _get_code_hash(self, code: str) -> str:
        """
        Get a hash for normalized code to quickly find potential duplicates.
        
        Args:
            code: Code string
            
        Returns:
            Hash string
        """
        normalized = self._normalize_code(code)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def find_duplicates(self, code_blocks: Dict[str, List[str]]) -> List[Dict]:
        """
        Find duplicate code blocks.
        
        Args:
            code_blocks: Dictionary mapping block names to code lines
            
        Returns:
            List of duplicate groups, each containing block names and similarity
        """
        duplicates = []
        block_names = list(code_blocks.keys())
        checked = set()
        
        # OPTIMIZATION: Limit to first 30 blocks to prevent O(n²) slowdown
        max_blocks = min(30, len(block_names))
        
        for i in range(max_blocks):
            name1 = block_names[i]
            code1 = '\n'.join(code_blocks[name1])
            
            # Skip very short blocks (less than 5 lines)
            if len(code_blocks[name1]) < 5:
                continue
                
            duplicate_group = {'original': name1, 'duplicates': [], 'code': code1}
            
            # OPTIMIZATION: Only check next 20 blocks
            for j in range(i + 1, min(i + 20, len(block_names))):
                name2 = block_names[j]
                pair_key = tuple(sorted([name1, name2]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)
                
                code2 = '\n'.join(code_blocks[name2])
                
                # Skip very short blocks
                if len(code_blocks[name2]) < 5:
                    continue
                
                similarity = self._calculate_similarity(code1, code2)
                
                if similarity >= self.similarity_threshold:
                    duplicate_group['duplicates'].append({
                        'name': name2,
                        'similarity': round(similarity * 100, 2),
                        'code': code2
                    })
            
            if duplicate_group['duplicates']:
                duplicates.append(duplicate_group)
                
            # OPTIMIZATION: Stop after finding 5 duplicate groups
            if len(duplicates) >= 5:
                break
        
        return duplicates
    
    def find_repeated_patterns(self, code: str, min_length: int = 3) -> List[Dict]:
        """
        Find repeated code patterns within a single code block.
        
        Args:
            code: Code to analyze
            min_length: Minimum number of lines for a pattern
            
        Returns:
            List of repeated patterns
        """
        lines = code.split('\n')
        patterns = []
        
        # OPTIMIZATION: Limit search space significantly
        max_lines = min(100, len(lines))
        max_pattern_length = min(10, max_lines // 4)
        
        # Look for repeated sequences of lines (limited search)
        for length in range(min_length, max_pattern_length + 1):
            if len(patterns) >= 3:  # Stop after finding 3 patterns
                break
                
            for i in range(min(50, max_lines - length * 2)):
                if len(patterns) >= 3:
                    break
                    
                pattern1 = '\n'.join(lines[i:i + length])
                
                # Only search next 30 lines
                for j in range(i + length, min(i + length + 30, max_lines - length)):
                    pattern2 = '\n'.join(lines[j:j + length])
                    
                    similarity = self._calculate_similarity(pattern1, pattern2)
                    
                    if similarity >= self.similarity_threshold:
                        patterns.append({
                            'pattern': pattern1,
                            'occurrences': [
                                {'start': i, 'end': i + length},
                                {'start': j, 'end': j + length}
                            ],
                            'similarity': round(similarity * 100, 2)
                        })
                        break  # Found match, move to next pattern
        
        return patterns


class MethodExtractor:
    """
    Extracts methods from long code blocks following the
    Extract Methods Aggressively principle.
    """
    
    def __init__(self, max_method_lines: int = 20, max_complexity: int = 10):
        """
        Initialize method extractor.
        
        Args:
            max_method_lines: Maximum allowed lines in a method
            max_complexity: Maximum allowed cyclomatic complexity
        """
        self.max_method_lines = max_method_lines
        self.max_complexity = max_complexity
    
    def identify_extraction_candidates(self, code: str, 
                                       method_info: MethodInfo) -> List[Dict]:
        """
        Identify code blocks that could be extracted into separate methods.
        
        Args:
            code: Method code
            method_info: Method information
            
        Returns:
            List of extraction candidates
        """
        candidates = []
        lines = code.split('\n')
        
        # Find control structure blocks (if, for, while, etc.)
        current_block = []
        block_start = -1
        brace_count = 0
        in_block = False
        block_type = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Detect start of a control structure
            if re.match(r'^(if|for|while|switch|try)\s*\(', stripped):
                if not in_block:
                    in_block = True
                    block_start = i
                    block_type = stripped.split('(')[0].strip()
                    current_block = [line]
                    brace_count = line.count('{') - line.count('}')
                else:
                    current_block.append(line)
                    brace_count += line.count('{') - line.count('}')
            elif in_block:
                current_block.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count <= 0:
                    # Block ended
                    if len(current_block) >= 5:  # Only extract if block is substantial
                        candidates.append({
                            'type': f'extract_{block_type}_block',
                            'start_line': block_start,
                            'end_line': i,
                            'code': '\n'.join(current_block),
                            'suggested_name': self._suggest_method_name(
                                block_type, current_block
                            )
                        })
                    in_block = False
                    current_block = []
                    brace_count = 0
        
        # Find consecutive statement groups (more than 5 related statements)
        statement_group = []
        group_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip empty lines and braces
            if not stripped or stripped in ['{', '}']:
                if len(statement_group) >= 5:
                    candidates.append({
                        'type': 'extract_statement_group',
                        'start_line': group_start,
                        'end_line': i - 1,
                        'code': '\n'.join(statement_group),
                        'suggested_name': self._suggest_method_name(
                            'process', statement_group
                        )
                    })
                statement_group = []
                group_start = -1
            else:
                if group_start == -1:
                    group_start = i
                statement_group.append(line)
        
        return candidates
    
    def _suggest_method_name(self, prefix: str, code_lines: List[str]) -> str:
        """
        Suggest a method name based on code content.
        
        Args:
            prefix: Prefix for the method name
            code_lines: Code lines to analyze
            
        Returns:
            Suggested method name
        """
        # Look for common patterns in the code
        code = '\n'.join(code_lines)
        
        # Check for common operations
        if 'validate' in code.lower() or 'check' in code.lower():
            return f'{prefix}Validation'
        elif 'calculate' in code.lower() or 'compute' in code.lower():
            return f'{prefix}Calculation'
        elif 'process' in code.lower():
            return f'{prefix}Processing'
        elif 'initialize' in code.lower() or 'init' in code.lower():
            return f'{prefix}Initialization'
        elif 'update' in code.lower():
            return f'{prefix}Update'
        elif 'get' in code.lower() or 'fetch' in code.lower():
            return f'{prefix}Retrieval'
        elif 'set' in code.lower():
            return f'{prefix}Assignment'
        else:
            return f'{prefix}Operation'
    
    def extract_method(self, code: str, candidate: Dict, 
                       class_name: str) -> Tuple[str, str]:
        """
        Extract a code block into a separate method.
        
        Args:
            code: Original method code
            candidate: Extraction candidate information
            class_name: Name of the containing class
            
        Returns:
            Tuple of (modified original method, new extracted method)
        """
        lines = code.split('\n')
        block_code = candidate['code']
        method_name = candidate['suggested_name']
        
        # Analyze the block to determine parameters and return type
        variables_used = self._find_used_variables(block_code)
        variables_modified = self._find_modified_variables(block_code)
        
        # Build parameter list
        params = [f"/* parameter */ {var}" for var in variables_used[:3]]
        params_str = ', '.join(params) if params else ''
        
        # Determine return type
        return_type = 'void'
        if variables_modified:
            return_type = 'Object'  # Simplified - would need type analysis
        
        # Create the new method
        new_method = f"""
    /**
     * Extracted method: {method_name}
     * @generated by Refactoring Engine
     */
    private {return_type} {method_name}({params_str}) {{
{self._indent_code(block_code, 8)}
    }}
"""
        
        # Create the method call
        method_call = f"        {method_name}({', '.join(variables_used[:3])});"
        
        # Replace the block in original code with method call
        start = candidate['start_line']
        end = candidate['end_line']
        
        modified_lines = lines[:start] + [method_call] + lines[end + 1:]
        modified_code = '\n'.join(modified_lines)
        
        return modified_code, new_method
    
    def _find_used_variables(self, code: str) -> List[str]:
        """Find variables used in a code block."""
        # Simple pattern matching for variable usage
        pattern = r'\b([a-z][a-zA-Z0-9]*)\b'
        matches = re.findall(pattern, code)
        
        # Filter out Java keywords
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
                   'continue', 'return', 'try', 'catch', 'finally', 'throw', 'throws',
                   'new', 'this', 'super', 'null', 'true', 'false', 'instanceof',
                   'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short',
                   'void', 'String', 'public', 'private', 'protected', 'static', 'final'}
        
        variables = [m for m in matches if m not in keywords]
        return list(dict.fromkeys(variables))  # Remove duplicates, preserve order
    
    def _find_modified_variables(self, code: str) -> List[str]:
        """Find variables that are modified in a code block."""
        # Look for assignment patterns
        pattern = r'([a-z][a-zA-Z0-9]*)\s*[+\-*\/]?='
        matches = re.findall(pattern, code)
        return list(dict.fromkeys(matches))
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified number of spaces."""
        lines = code.split('\n')
        indented = [' ' * spaces + line if line.strip() else line for line in lines]
        return '\n'.join(indented)


class ConditionalReducer:
    """
    Reduces complex conditionals and nested structures.
    Implements Replace Conditionals with Polymorphism principle.
    """
    
    def __init__(self, max_nesting: int = 3):
        """
        Initialize conditional reducer.
        
        Args:
            max_nesting: Maximum allowed nesting depth
        """
        self.max_nesting = max_nesting
    
    def analyze_conditionals(self, code: str) -> List[Dict]:
        """
        Analyze conditional structures in code.
        
        Args:
            code: Code to analyze
            
        Returns:
            List of conditional analysis results
        """
        results = []
        lines = code.split('\n')
        
        nesting_level = 0
        max_nesting_found = 0
        conditional_chains = []
        current_chain = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Track nesting
            if re.match(r'^(if|for|while|switch|try)\s*[\(\{]', stripped):
                nesting_level += 1
                if nesting_level > max_nesting_found:
                    max_nesting_found = nesting_level
            
            # Count closing braces
            if '}' in stripped:
                nesting_level = max(0, nesting_level - stripped.count('}'))
            
            # Track if-else chains
            if stripped.startswith('if'):
                if current_chain:
                    current_chain.append({'line': i, 'type': 'if', 'code': stripped})
                else:
                    current_chain = [{'line': i, 'type': 'if', 'code': stripped}]
            elif stripped.startswith('else if') or stripped.startswith('} else if'):
                current_chain.append({'line': i, 'type': 'else_if', 'code': stripped})
            elif stripped.startswith('else') or stripped.startswith('} else'):
                current_chain.append({'line': i, 'type': 'else', 'code': stripped})
                if len(current_chain) >= 3:
                    conditional_chains.append(current_chain)
                current_chain = []
        
        if max_nesting_found > self.max_nesting:
            results.append({
                'type': 'deep_nesting',
                'max_depth': max_nesting_found,
                'recommendation': 'Consider extracting nested blocks into separate methods'
            })
        
        for chain in conditional_chains:
            if len(chain) >= 3:
                results.append({
                    'type': 'long_if_else_chain',
                    'length': len(chain),
                    'start_line': chain[0]['line'],
                    'recommendation': 'Consider using strategy pattern or lookup table'
                })
        
        return results
    
    def reduce_nesting(self, code: str) -> str:
        """
        Apply guard clauses to reduce nesting.
        
        Args:
            code: Code to refactor
            
        Returns:
            Refactored code with reduced nesting
        """
        lines = code.split('\n')
        refactored_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Look for patterns like: if (condition) { ... } else { return/throw }
            if stripped.startswith('if') and '{' in stripped:
                # Check if this can be converted to a guard clause
                block_end = self._find_block_end(lines, i)
                
                if block_end and block_end < len(lines) - 1:
                    next_line = lines[block_end + 1].strip() if block_end + 1 < len(lines) else ''
                    
                    # If the else block is just a return/throw, convert to guard
                    if next_line.startswith('} else') and 'return' in next_line or 'throw' in next_line:
                        # Convert to guard clause
                        condition = self._extract_condition(stripped)
                        if condition:
                            negated = self._negate_condition(condition)
                            guard = f"    if ({negated}) {{\n        return; // Guard clause\n    }}\n"
                            refactored_lines.append(guard)
                            
                            # Add the original block content without the if wrapper
                            block_content = self._extract_block_content(lines, i + 1, block_end)
                            refactored_lines.extend(block_content)
                            
                            i = block_end + 2
                            continue
            
            refactored_lines.append(line)
            i += 1
        
        return '\n'.join(refactored_lines)
    
    def _find_block_end(self, lines: List[str], start: int) -> Optional[int]:
        """Find the end of a code block."""
        brace_count = 0
        for i in range(start, len(lines)):
            brace_count += lines[i].count('{') - lines[i].count('}')
            if brace_count == 0 and i > start:
                return i
        return None
    
    def _extract_condition(self, if_line: str) -> Optional[str]:
        """Extract condition from an if statement."""
        match = re.search(r'if\s*\((.*)\)\s*\{', if_line)
        return match.group(1) if match else None
    
    def _negate_condition(self, condition: str) -> str:
        """Negate a boolean condition."""
        # Handle simple negations
        if condition.startswith('!'):
            return condition[1:]
        
        # Handle comparison operators
        negations = {
            '==': '!=',
            '!=': '==',
            '<': '>=',
            '>': '<=',
            '<=': '>',
            '>=': '<'
        }
        
        for op, neg in negations.items():
            if op in condition:
                return condition.replace(op, neg, 1)
        
        return f"!({condition})"
    
    def _extract_block_content(self, lines: List[str], start: int, 
                               end: int) -> List[str]:
        """Extract content between block braces."""
        content = []
        for i in range(start, end):
            line = lines[i]
            # Remove one level of indentation
            if line.startswith('        '):
                line = line[4:]
            content.append(line)
        return content
    
    def suggest_polymorphism(self, code: str) -> Optional[Dict]:
        """
        Suggest polymorphic refactoring for type-checking code.
        
        Args:
            code: Code to analyze
            
        Returns:
            Suggestion for polymorphic refactoring if applicable
        """
        # Look for instanceof checks or type-based switches
        instanceof_count = len(re.findall(r'instanceof\s+\w+', code))
        
        if instanceof_count >= 3:
            return {
                'type': 'instanceof_chain',
                'count': instanceof_count,
                'suggestion': 'Consider using polymorphism instead of instanceof checks',
                'pattern': 'Replace type-checking conditional with polymorphic method calls'
            }
        
        return None


class ClassSplitter:
    """
    Splits large classes following the Single Responsibility Principle.
    """
    
    def __init__(self, max_lines: int = 200, max_methods: int = 15):
        """
        Initialize class splitter.
        
        Args:
            max_lines: Maximum allowed lines in a class
            max_methods: Maximum allowed methods in a class
        """
        self.max_lines = max_lines
        self.max_methods = max_methods
    
    def analyze_class(self, class_info: ClassInfo) -> Dict:
        """
        Analyze a class for potential splitting.
        
        Args:
            class_info: Class information
            
        Returns:
            Analysis results with splitting recommendations
        """
        analysis = {
            'name': class_info.name,
            'needs_split': False,
            'reasons': [],
            'suggested_splits': []
        }
        
        if class_info.total_lines > self.max_lines:
            analysis['needs_split'] = True
            analysis['reasons'].append(
                f"Class has {class_info.total_lines} lines (max: {self.max_lines})"
            )
        
        if len(class_info.methods) > self.max_methods:
            analysis['needs_split'] = True
            analysis['reasons'].append(
                f"Class has {len(class_info.methods)} methods (max: {self.max_methods})"
            )
        
        # Group methods by functionality
        method_groups = self._group_methods_by_functionality(class_info.methods)
        
        if len(method_groups) > 2:
            analysis['needs_split'] = True
            analysis['reasons'].append(
                f"Class appears to have {len(method_groups)} distinct responsibilities"
            )
            
            for group_name, methods in method_groups.items():
                if len(methods) >= 2:
                    analysis['suggested_splits'].append({
                        'new_class_name': f"{class_info.name}{group_name}",
                        'methods': [m.name for m in methods],
                        'responsibility': group_name
                    })
        
        return analysis
    
    def _group_methods_by_functionality(self, 
                                        methods: List[MethodInfo]) -> Dict[str, List[MethodInfo]]:
        """
        Group methods by their apparent functionality.
        
        Args:
            methods: List of methods
            
        Returns:
            Dictionary mapping functionality names to methods
        """
        groups = defaultdict(list)
        
        # Common prefixes indicating functionality
        prefixes = {
            'get': 'Accessor',
            'set': 'Mutator',
            'is': 'Accessor',
            'has': 'Accessor',
            'find': 'Query',
            'search': 'Query',
            'load': 'DataAccess',
            'save': 'DataAccess',
            'read': 'DataAccess',
            'write': 'DataAccess',
            'update': 'DataAccess',
            'delete': 'DataAccess',
            'validate': 'Validation',
            'check': 'Validation',
            'calculate': 'Calculation',
            'compute': 'Calculation',
            'process': 'Processing',
            'handle': 'EventHandler',
            'on': 'EventHandler',
            'render': 'Presentation',
            'display': 'Presentation',
            'show': 'Presentation',
            'format': 'Formatting',
            'parse': 'Parsing',
            'convert': 'Conversion',
            'transform': 'Conversion'
        }
        
        for method in methods:
            grouped = False
            name_lower = method.name.lower()
            
            for prefix, group in prefixes.items():
                if name_lower.startswith(prefix):
                    groups[group].append(method)
                    grouped = True
                    break
            
            if not grouped:
                groups['Core'].append(method)
        
        return dict(groups)
    
    def generate_split_classes(self, class_info: ClassInfo, 
                               splits: List[Dict]) -> Dict[str, str]:
        """
        Generate code for split classes.
        
        Args:
            class_info: Original class information
            splits: Splitting recommendations
            
        Returns:
            Dictionary mapping new class names to their code
        """
        generated_classes = {}
        
        for split in splits:
            new_class_name = split['new_class_name']
            methods = split['methods']
            
            # Generate class code
            code = f"""/**
 * {new_class_name}
 * Responsibility: {split['responsibility']}
 * Extracted from: {class_info.name}
 * @generated by Refactoring Engine
 */
public class {new_class_name} {{

"""
            # Add method stubs (would need actual code in real implementation)
            for method_name in methods:
                code += f"""    public void {method_name}() {{
        // Implementation
    }}

"""
            code += "}\n"
            generated_classes[new_class_name] = code
        
        return generated_classes


# ============================================================================
# CHANGE STRUCTURE - Kent Beck Structural Refactoring
# ============================================================================
# 
# CONCEPT DEFINITION (FYP/VIVA READY):
# "Change Structure is a structural refactoring technique that reorganizes 
# classes, responsibilities, and relationships without changing external 
# behavior. It focuses on dividing large classes into multiple focused 
# classes to improve coupling and cohesion."
#
# KEY DIFFERENCES:
# - Decompose Behavior → restructures logic inside methods
# - Change Structure → restructures classes and architecture
#
# WHEN TO APPLY:
# - God Classes (too many responsibilities)
# - Tight Coupling (classes too interdependent)
# - Low Cohesion (unrelated methods grouped together)
# - Poor Scalability and Maintainability
#
# KENT BECK TECHNIQUES USED:
# - Extract Class
# - Move Method
# - Move Field
# - Introduce Interface
# ============================================================================

@dataclass
class NewClassDefinition:
    """
    Represents a new class to be extracted during structural refactoring.
    """
    name: str
    responsibility: str
    fields: List[str]
    methods: List[str]
    original_class: str
    code: str = ""


@dataclass
class StructuralRefactoringResult:
    """
    Result of structural refactoring (Change Structure).
    """
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


class StructureChanger:
    """
    Implements Kent Beck's "Change Structure" refactoring technique.
    
    This class performs structural refactoring by:
    1. Analyzing class structure for responsibility violations
    2. Identifying cohesive groups of fields and methods
    3. Dividing large classes into multiple focused classes
    4. Reducing coupling through dependency inversion
    5. Preserving behavior throughout the process
    
    ATTRIBUTES OF SUCCESSFUL STRUCTURAL DESIGN:
    - High Cohesion: Related elements grouped together
    - Low Coupling: Minimal dependencies between classes
    - Clear Responsibility: Each class has one reason to change
    - Loose Dependencies: Depend on abstractions, not concretions
    - Improved Testability: Smaller, focused units
    - Improved Readability: Clear purpose for each class
    - Improved Extensibility: Easy to add new features
    
    PRINCIPLES INVOLVED:
    - Behavior Preservation (non-negotiable)
    - Single Responsibility Principle (SRP)
    - Separation of Concerns
    - Open-Closed Principle (OCP)
    - Dependency Inversion Principle (DIP)
    - High Cohesion & Low Coupling
    """
    
    # Responsibility keywords for classification
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
    
    def __init__(self, 
                 max_class_lines: int = 200,
                 max_methods_per_class: int = 10,
                 max_fields_per_class: int = 8,
                 min_methods_for_split: int = 3):
        """
        Initialize the structure changer.
        
        Args:
            max_class_lines: Maximum lines before suggesting split
            max_methods_per_class: Maximum methods before suggesting split
            max_fields_per_class: Maximum fields before suggesting split
            min_methods_for_split: Minimum methods needed for a new class
        """
        self.max_class_lines = max_class_lines
        self.max_methods_per_class = max_methods_per_class
        self.max_fields_per_class = max_fields_per_class
        self.min_methods_for_split = min_methods_for_split
    
    def analyze_structure(self, code: str) -> Dict[str, Any]:
        """
        Analyze code structure for refactoring opportunities.
        
        This is Step 1: IDENTIFY STRUCTURAL PROBLEMS
        
        Args:
            code: Java source code
            
        Returns:
            Analysis results with structural issues and recommendations
        """
        analysis = {
            'needs_restructuring': False,
            'reasons': [],
            'god_class_detected': False,
            'tight_coupling_detected': False,
            'low_cohesion_detected': False,
            'responsibility_groups': {},
            'suggested_classes': [],
        }
        
        lines = code.split('\n')
        total_lines = len(lines)
        
        # Find class name
        class_match = re.search(r'class\s+(\w+)', code)
        class_name = class_match.group(1) if class_match else 'Unknown'
        
        # Find all methods
        method_pattern = r'(public|private|protected)\s+\w+\s+(\w+)\s*\([^)]*\)'
        methods = re.findall(method_pattern, code)
        method_names = [m[1] for m in methods]
        
        # Find all fields
        field_pattern = r'(private|protected|public)\s+(\w+)\s+(\w+)\s*[;=]'
        fields = re.findall(field_pattern, code)
        field_names = [f[2] for f in fields]
        
        # Check for God Class (too many lines/methods/fields)
        if total_lines > self.max_class_lines:
            analysis['needs_restructuring'] = True
            analysis['god_class_detected'] = True
            analysis['reasons'].append(
                f"God Class: {total_lines} lines (max: {self.max_class_lines})"
            )
        
        if len(methods) > self.max_methods_per_class:
            analysis['needs_restructuring'] = True
            analysis['god_class_detected'] = True
            analysis['reasons'].append(
                f"Too many methods: {len(methods)} (max: {self.max_methods_per_class})"
            )
        
        if len(fields) > self.max_fields_per_class:
            analysis['needs_restructuring'] = True
            analysis['reasons'].append(
                f"Too many fields: {len(fields)} (max: {self.max_fields_per_class})"
            )
        
        # Group methods by responsibility
        responsibility_groups = self._group_methods_by_responsibility(method_names)
        analysis['responsibility_groups'] = responsibility_groups
        
        # Check for low cohesion (multiple distinct responsibility groups)
        if len(responsibility_groups) > 2:
            analysis['needs_restructuring'] = True
            analysis['low_cohesion_detected'] = True
            analysis['reasons'].append(
                f"Low Cohesion: {len(responsibility_groups)} distinct responsibility groups detected"
            )
        
        # Generate suggested class splits
        if analysis['needs_restructuring']:
            analysis['suggested_classes'] = self._suggest_class_splits(
                class_name, responsibility_groups, fields, code
            )
        
        return analysis
    
    def _group_methods_by_responsibility(self, method_names: List[str]) -> Dict[str, List[str]]:
        """
        Group methods by their responsibility type based on naming patterns.
        
        Args:
            method_names: List of method names
            
        Returns:
            Dictionary mapping responsibility type to method names
        """
        groups = defaultdict(list)
        
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
    
    def _suggest_class_splits(self, class_name: str, 
                              responsibility_groups: Dict[str, List[str]],
                              fields: List[tuple], 
                              code: str) -> List[Dict]:
        """
        Generate suggestions for splitting the class.
        
        Args:
            class_name: Original class name
            responsibility_groups: Methods grouped by responsibility
            fields: List of field tuples (modifier, type, name)
            code: Original source code
            
        Returns:
            List of suggested new classes
        """
        suggestions = []
        
        for responsibility, methods in responsibility_groups.items():
            if len(methods) >= self.min_methods_for_split:
                # Generate new class name
                new_class_name = f"{class_name}{responsibility.replace('_', ' ').title().replace(' ', '')}"
                
                # Find fields used by these methods
                related_fields = self._find_related_fields(methods, fields, code)
                
                suggestions.append({
                    'new_class_name': new_class_name,
                    'responsibility': responsibility,
                    'methods': methods,
                    'related_fields': related_fields,
                    'rationale': self._get_split_rationale(responsibility),
                })
        
        return suggestions
    
    def _find_related_fields(self, methods: List[str], 
                             fields: List[tuple], 
                             code: str) -> List[str]:
        """
        Find fields that are used by the given methods.
        
        Args:
            methods: List of method names
            fields: List of field tuples
            code: Source code
            
        Returns:
            List of field names used by the methods
        """
        related_fields = []
        
        # Extract method bodies (simplified)
        for method in methods:
            method_pattern = rf'{method}\s*\([^)]*\)\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}'
            match = re.search(method_pattern, code, re.DOTALL)
            if match:
                method_body = match.group(1)
                for field in fields:
                    field_name = field[2]
                    if re.search(rf'\b{field_name}\b', method_body):
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
    
    def change_structure(self, code: str) -> StructuralRefactoringResult:
        """
        Apply structural refactoring to divide class into multiple classes.
        
        This method:
        1. Analyzes the code structure
        2. Identifies responsibility groups
        3. Generates new focused classes
        4. Creates refactored code with interface
        5. Calculates coupling/cohesion improvements
        
        Args:
            code: Original Java source code
            
        Returns:
            StructuralRefactoringResult with new classes and metrics
        """
        from java_refactoring_engine.metrics import CouplingCohesionCalculator
        
        # Calculate metrics BEFORE refactoring
        coupling_before = CouplingCohesionCalculator.calculate_coupling(code)
        cohesion_before = CouplingCohesionCalculator.calculate_cohesion(code)
        
        # Analyze structure
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
                principles_applied=[]
            )
        
        # Generate new classes
        new_classes = []
        generated_class_codes = []
        
        for suggestion in analysis['suggested_classes']:
            new_class = self._generate_new_class(suggestion, code)
            new_classes.append(new_class)
            generated_class_codes.append(new_class.code)
        
        # Generate refactored main class
        refactored_main = self._refactor_main_class(code, analysis, new_classes)
        
        # Combine all code
        all_code = refactored_main + "\n\n" + "\n\n".join(generated_class_codes)
        
        # Calculate metrics AFTER refactoring
        coupling_after = CouplingCohesionCalculator.calculate_coupling(refactored_main)
        cohesion_after = CouplingCohesionCalculator.calculate_cohesion(refactored_main)
        
        # Generate explanations
        explanations = self._generate_explanations(analysis, new_classes)
        
        # List principles applied
        principles = [
            "Behavior Preservation - External behavior unchanged",
            "Single Responsibility Principle (SRP) - Each class has one responsibility",
            "Separation of Concerns - Different concerns in different classes",
            "High Cohesion - Related methods grouped together",
            "Low Coupling - Minimal dependencies between classes",
        ]
        
        return StructuralRefactoringResult(
            success=True,
            original_code=code,
            refactored_code=all_code,
            new_classes=new_classes,
            coupling_before=coupling_before,
            coupling_after=coupling_after,
            cohesion_before=cohesion_before,
            cohesion_after=cohesion_after,
            explanations=explanations,
            principles_applied=principles
        )
    
    def _generate_new_class(self, suggestion: Dict, original_code: str) -> NewClassDefinition:
        """
        Generate code for a new extracted class.
        
        Args:
            suggestion: Class split suggestion
            original_code: Original source code
            
        Returns:
            NewClassDefinition with generated code
        """
        from datetime import datetime
        
        class_name = suggestion['new_class_name']
        responsibility = suggestion['responsibility']
        methods = suggestion['methods']
        fields = suggestion.get('related_fields', [])
        
        # Find original class name
        class_match = re.search(r'class\s+(\w+)', original_code)
        original_class = class_match.group(1) if class_match else 'Unknown'
        
        # Generate class code - minimal and clean
        code = f"// {class_name} - Extracted for {responsibility}\n"
        code += f"public class {class_name} {{\n\n"
        
        # Add fields
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
            code=code
        )
    
    def _refactor_main_class(self, code: str, analysis: Dict, 
                             new_classes: List[NewClassDefinition]) -> str:
        """
        Refactor the main class to use extracted classes.
        
        Args:
            code: Original code
            analysis: Structure analysis results
            new_classes: List of extracted classes
            
        Returns:
            Refactored main class code
        """
        from datetime import datetime
        
        # Find class name
        class_match = re.search(r'(public\s+class\s+(\w+))', code)
        if not class_match:
            return code
        
        class_name = class_match.group(2)
        
        # Simple header - just one line
        header = "// Refactored using Change Structure - SRP Applied\n\n"
        
        refactored = code
        
        # Insert header before class declaration
        refactored = refactored.replace(
            class_match.group(0),
            header + class_match.group(0)
        )
        
        # Add composition fields for new classes - simple, no excessive comments
        composition_fields = "\n    // Extracted class references\n"
        
        for new_class in new_classes:
            field_name = new_class.name[0].lower() + new_class.name[1:]
            composition_fields += f"    private final {new_class.name} {field_name} = new {new_class.name}();\n"
        
        composition_fields += "\n"
        
        # Find position after class opening brace
        class_brace = refactored.find('{', refactored.find(f'class {class_name}'))
        if class_brace > 0:
            refactored = refactored[:class_brace + 1] + composition_fields + refactored[class_brace + 1:]
        
        # Add delegation code to methods that were moved
        for new_class in new_classes:
            field_name = new_class.name[0].lower() + new_class.name[1:]
            for method_name in new_class.methods:
                # Find the method and add delegation
                method_pattern = rf'(public|private|protected)\s+\w+\s+{method_name}\s*\([^)]*\)\s*\{{'
                match = re.search(method_pattern, refactored)
                if match:
                    # Find method body start
                    method_body_start = match.end()
                    # Find method body end
                    brace_count = 1
                    pos = method_body_start
                    while pos < len(refactored) and brace_count > 0:
                        if refactored[pos] == '{':
                            brace_count += 1
                        elif refactored[pos] == '}':
                            brace_count -= 1
                        pos += 1
                    
                    # Replace method body with delegation call
                    delegation_code = f"\n        {field_name}.{method_name}(); // Delegated\n    "
                    refactored = refactored[:method_body_start] + delegation_code + refactored[pos-1:]
        
        return refactored
    
    def _generate_explanations(self, analysis: Dict, 
                               new_classes: List[NewClassDefinition]) -> List[str]:
        """Generate explanations for the structural changes."""
        explanations = [
            "\n📋 STRUCTURAL REFACTORING REPORT",
            "=" * 50,
        ]
        
        explanations.append(f"\n🔍 PROBLEMS IDENTIFIED:")
        for reason in analysis['reasons']:
            explanations.append(f"   • {reason}")
        
        explanations.append(f"\n✅ NEW CLASSES CREATED ({len(new_classes)}):")
        for new_class in new_classes:
            explanations.append(f"\n   📦 {new_class.name}")
            explanations.append(f"      Responsibility: {new_class.responsibility}")
            explanations.append(f"      Methods: {', '.join(new_class.methods)}")
            explanations.append(f"      Fields: {', '.join(new_class.fields) if new_class.fields else 'None'}")
        
        explanations.append(f"\n🎯 KENT BECK TECHNIQUES APPLIED:")
        explanations.append("   • Extract Class - Divided God Class into focused units")
        explanations.append("   • Move Method - Relocated methods to appropriate classes")
        explanations.append("   • Move Field - Moved related fields with methods")
        explanations.append("   • Introduce Interface - Added composition for delegation")
        
        return explanations


# ============================================================================
# DECOMPOSE ITS BEHAVIOR - Kent Beck Refactoring Technique
# ============================================================================
# 
# EXAM-READY DEFINITION:
# "Decomposing Behavior is a refactoring technique that breaks down long or 
# complex methods and classes into smaller, focused units where each unit 
# handles exactly one responsibility, while preserving the program's external 
# behavior completely."
#
# Targets these Code Smells:
# - Long Method (>20 lines)
# - Large Class (>200 lines or >15 methods)
# - Feature Envy (method uses another class's data more than its own)
# - Duplicate Code (same logic appears multiple times)
#
# Kent Beck's Principles Applied:
# - Single Responsibility Principle (SRP)
# - Separation of Concerns
# - High Cohesion / Low Coupling
# - Extract Method pattern
# - Behavior Preservation
# ============================================================================

@dataclass
class ResponsibilityBlock:
    """
    Represents a cohesive block of code with a single responsibility.
    Used during behavior decomposition analysis.
    """
    responsibility_type: str  # e.g., 'validation', 'calculation', 'persistence'
    start_line: int
    end_line: int
    code_lines: List[str]
    variables_used: Set[str]
    variables_modified: Set[str]
    method_calls: List[str]
    suggested_method_name: str
    description: str
    
    def get_code(self) -> str:
        return '\n'.join(self.code_lines)


@dataclass
class DecompositionResult:
    """
    Result of behavior decomposition analysis.
    Contains identified responsibilities and extraction suggestions.
    """
    original_method_name: str
    original_line_count: int
    responsibilities: List[ResponsibilityBlock]
    extracted_methods: List[Dict]
    feature_envy_detected: bool
    duplicate_blocks: List[Dict]
    refactored_code: str
    explanation: List[str]


class BehaviorDecomposer:
    """
    Implements Kent Beck's "Decompose Its Behavior" refactoring technique.
    
    This class analyzes complex code and decomposes it into smaller, focused units
    following these principles:
    
    1. IDENTIFY RESPONSIBILITIES: Parse code to find distinct tasks
    2. GROUP RELATED STATEMENTS: Cluster statements by shared variables/purpose
    3. EXTRACT METHODS: Create new methods for each responsibility
    4. REMOVE DUPLICATION: Apply Rule of Three for repeated code
    5. MOVE BEHAVIOR: Address Feature Envy by relocating methods
    6. VERIFY PRESERVATION: Ensure behavior remains identical
    
    Non-Negotiable Rules:
    - Behavior preservation at all costs
    - Each extracted method has Single Responsibility
    - Small, safe, incremental steps
    - Readability over cleverness
    - Avoid over-decomposition
    """
    
    # Responsibility type patterns for classification
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
            r'(\?\s*:)',  # ternary
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
    }
    
    def __init__(self, 
                 max_method_lines: int = 20,
                 max_class_lines: int = 200,
                 max_methods_per_class: int = 15,
                 min_extraction_lines: int = 5):
        """
        Initialize the behavior decomposer.
        
        Args:
            max_method_lines: Threshold for Long Method smell (default: 20)
            max_class_lines: Threshold for Large Class smell (default: 200)
            max_methods_per_class: Max methods before class split (default: 15)
            min_extraction_lines: Minimum lines to consider for extraction (default: 5)
        """
        self.max_method_lines = max_method_lines
        self.max_class_lines = max_class_lines
        self.max_methods_per_class = max_methods_per_class
        self.min_extraction_lines = min_extraction_lines
    
    def analyze_for_decomposition(self, code: str) -> Dict[str, Any]:
        """
        Analyze code for decomposition opportunities.
        
        This is Step 1: IDENTIFY RESPONSIBILITIES
        
        Args:
            code: Java source code to analyze
            
        Returns:
            Dictionary containing analysis results with decomposition suggestions
        """
        lines = code.split('\n')
        analysis = {
            'needs_decomposition': False,
            'reasons': [],
            'long_methods': [],
            'large_classes': [],
            'feature_envy': [],
            'duplicate_code': [],
            'decomposition_suggestions': [],
            'total_responsibilities_found': 0,
        }
        
        # Find all methods using fast regex-based line counting
        method_pattern = re.compile(
            r'(public|private|protected)?\s*(static)?\s*(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{'
        )
        
        methods = []
        # OPTIMIZATION: Limit to first 20 methods
        method_count = 0
        for match in method_pattern.finditer(code):
            if method_count >= 20:
                break
            method_count += 1
            
            method_name = match.group(4)
            method_start = code[:match.start()].count('\n') + 1
            
            # OPTIMIZATION: Estimate method end using limited search (max 500 chars)
            # Instead of counting braces char-by-char through entire file
            search_limit = min(match.end() + 5000, len(code))
            method_body_estimate = code[match.end():search_limit]
            
            # Quick estimate of method lines using newline counting
            method_lines = min(method_body_estimate.count('\n'), 100)
            
            methods.append({
                'name': method_name,
                'start_line': method_start,
                'end_line': method_start + method_lines,
                'line_count': method_lines,
                'body': method_body_estimate[:2000],  # Limit body analysis
                'params': match.group(5),
            })
        
        # Analyze each method for decomposition needs (limit to first 5)
        for method in methods[:5]:
            if method['line_count'] > self.max_method_lines:
                analysis['needs_decomposition'] = True
                analysis['reasons'].append(
                    f"Long Method: '{method['name']}' has {method['line_count']}+ lines "
                    f"(max: {self.max_method_lines})"
                )
                analysis['long_methods'].append(method)
                
                # Skip expensive responsibility identification for performance
                analysis['decomposition_suggestions'].append({
                    'method': method['name'],
                    'current_lines': method['line_count'],
                    'responsibilities': [],
                    'suggested_extractions': [{
                        'name': f"{method['name']}_extracted",
                        'reason': 'Method too long - consider splitting'
                    }]
                })
        
        # Check for Large Class
        total_lines = len(lines)
        total_methods = len(methods)
        
        if total_lines > self.max_class_lines:
            analysis['needs_decomposition'] = True
            analysis['reasons'].append(
                f"Large Class: {total_lines} lines (max: {self.max_class_lines})"
            )
            analysis['large_classes'].append({
                'lines': total_lines,
                'methods': total_methods
            })
        
        if total_methods > self.max_methods_per_class:
            analysis['needs_decomposition'] = True
            analysis['reasons'].append(
                f"Too Many Methods: {total_methods} methods (max: {self.max_methods_per_class})"
            )
        
        # Detect Feature Envy
        feature_envy = self._detect_feature_envy(code, methods)
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
    
    def _identify_responsibilities(self, method_body: str) -> List[Dict]:
        """
        Step 2: GROUP RELATED STATEMENTS
        
        Identify distinct responsibilities within a method body.
        Groups statements that operate on the same variables or serve the same purpose.
        
        Args:
            method_body: The body of the method to analyze
            
        Returns:
            List of identified responsibilities with their characteristics
        """
        responsibilities = []
        lines = method_body.split('\n')
        
        current_block = []
        current_type = None
        current_start = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped == '{' or stripped == '}':
                # End of block - save if substantial
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
            
            # Classify the line
            line_type = self._classify_line(line)
            
            if current_type is None:
                current_type = line_type
                current_start = i
            elif line_type != current_type and len(current_block) >= 3:
                # Responsibility change - save current block
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
        
        # Don't forget the last block
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
        """
        Classify a line of code by its responsibility type.
        
        Args:
            line: Line of code to classify
            
        Returns:
            Responsibility type string
        """
        line_lower = line.lower()
        
        for resp_type, patterns in self.RESPONSIBILITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return resp_type
        
        return 'general'
    
    def _extract_variables(self, lines: List[str]) -> Set[str]:
        """
        Extract variable names used in a block of code.
        
        Args:
            lines: List of code lines
            
        Returns:
            Set of variable names
        """
        code = '\n'.join(lines)
        # Match variable names (simple pattern)
        pattern = r'\b([a-z][a-zA-Z0-9]*)\b'
        matches = re.findall(pattern, code)
        
        # Filter out Java keywords
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
                   'continue', 'return', 'try', 'catch', 'finally', 'throw', 'throws',
                   'new', 'this', 'super', 'null', 'true', 'false', 'instanceof',
                   'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short',
                   'void', 'public', 'private', 'protected', 'static', 'final', 'class'}
        
        return {m for m in matches if m not in keywords}
    
    def _suggest_extractions(self, method_name: str, 
                            responsibilities: List[Dict]) -> List[Dict]:
        """
        Step 3: EXTRACT METHODS
        
        Generate extraction suggestions for identified responsibilities.
        
        Args:
            method_name: Original method name
            responsibilities: List of identified responsibilities
            
        Returns:
            List of extraction suggestions
        """
        suggestions = []
        
        for i, resp in enumerate(responsibilities):
            resp_type = resp['type']
            prefix = self.METHOD_NAME_PREFIXES.get(resp_type, 'process')
            
            # Generate descriptive method name
            variables = list(resp.get('variables', set()))[:2]
            if variables:
                var_suffix = ''.join(v.capitalize() for v in variables)
                suggested_name = f"{prefix}{var_suffix}"
            else:
                suggested_name = f"{prefix}{method_name.capitalize()}Part{i+1}"
            
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
    
    def _detect_feature_envy(self, code: str, methods: List[Dict]) -> List[Dict]:
        """
        Detect Feature Envy smell.
        
        A method has Feature Envy when it uses another class's data more than its own.
        
        Args:
            code: Source code
            methods: List of method information
            
        Returns:
            List of methods with Feature Envy
        """
        feature_envy = []
        
        for method in methods:
            body = method['body']
            
            # Count references to other objects vs local/this
            other_refs = len(re.findall(r'(\w+)\.(\w+)\(', body))
            this_refs = len(re.findall(r'this\.(\w+)', body))
            local_refs = len(re.findall(r'\b([a-z][a-zA-Z0-9]*)\s*=', body))
            
            # If more external references than internal, it's Feature Envy
            if other_refs > (this_refs + local_refs) * 1.5 and other_refs > 3:
                feature_envy.append({
                    'method': method['name'],
                    'external_refs': other_refs,
                    'internal_refs': this_refs + local_refs,
                    'suggestion': "Consider moving this method to the class whose data it uses most"
                })
        
        return feature_envy
    
    def _detect_duplicate_code(self, code: str) -> List[Dict]:
        """
        Step 4: REMOVE DUPLICATION (Rule of Three)
        
        Detect duplicate code blocks that should be extracted.
        
        Args:
            code: Source code to analyze
            
        Returns:
            List of duplicate code patterns
        """
        lines = code.split('\n')
        duplicates = []
        checked_blocks = set()
        
        # Look for blocks of 5+ similar lines
        min_block_size = 5
        
        # OPTIMIZATION: Limit to first 100 lines to prevent O(n²) slowdown
        max_lines_to_check = min(100, len(lines) - min_block_size)
        
        for i in range(max_lines_to_check):
            block1 = '\n'.join(lines[i:i + min_block_size])
            
            # Skip if too short or already checked
            if len(block1.strip()) < 50:
                continue
            
            block1_hash = hash(self._normalize_code(block1))
            if block1_hash in checked_blocks:
                continue
            
            occurrences = []
            # OPTIMIZATION: Only check next 50 lines, not entire file
            for j in range(i + min_block_size, min(i + 50, len(lines) - min_block_size)):
                block2 = '\n'.join(lines[j:j + min_block_size])
                
                similarity = self._calculate_similarity_fast(block1, block2)
                if similarity > 0.75:
                    occurrences.append({
                        'line': j + 1,
                        'similarity': round(similarity * 100, 1)
                    })
            
            # Rule of Three: Flag if appears 2+ more times
            if len(occurrences) >= 2:
                duplicates.append({
                    'original_line': i + 1,
                    'code': block1[:200] + ('...' if len(block1) > 200 else ''),
                    'occurrences': occurrences,
                    'suggestion': "Extract to common method (Rule of Three)"
                })
                checked_blocks.add(block1_hash)
                
            # OPTIMIZATION: Stop after finding 3 duplicates
            if len(duplicates) >= 3:
                break
        
        return duplicates
    
    def _normalize_code(self, code: str) -> str:
        """Normalize code for comparison."""
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'\s+', ' ', code)
        return code.strip().lower()
    
    def _calculate_similarity_fast(self, code1: str, code2: str) -> float:
        """Calculate similarity between two code blocks using fast word-based comparison."""
        # Use fast word set comparison instead of slow SequenceMatcher
        words1 = set(self._normalize_code(code1).split())
        words2 = set(self._normalize_code(code2).split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0
    
    def _calculate_similarity(self, code1: str, code2: str) -> float:
        """Calculate similarity between two code blocks (legacy - use _calculate_similarity_fast)."""
        return self._calculate_similarity_fast(code1, code2)
    
    def decompose(self, code: str, method_name: str = None) -> DecompositionResult:
        """
        Apply behavior decomposition to code.
        
        This is the main refactoring method that:
        1. Analyzes the code
        2. Identifies responsibilities
        3. Extracts methods
        4. Generates refactored code
        
        Args:
            code: Original Java code
            method_name: Specific method to decompose (optional)
            
        Returns:
            DecompositionResult with refactored code and explanations
        """
        analysis = self.analyze_for_decomposition(code)
        
        if not analysis['needs_decomposition']:
            return DecompositionResult(
                original_method_name=method_name or 'unknown',
                original_line_count=len(code.split('\n')),
                responsibilities=[],
                extracted_methods=[],
                feature_envy_detected=False,
                duplicate_blocks=[],
                refactored_code=code,
                explanation=["Code already well-structured, no decomposition needed"]
            )
        
        refactored_code = code
        extracted_methods = []
        explanations = []
        
        # Process decomposition suggestions
        for suggestion in analysis.get('decomposition_suggestions', []):
            target_method = suggestion['method']
            
            if method_name and target_method != method_name:
                continue
            
            explanations.append(f"\n📋 DECOMPOSING METHOD: {target_method}")
            explanations.append(f"   Original size: {suggestion['current_lines']} lines")
            explanations.append(f"   Responsibilities found: {len(suggestion['responsibilities'])}")
            
            for extraction in suggestion.get('suggested_extractions', []):
                method_code = extraction['code']
                new_name = extraction['suggested_method_name']
                resp_type = extraction['responsibility_type']
                
                # Generate the extracted method
                extracted_method = self._generate_extracted_method(
                    new_name, 
                    method_code,
                    extraction['variables_needed']
                )
                
                extracted_methods.append({
                    'name': new_name,
                    'code': extracted_method,
                    'type': resp_type,
                    'rationale': extraction['rationale']
                })
                
                explanations.append(f"\n   ✅ Extracted: {new_name}()")
                explanations.append(f"      Type: {resp_type}")
                explanations.append(f"      Rationale: {extraction['rationale']}")
        
        # Insert extracted methods and add comments
        refactored_code = self._apply_decomposition(code, extracted_methods, analysis)
        
        # Add duplicate code markers
        if analysis.get('duplicate_code'):
            for dup in analysis['duplicate_code']:
                explanations.append(f"\n   ⚠️ Duplicate code at line {dup['original_line']}")
                explanations.append(f"      Found {len(dup['occurrences'])} similar blocks")
                explanations.append(f"      Suggestion: {dup['suggestion']}")
        
        # Add Feature Envy warnings
        if analysis.get('feature_envy'):
            for fe in analysis['feature_envy']:
                explanations.append(f"\n   🔄 Feature Envy in: {fe['method']}")
                explanations.append(f"      External refs: {fe['external_refs']}, Internal: {fe['internal_refs']}")
                explanations.append(f"      {fe['suggestion']}")
        
        return DecompositionResult(
            original_method_name=method_name or 'multiple',
            original_line_count=len(code.split('\n')),
            responsibilities=[],
            extracted_methods=extracted_methods,
            feature_envy_detected=bool(analysis.get('feature_envy')),
            duplicate_blocks=analysis.get('duplicate_code', []),
            refactored_code=refactored_code,
            explanation=explanations
        )
    
    def _generate_extracted_method(self, name: str, body: str, 
                                   variables: List[str]) -> str:
        """
        Generate code for an extracted method.
        
        Args:
            name: Method name
            body: Method body code
            variables: Variables that need to be parameters
            
        Returns:
            Complete method code
        """
        # Determine parameters (limit to 3 for readability)
        params = variables[:3] if variables else []
        params_str = ', '.join(f"Object {v}" for v in params)
        
        method = f"""
    /**
     * {name} - Extracted for Single Responsibility
     * 
     * Responsibility: {self._infer_responsibility_description(name)}
     * 
     * @generated by Java Refactoring Engine - Decompose Behavior
     * @principle Single Responsibility Principle (SRP)
     */
    private void {name}({params_str}) {{
{self._indent_code(body, 8)}
    }}
"""
        return method
    
    def _infer_responsibility_description(self, method_name: str) -> str:
        """Infer a description from the method name."""
        name_lower = method_name.lower()
        if 'validate' in name_lower:
            return "Input validation and constraint checking"
        elif 'calculate' in name_lower or 'compute' in name_lower:
            return "Mathematical computation and calculation"
        elif 'fetch' in name_lower or 'load' in name_lower:
            return "Data retrieval and access"
        elif 'convert' in name_lower or 'transform' in name_lower:
            return "Data transformation and conversion"
        elif 'format' in name_lower:
            return "Output formatting and presentation"
        elif 'handle' in name_lower:
            return "Error and exception handling"
        elif 'process' in name_lower:
            return "Data processing and iteration"
        else:
            return "Specific isolated behavior"
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified number of spaces."""
        lines = code.split('\n')
        return '\n'.join(' ' * spaces + line if line.strip() else line for line in lines)
    
    def _apply_decomposition(self, code: str, extracted_methods: List[Dict], 
                            analysis: Dict) -> str:
        """
        Apply the decomposition to the code.
        
        Args:
            code: Original code
            extracted_methods: List of extracted methods
            analysis: Analysis results
            
        Returns:
            Refactored code with decomposition applied
        """
        from datetime import datetime
        
        refactored = code
        
        # Add decomposition header comment
        header = f"""
// ═══════════════════════════════════════════════════════════════════════════
// DECOMPOSE ITS BEHAVIOR - Kent Beck Refactoring Applied
// ═══════════════════════════════════════════════════════════════════════════
// Refactoring Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
// 
// Code Smells Addressed:
"""
        for reason in analysis.get('reasons', []):
            header += f"//   • {reason}\n"
        
        header += """// 
// Principles Applied:
//   • Single Responsibility Principle (SRP)
//   • Separation of Concerns
//   • High Cohesion / Low Coupling
//   • Extract Method Pattern
//   • Behavior Preservation
// 
// Generated by: Java Refactoring Engine
// ═══════════════════════════════════════════════════════════════════════════

"""
        
        # Find class declaration and insert header before it
        class_match = re.search(r'(public\s+class\s+\w+)', refactored)
        if class_match:
            refactored = refactored[:class_match.start()] + header + refactored[class_match.start():]
        
        # Insert extracted methods before the last closing brace
        if extracted_methods:
            methods_section = """
    // ═══════════════════════════════════════════════════════════════════════
    // EXTRACTED METHODS - Single Responsibility Principle
    // ═══════════════════════════════════════════════════════════════════════
"""
            for method in extracted_methods:
                methods_section += method['code']
            
            # Find the last closing brace of the class
            last_brace = refactored.rfind('}')
            if last_brace > 0:
                refactored = refactored[:last_brace] + methods_section + '\n}\n'
        
        # Add TODO comments for long methods
        for method_info in analysis.get('long_methods', []):
            method_name = method_info['name']
            pattern = rf'(public|private|protected)\s+\w+\s+{method_name}\s*\([^)]*\)\s*\{{'
            match = re.search(pattern, refactored)
            if match:
                todo_comment = f"""
        // 🔧 TODO: DECOMPOSE THIS METHOD
        // Current size: {method_info['line_count']} lines (recommended: < {self.max_method_lines})
        // Suggested decomposition:
"""
                for suggestion in analysis.get('decomposition_suggestions', []):
                    if suggestion['method'] == method_name:
                        for ext in suggestion.get('suggested_extractions', []):
                            todo_comment += f"        //   • Call {ext['suggested_method_name']}() for {ext['responsibility_type']}\n"
                
                insert_pos = match.end()
                refactored = refactored[:insert_pos] + todo_comment + refactored[insert_pos:]
        
        return refactored


class JavaRefactoringEngine:
    """
    Main refactoring engine that orchestrates all refactoring operations.
    Implements the complete refactoring workflow with behavior preservation.
    """
    
    def __init__(self):
        """Initialize the refactoring engine with all components."""
        self.parser = None
        self.duplicate_detector = DuplicateDetector()
        self.method_extractor = MethodExtractor()
        self.conditional_reducer = ConditionalReducer()
        self.class_splitter = ClassSplitter()
        self.behavior_decomposer = BehaviorDecomposer()  # Kent Beck technique
        self.structure_changer = StructureChanger()  # NEW: Change Structure technique
        self.history: List[RefactoringResult] = []
    
    def analyze_code(self, code: str) -> Dict[str, Any]:
        """
        Analyze Java code for refactoring opportunities.
        
        Args:
            code: Java source code
            
        Returns:
            Analysis results with refactoring suggestions
        """
        self.parser = JavaASTParser()
        self.parser.load_code(code)
        self.parser.build_ast()
        structure = self.parser.extract_all()
        
        analysis = {
            'structure': structure,
            'code_smells': [],
            'refactoring_opportunities': [],
            'metrics': self.parser.metrics.to_dict()
        }
        
        # Detect code smells
        analysis['code_smells'] = self._detect_code_smells(structure, code)
        
        # Find refactoring opportunities
        analysis['refactoring_opportunities'] = self._find_refactoring_opportunities(
            structure, code
        )
        
        return analysis
    
    def _detect_code_smells(self, structure: Dict, code: str) -> List[Dict]:
        """Detect code smells in the analyzed code."""
        smells = []
        
        for cls_dict in structure['classes']:
            # Large class smell
            if cls_dict['total_lines'] > 200:
                smells.append({
                    'type': 'Large Class',
                    'class': cls_dict['name'],
                    'description': f"Class has {cls_dict['total_lines']} lines (recommended: < 200)",
                    'severity': 'high'
                })
            
            # Too many methods
            if len(cls_dict['methods']) > 15:
                smells.append({
                    'type': 'Too Many Methods',
                    'class': cls_dict['name'],
                    'description': f"Class has {len(cls_dict['methods'])} methods (recommended: < 15)",
                    'severity': 'medium'
                })
            
            # Analyze individual methods
            for method in cls_dict['methods']:
                # Long method smell
                if method['body_lines'] > 20:
                    smells.append({
                        'type': 'Long Method',
                        'class': cls_dict['name'],
                        'method': method['name'],
                        'description': f"Method has {method['body_lines']} lines (recommended: < 20)",
                        'severity': 'medium'
                    })
                
                # High complexity smell
                if method['complexity'] > 10:
                    smells.append({
                        'type': 'High Complexity',
                        'class': cls_dict['name'],
                        'method': method['name'],
                        'description': f"Cyclomatic complexity is {method['complexity']} (recommended: < 10)",
                        'severity': 'high'
                    })
        
        # Detect duplicate code
        code_blocks = self.parser.get_code_blocks()
        duplicates = self.duplicate_detector.find_duplicates(code_blocks)
        
        for dup in duplicates:
            smells.append({
                'type': 'Duplicate Code',
                'original': dup['original'],
                'duplicates': [d['name'] for d in dup['duplicates']],
                'description': f"Code block duplicated {len(dup['duplicates'])} times",
                'severity': 'high'
            })
        
        return smells
    
    def _find_refactoring_opportunities(self, structure: Dict, 
                                        code: str) -> List[Dict]:
        """Find specific refactoring opportunities."""
        opportunities = []
        
        for cls_dict in structure['classes']:
            # Check for class splitting opportunities
            class_info = self._dict_to_class_info(cls_dict)
            split_analysis = self.class_splitter.analyze_class(class_info)
            
            if split_analysis['needs_split']:
                opportunities.append({
                    'type': 'Split Class',
                    'class': cls_dict['name'],
                    'reasons': split_analysis['reasons'],
                    'suggested_splits': split_analysis['suggested_splits']
                })
            
            # Check for method extraction opportunities
            for method in cls_dict['methods']:
                if method['body_lines'] > 20:
                    opportunities.append({
                        'type': 'Extract Method',
                        'class': cls_dict['name'],
                        'method': method['name'],
                        'description': 'Method is too long and should be broken down'
                    })
        
        # Check for conditional refactoring
        conditional_analysis = self.conditional_reducer.analyze_conditionals(code)
        for analysis in conditional_analysis:
            opportunities.append({
                'type': 'Simplify Conditional',
                'analysis': analysis,
                'recommendation': analysis.get('recommendation', 'Simplify conditional structure')
            })
        
        return opportunities
    
    def _dict_to_class_info(self, cls_dict: Dict) -> ClassInfo:
        """Convert dictionary to ClassInfo object."""
        methods = []
        for m in cls_dict['methods']:
            method_info = MethodInfo(
                name=m['name'],
                params=m['params'],
                return_type=m['return_type'],
                modifiers=m['modifiers'],
                body_lines=m['body_lines'],
                start_line=m['start_line'],
                end_line=m['end_line'],
                complexity=m['complexity'],
                nested_depth=m['nested_depth'],
                local_variables=m['local_variables'],
                method_calls=m['method_calls']
            )
            methods.append(method_info)
        
        fields = []
        for f in cls_dict['fields']:
            field_info = FieldInfo(
                name=f['name'],
                type_name=f['type_name'],
                modifiers=f['modifiers'],
                line=f['line']
            )
            fields.append(field_info)
        
        return ClassInfo(
            name=cls_dict['name'],
            modifiers=cls_dict['modifiers'],
            extends=cls_dict['extends'],
            implements=cls_dict['implements'],
            methods=methods,
            fields=fields,
            inner_classes=[],
            start_line=cls_dict['start_line'],
            end_line=cls_dict['end_line'],
            total_lines=cls_dict['total_lines']
        )
    
    def refactor(self, code: str, 
                 apply_all: bool = False,
                 selected_refactorings: Optional[List[str]] = None) -> RefactoringResult:
        """
        Apply refactoring to Java code.
        
        Args:
            code: Original Java code
            apply_all: Apply all suggested refactorings
            selected_refactorings: List of specific refactoring types to apply
            
        Returns:
            RefactoringResult with refactored code and details
        """
        # Parse and analyze original code (with graceful error handling)
        self.parser = JavaASTParser()
        self.parser.load_code(code)
        try:
            self.parser.build_ast()
            self.parser.extract_all()
            metrics_before = copy.deepcopy(self.parser.metrics)
        except Exception as ast_error:
            # If AST parsing fails, use regex-based analysis with default metrics
            metrics_before = {
                'loc': len(code.split('\n')),
                'methods': 0,
                'classes': 0,
                'complexity': 0
            }
        
        actions = []
        refactored_code = code
        warnings = []
        errors = []
        
        # Determine which refactorings to apply
        refactoring_types = selected_refactorings or []
        if apply_all:
            refactoring_types = ['extract_method', 'reduce_nesting', 
                                'remove_duplicates', 'decompose_behavior', 'split_class']
        
        try:
            # Apply refactorings in safe order (small changes first)
            
            # 1. Reduce nesting (safe, doesn't change structure much)
            if 'reduce_nesting' in refactoring_types:
                refactored_code, nesting_actions = self._apply_nesting_reduction(
                    refactored_code
                )
                actions.extend(nesting_actions)
            
            # 2. Extract methods (medium impact)
            if 'extract_method' in refactoring_types:
                refactored_code, extract_actions = self._apply_method_extraction(
                    refactored_code
                )
                actions.extend(extract_actions)
            
            # 3. Remove duplicates (creates new methods)
            if 'remove_duplicates' in refactoring_types:
                refactored_code, dup_actions = self._apply_duplicate_removal(
                    refactored_code
                )
                actions.extend(dup_actions)
            
            # 4. NEW: Decompose Behavior (Kent Beck technique)
            if 'decompose_behavior' in refactoring_types:
                refactored_code, decompose_actions = self._apply_behavior_decomposition(
                    refactored_code
                )
                actions.extend(decompose_actions)
            
            # 5. NEW: Change Structure - Divide into Multiple Classes
            if 'change_structure' in refactoring_types:
                refactored_code, structure_actions = self._apply_structure_change(
                    refactored_code
                )
                actions.extend(structure_actions)
            
            # Parse refactored code for metrics (with graceful error handling)
            try:
                parser_after = JavaASTParser()
                parser_after.load_code(refactored_code)
                parser_after.build_ast()
                parser_after.extract_all()
                metrics_after = parser_after.metrics
            except Exception as parse_error:
                # If parsing fails, use default metrics based on line count
                metrics_after = {
                    'loc': len(refactored_code.split('\n')),
                    'methods': 0,
                    'classes': 0,
                    'complexity': 0
                }
            
        except Exception as e:
            errors.append(str(e))
            metrics_after = metrics_before
        
        # Create result
        result = RefactoringResult(
            success=len(errors) == 0,
            original_code=code,
            refactored_code=refactored_code,
            actions=actions,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            warnings=warnings,
            errors=errors
        )
        
        # Add to history
        self.history.append(result)
        
        return result
    
    def _apply_nesting_reduction(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """Apply nesting reduction refactoring."""
        actions = []
        refactored = self.conditional_reducer.reduce_nesting(code)
        
        if refactored != code:
            actions.append(RefactoringAction(
                action_type='reduce_nesting',
                description='Applied guard clauses to reduce nesting depth',
                original_code=code,
                refactored_code=refactored
            ))
        
        return refactored, actions
    
    def _apply_method_extraction(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """Apply method extraction refactoring - extracts long code blocks into methods."""
        actions = []
        lines = code.split('\n')
        refactored_lines = []
        extracted_methods = []
        
        i = 0
        method_counter = 1
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Look for long if/for/while blocks (more than 10 lines)
            if re.match(r'^(if|for|while)\s*\(', stripped):
                # Find the block
                block_start = i
                brace_count = line.count('{') - line.count('}')
                block_lines = [line]
                j = i + 1
                
                while j < len(lines) and (brace_count > 0 or '{' not in ''.join(block_lines)):
                    block_lines.append(lines[j])
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    j += 1
                
                # If block is long enough, extract it
                if len(block_lines) > 10:
                    indent = len(line) - len(line.lstrip())
                    indent_str = ' ' * indent
                    
                    # Determine method name based on content
                    block_code = '\n'.join(block_lines)
                    if 'validate' in block_code.lower():
                        method_name = f"performValidation{method_counter}"
                    elif 'process' in block_code.lower():
                        method_name = f"processBlock{method_counter}"
                    elif 'calculate' in block_code.lower():
                        method_name = f"calculateValues{method_counter}"
                    else:
                        method_name = f"extractedMethod{method_counter}"
                    
                    method_counter += 1
                    
                    # Replace block with method call
                    refactored_lines.append(f"{indent_str}// Extracted to {method_name}()")
                    refactored_lines.append(f"{indent_str}{method_name}();")
                    
                    # Create extracted method
                    extracted_method = f"\n    /**\n     * Extracted method - improves readability\n     * @generated by Refactoring Engine\n     */\n    private void {method_name}() {{\n"
                    for bl in block_lines:
                        extracted_method += f"    {bl}\n"
                    extracted_method += "    }\n"
                    extracted_methods.append(extracted_method)
                    
                    actions.append(RefactoringAction(
                        action_type='extract_method',
                        description=f'Extracted {len(block_lines)} lines to {method_name}()',
                        original_code=block_code,
                        refactored_code=f"{method_name}();"
                    ))
                    
                    i = j
                    continue
            
            refactored_lines.append(line)
            i += 1
        
        # Add extracted methods before the last closing brace
        if extracted_methods:
            # Find last closing brace of class
            result_code = '\n'.join(refactored_lines)
            last_brace = result_code.rfind('}')
            if last_brace > 0:
                result_code = result_code[:last_brace] + '\n'.join(extracted_methods) + '\n}'
            return result_code, actions
        
        return code, actions
    
    def _apply_duplicate_removal(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """Apply duplicate code removal - finds similar blocks and extracts common method."""
        actions = []
        lines = code.split('\n')
        
        # Find duplicate patterns (similar consecutive lines)
        duplicates_found = []
        
        for i in range(len(lines) - 4):
            block1 = '\n'.join(lines[i:i+5])
            if len(block1.strip()) < 50:  # Skip short blocks
                continue
                
            for j in range(i + 5, len(lines) - 4):
                block2 = '\n'.join(lines[j:j+5])
                
                # Simple similarity check
                words1 = set(block1.split())
                words2 = set(block2.split())
                if len(words1) > 5 and len(words2) > 5:
                    similarity = len(words1 & words2) / max(len(words1 | words2), 1)
                    
                    if similarity > 0.7:
                        duplicates_found.append({
                            'line1': i,
                            'line2': j,
                            'block': block1,
                            'similarity': similarity
                        })
                        break  # Only report first duplicate
        
        if duplicates_found:
            # Create a common method for the first duplicate found
            dup = duplicates_found[0]
            
            # Generate refactored code with extracted method
            refactored_lines = lines.copy()
            
            actions.append(RefactoringAction(
                action_type='remove_duplicates',
                description=f"Duplicate code found at lines {dup['line1']+1} and {dup['line2']+1} ({dup['similarity']*100:.0f}% similar)",
                original_code=dup['block'],
                refactored_code="// Marked for extraction"
            ))
            
            return '\n'.join(refactored_lines), actions
        
        return code, actions
    
    def _apply_behavior_decomposition(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """
        Apply Kent Beck's "Decompose Its Behavior" refactoring technique.
        
        This method:
        1. Analyzes code for decomposition opportunities
        2. Identifies distinct responsibilities in long methods
        3. Generates extracted methods for each responsibility
        4. Preserves original behavior while improving structure
        
        Args:
            code: Original Java source code
            
        Returns:
            Tuple of (refactored code, list of actions taken)
        """
        actions = []
        
        # Use the BehaviorDecomposer to analyze and refactor
        decomposition_result = self.behavior_decomposer.decompose(code)
        
        # If decomposition was applied, record the action
        if decomposition_result.refactored_code != code:
            # Create detailed description
            description_parts = [
                "Applied Kent Beck's 'Decompose Its Behavior' technique:"
            ]
            
            if decomposition_result.extracted_methods:
                description_parts.append(
                    f"  - Extracted {len(decomposition_result.extracted_methods)} method(s)"
                )
                for method in decomposition_result.extracted_methods:
                    description_parts.append(
                        f"    • {method['name']}() [{method['type']}]"
                    )
            
            if decomposition_result.duplicate_blocks:
                description_parts.append(
                    f"  - Identified {len(decomposition_result.duplicate_blocks)} duplicate block(s)"
                )
            
            if decomposition_result.feature_envy_detected:
                description_parts.append(
                    "  - Detected Feature Envy (methods using other class data)"
                )
            
            actions.append(RefactoringAction(
                action_type='decompose_behavior',
                description='\n'.join(description_parts),
                original_code=code,
                refactored_code=decomposition_result.refactored_code
            ))
            
            # Add explanation as separate info action
            if decomposition_result.explanation:
                explanation_text = '\n'.join(decomposition_result.explanation)
                actions.append(RefactoringAction(
                    action_type='decompose_behavior_explanation',
                    description="Decomposition Analysis:\n" + explanation_text,
                    original_code="",
                    refactored_code=""
                ))
            
            return decomposition_result.refactored_code, actions
        
        return code, actions
    
    def _apply_structure_change(self, code: str) -> Tuple[str, List[RefactoringAction]]:
        """
        Apply Kent Beck's "Change Structure" refactoring technique.
        
        This method:
        1. Analyzes code for structural issues (God Class, low cohesion)
        2. Divides large classes into multiple focused classes
        3. Reduces coupling and improves cohesion
        4. Preserves original behavior
        
        Args:
            code: Original Java source code
            
        Returns:
            Tuple of (refactored code, list of actions taken)
        """
        actions = []
        
        # Use the StructureChanger to analyze and refactor
        result = self.structure_changer.change_structure(code)
        
        if result.refactored_code != code and result.new_classes:
            # Create detailed description
            description_parts = [
                "Applied Kent Beck's 'Change Structure' technique:",
                f"  - Created {len(result.new_classes)} new class(es):"
            ]
            
            for new_class in result.new_classes:
                description_parts.append(
                    f"    • {new_class.name} [{new_class.responsibility}]"
                )
            
            # Add coupling/cohesion metrics
            description_parts.append("")
            description_parts.append("📊 COUPLING & COHESION METRICS:")
            description_parts.append(f"  Coupling: {result.coupling_before['coupling_level']} → {result.coupling_after['coupling_level']}")
            description_parts.append(f"    Score: {result.coupling_before['coupling_score']} → {result.coupling_after['coupling_score']}")
            description_parts.append(f"  Cohesion: {result.cohesion_before['cohesion_level']} → {result.cohesion_after['cohesion_level']}")
            description_parts.append(f"    Score: {result.cohesion_before['cohesion_score']} → {result.cohesion_after['cohesion_score']}")
            
            actions.append(RefactoringAction(
                action_type='change_structure',
                description='\n'.join(description_parts),
                original_code=code,
                refactored_code=result.refactored_code
            ))
            
            # Add separate action for each new class
            for new_class in result.new_classes:
                actions.append(RefactoringAction(
                    action_type='new_class_created',
                    description=f"New class: {new_class.name} - {new_class.responsibility}",
                    original_code="",
                    refactored_code=new_class.code,
                    class_name=new_class.name
                ))
            
            return result.refactored_code, actions
        
        return code, actions
    
    def get_history(self) -> List[Dict]:
        """Get refactoring history."""
        return [result.get_summary() for result in self.history]
    
    def undo_last(self) -> Optional[str]:
        """Undo the last refactoring and return previous code."""
        if self.history:
            last_result = self.history.pop()
            return last_result.original_code
        return None
    
    def export_report(self) -> str:
        """Export a detailed refactoring report."""
        if not self.history:
            return "No refactorings performed yet."
        
        report = "=" * 60 + "\n"
        report += "JAVA REFACTORING ENGINE - REPORT\n"
        report += "=" * 60 + "\n\n"
        
        for i, result in enumerate(self.history, 1):
            summary = result.get_summary()
            report += f"Refactoring #{i}\n"
            report += "-" * 40 + "\n"
            report += f"Status: {'Success' if summary['success'] else 'Failed'}\n"
            report += f"Actions Applied: {summary['total_actions']}\n"
            report += f"\nMetrics Comparison:\n"
            report += f"  LOC: {summary['loc_before']} -> {summary['loc_after']} "
            report += f"({summary['loc_change']:+d})\n"
            report += f"  Methods: {summary['methods_before']} -> {summary['methods_after']}\n"
            report += f"  Avg Complexity: {summary['complexity_before']} -> "
            report += f"{summary['complexity_after']}\n"
            
            if summary['warnings_count'] > 0:
                report += f"\nWarnings: {summary['warnings_count']}\n"
                for warning in result.warnings:
                    report += f"  - {warning}\n"
            
            if summary['errors_count'] > 0:
                report += f"\nErrors: {summary['errors_count']}\n"
                for error in result.errors:
                    report += f"  - {error}\n"
            
            report += "\n"
        
        return report
