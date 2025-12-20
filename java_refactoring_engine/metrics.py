"""
Metrics and Visualization Module
================================
Provides code quality metrics collection and visualization capabilities.
Includes charts, statistics, and comparative analysis.
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict


@dataclass
class MetricsSnapshot:
    """Stores a snapshot of metrics at a specific point in time."""
    timestamp: str
    file_path: Optional[str]
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    total_classes: int
    total_methods: int
    total_fields: int
    avg_method_length: float
    max_method_length: int
    avg_complexity: float
    max_complexity: int
    long_methods: int
    large_classes: int
    duplicate_blocks: int
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MetricsSnapshot':
        return cls(**data)


@dataclass
class RefactoringStats:
    """Statistics about refactoring operations."""
    total_refactorings: int = 0
    methods_extracted: int = 0
    classes_split: int = 0
    duplicates_removed: int = 0
    conditionals_simplified: int = 0
    nesting_reduced: int = 0
    loc_reduced: int = 0
    complexity_reduced: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class MetricsCollector:
    """
    Collects and manages code quality metrics over time.
    Provides comparison and trend analysis.
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.snapshots: List[MetricsSnapshot] = []
        self.stats = RefactoringStats()
        self.file_metrics: Dict[str, List[MetricsSnapshot]] = defaultdict(list)
    
    def create_snapshot(self, metrics: Dict, 
                        file_path: Optional[str] = None) -> MetricsSnapshot:
        """
        Create a metrics snapshot from a metrics dictionary.
        
        Args:
            metrics: Dictionary containing metrics data
            file_path: Optional path to the source file
            
        Returns:
            MetricsSnapshot object
        """
        snapshot = MetricsSnapshot(
            timestamp=datetime.now().isoformat(),
            file_path=file_path,
            total_lines=metrics.get('total_lines', 0),
            code_lines=metrics.get('code_lines', 0),
            comment_lines=metrics.get('comment_lines', 0),
            blank_lines=metrics.get('blank_lines', 0),
            total_classes=metrics.get('total_classes', 0),
            total_methods=metrics.get('total_methods', 0),
            total_fields=metrics.get('total_fields', 0),
            avg_method_length=metrics.get('avg_method_length', 0.0),
            max_method_length=metrics.get('max_method_length', 0),
            avg_complexity=metrics.get('avg_complexity', 0.0),
            max_complexity=metrics.get('max_complexity', 0),
            long_methods=metrics.get('long_methods', 0),
            large_classes=metrics.get('large_classes', 0),
            duplicate_blocks=metrics.get('duplicate_blocks', 0)
        )
        
        self.snapshots.append(snapshot)
        
        if file_path:
            self.file_metrics[file_path].append(snapshot)
        
        return snapshot
    
    def get_latest_snapshot(self, file_path: Optional[str] = None) -> Optional[MetricsSnapshot]:
        """
        Get the most recent metrics snapshot.
        
        Args:
            file_path: Optional file path to filter by
            
        Returns:
            Latest MetricsSnapshot or None
        """
        if file_path and file_path in self.file_metrics:
            if self.file_metrics[file_path]:
                return self.file_metrics[file_path][-1]
        elif self.snapshots:
            return self.snapshots[-1]
        return None
    
    def compare_snapshots(self, before: MetricsSnapshot, 
                          after: MetricsSnapshot) -> Dict[str, Any]:
        """
        Compare two metrics snapshots.
        
        Args:
            before: Earlier snapshot
            after: Later snapshot
            
        Returns:
            Dictionary with comparison results
        """
        return {
            'loc_change': after.code_lines - before.code_lines,
            'loc_percent_change': self._percent_change(before.code_lines, after.code_lines),
            'methods_change': after.total_methods - before.total_methods,
            'classes_change': after.total_classes - before.total_classes,
            'complexity_change': after.avg_complexity - before.avg_complexity,
            'complexity_percent_change': self._percent_change(
                before.avg_complexity, after.avg_complexity
            ),
            'long_methods_change': after.long_methods - before.long_methods,
            'large_classes_change': after.large_classes - before.large_classes,
            'improvement_score': self._calculate_improvement_score(before, after)
        }
    
    def _percent_change(self, before: float, after: float) -> float:
        """Calculate percentage change between two values."""
        if before == 0:
            return 0.0 if after == 0 else 100.0
        return round(((after - before) / before) * 100, 2)
    
    def _calculate_improvement_score(self, before: MetricsSnapshot, 
                                     after: MetricsSnapshot) -> float:
        """
        Calculate an overall improvement score (0-100).
        Higher is better.
        """
        score = 50.0  # Start at neutral
        
        # LOC reduction is good (up to +20 points)
        if before.code_lines > 0:
            loc_improvement = ((before.code_lines - after.code_lines) / 
                              before.code_lines * 100)
            score += min(loc_improvement * 2, 20)
        
        # Complexity reduction is good (up to +20 points)
        if before.avg_complexity > 0:
            complexity_improvement = ((before.avg_complexity - after.avg_complexity) / 
                                     before.avg_complexity * 100)
            score += min(complexity_improvement * 2, 20)
        
        # Reducing long methods is good (up to +10 points)
        long_method_reduction = before.long_methods - after.long_methods
        score += min(long_method_reduction * 2, 10)
        
        # Reducing large classes is good (up to +10 points)
        large_class_reduction = before.large_classes - after.large_classes
        score += min(large_class_reduction * 5, 10)
        
        return max(0, min(100, round(score, 1)))
    
    def update_stats(self, action_type: str, count: int = 1, 
                     loc_change: int = 0, complexity_change: float = 0.0):
        """
        Update refactoring statistics.
        
        Args:
            action_type: Type of refactoring action
            count: Number of times the action was performed
            loc_change: Change in lines of code
            complexity_change: Change in complexity
        """
        self.stats.total_refactorings += count
        
        if action_type == 'extract_method':
            self.stats.methods_extracted += count
        elif action_type == 'split_class':
            self.stats.classes_split += count
        elif action_type == 'remove_duplicate':
            self.stats.duplicates_removed += count
        elif action_type == 'simplify_conditional':
            self.stats.conditionals_simplified += count
        elif action_type == 'reduce_nesting':
            self.stats.nesting_reduced += count
        
        if loc_change < 0:
            self.stats.loc_reduced += abs(loc_change)
        if complexity_change < 0:
            self.stats.complexity_reduced += abs(complexity_change)
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get a summary of all refactoring statistics."""
        return {
            'stats': self.stats.to_dict(),
            'total_snapshots': len(self.snapshots),
            'files_analyzed': len(self.file_metrics),
            'latest_metrics': self.get_latest_snapshot().to_dict() if self.snapshots else None
        }
    
    def get_trend_data(self, metric_name: str, 
                       file_path: Optional[str] = None) -> List[Dict]:
        """
        Get trend data for a specific metric.
        
        Args:
            metric_name: Name of the metric (e.g., 'code_lines', 'avg_complexity')
            file_path: Optional file path to filter by
            
        Returns:
            List of data points with timestamp and value
        """
        snapshots = (self.file_metrics.get(file_path, []) if file_path 
                    else self.snapshots)
        
        return [
            {
                'timestamp': s.timestamp,
                'value': getattr(s, metric_name, None)
            }
            for s in snapshots
            if hasattr(s, metric_name)
        ]
    
    def export_metrics(self) -> str:
        """Export all metrics as JSON string."""
        data = {
            'snapshots': [s.to_dict() for s in self.snapshots],
            'stats': self.stats.to_dict(),
            'file_metrics': {
                path: [s.to_dict() for s in snapshots]
                for path, snapshots in self.file_metrics.items()
            }
        }
        return json.dumps(data, indent=2)
    
    def import_metrics(self, json_str: str):
        """Import metrics from JSON string."""
        data = json.loads(json_str)
        
        self.snapshots = [
            MetricsSnapshot.from_dict(s) for s in data.get('snapshots', [])
        ]
        
        stats_data = data.get('stats', {})
        self.stats = RefactoringStats(**stats_data)
        
        self.file_metrics = defaultdict(list)
        for path, snapshots in data.get('file_metrics', {}).items():
            self.file_metrics[path] = [
                MetricsSnapshot.from_dict(s) for s in snapshots
            ]


class MetricsVisualizer:
    """
    Creates text-based visualizations for metrics.
    Can be used in terminal or GUI console.
    """
    
    @staticmethod
    def create_bar_chart(data: Dict[str, float], 
                         width: int = 50, 
                         title: str = "") -> str:
        """
        Create a horizontal bar chart.
        
        Args:
            data: Dictionary mapping labels to values
            width: Maximum bar width in characters
            title: Chart title
            
        Returns:
            String representation of the bar chart
        """
        if not data:
            return "No data to display"
        
        max_value = max(data.values()) if data.values() else 1
        max_label_len = max(len(str(k)) for k in data.keys())
        
        lines = []
        if title:
            lines.append(f"\n{title}")
            lines.append("=" * (width + max_label_len + 10))
        
        for label, value in data.items():
            bar_length = int((value / max_value) * width) if max_value > 0 else 0
            bar = "█" * bar_length
            lines.append(f"{label:>{max_label_len}} │ {bar} {value:.1f}")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_comparison_chart(before: Dict[str, float], 
                                after: Dict[str, float],
                                title: str = "Before vs After") -> str:
        """
        Create a comparison chart showing before and after values.
        
        Args:
            before: Before metrics
            after: After metrics
            title: Chart title
            
        Returns:
            String representation of the comparison chart
        """
        lines = [f"\n{title}", "=" * 60]
        
        all_keys = set(before.keys()) | set(after.keys())
        max_label_len = max(len(str(k)) for k in all_keys) if all_keys else 10
        
        lines.append(f"{'Metric':<{max_label_len}} │ {'Before':>10} │ {'After':>10} │ {'Change':>10}")
        lines.append("-" * 60)
        
        for key in sorted(all_keys):
            b_val = before.get(key, 0)
            a_val = after.get(key, 0)
            change = a_val - b_val
            change_str = f"{change:+.1f}" if isinstance(change, float) else f"{change:+d}"
            
            # Add color indicator
            indicator = "↓" if change < 0 else "↑" if change > 0 else "="
            
            lines.append(
                f"{key:<{max_label_len}} │ {b_val:>10.1f} │ {a_val:>10.1f} │ {change_str:>8} {indicator}"
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def create_summary_box(metrics: Dict[str, Any], title: str = "Metrics Summary") -> str:
        """
        Create a summary box with key metrics.
        
        Args:
            metrics: Dictionary of metrics
            title: Box title
            
        Returns:
            Formatted summary string
        """
        width = 50
        lines = []
        
        lines.append("┌" + "─" * (width - 2) + "┐")
        lines.append("│" + title.center(width - 2) + "│")
        lines.append("├" + "─" * (width - 2) + "┤")
        
        for key, value in metrics.items():
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)
            
            label = key.replace('_', ' ').title()
            content = f" {label}: {value_str}"
            lines.append("│" + content.ljust(width - 2) + "│")
        
        lines.append("└" + "─" * (width - 2) + "┘")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_progress_bar(current: float, total: float, 
                            width: int = 40, label: str = "") -> str:
        """
        Create a progress bar.
        
        Args:
            current: Current value
            total: Total value
            width: Bar width in characters
            label: Optional label
            
        Returns:
            Progress bar string
        """
        if total == 0:
            percent = 0
        else:
            percent = min(100, (current / total) * 100)
        
        filled = int(width * percent / 100)
        empty = width - filled
        
        bar = "█" * filled + "░" * empty
        percent_str = f"{percent:5.1f}%"
        
        if label:
            return f"{label}: [{bar}] {percent_str}"
        return f"[{bar}] {percent_str}"
    
    @staticmethod
    def create_code_smell_report(smells: List[Dict]) -> str:
        """
        Create a formatted report of code smells.
        
        Args:
            smells: List of code smell dictionaries
            
        Returns:
            Formatted report string
        """
        if not smells:
            return "✓ No code smells detected!"
        
        lines = ["\n⚠ CODE SMELLS DETECTED", "=" * 50]
        
        # Group by severity
        by_severity = {'high': [], 'medium': [], 'low': []}
        for smell in smells:
            severity = smell.get('severity', 'medium')
            by_severity.setdefault(severity, []).append(smell)
        
        severity_icons = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
        
        for severity in ['high', 'medium', 'low']:
            if by_severity[severity]:
                lines.append(f"\n{severity_icons[severity]} {severity.upper()} SEVERITY:")
                for smell in by_severity[severity]:
                    lines.append(f"  • [{smell['type']}]")
                    if 'class' in smell:
                        lines.append(f"    Class: {smell['class']}")
                    if 'method' in smell:
                        lines.append(f"    Method: {smell['method']}")
                    lines.append(f"    {smell['description']}")
        
        lines.append("\n" + "=" * 50)
        lines.append(f"Total: {len(smells)} code smell(s) found")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_refactoring_suggestions(opportunities: List[Dict]) -> str:
        """
        Create a formatted list of refactoring suggestions.
        
        Args:
            opportunities: List of refactoring opportunity dictionaries
            
        Returns:
            Formatted suggestions string
        """
        if not opportunities:
            return "✓ Code looks good! No immediate refactoring needed."
        
        lines = ["\n💡 REFACTORING SUGGESTIONS", "=" * 50]
        
        # Group by type
        by_type = defaultdict(list)
        for opp in opportunities:
            by_type[opp['type']].append(opp)
        
        for ref_type, opps in by_type.items():
            lines.append(f"\n📌 {ref_type}:")
            for i, opp in enumerate(opps, 1):
                lines.append(f"  {i}. ", end="")
                if 'class' in opp:
                    lines[-1] += f"Class '{opp['class']}'"
                if 'method' in opp:
                    lines[-1] += f" → Method '{opp['method']}'"
                if 'description' in opp:
                    lines.append(f"     {opp['description']}")
                if 'recommendation' in opp:
                    lines.append(f"     💬 {opp['recommendation']}")
        
        return "\n".join(lines)


class CouplingCohesionCalculator:
    """
    Calculates Coupling and Cohesion metrics for Java code.
    
    COUPLING TYPES (Kent Beck):
    - Afferent Coupling (Ca): Number of classes that depend on this class
    - Efferent Coupling (Ce): Number of classes this class depends on
    - Instability: Ce / (Ca + Ce) - 0 = stable, 1 = unstable
    
    COHESION TYPES:
    - LCOM (Lack of Cohesion in Methods): Lower is better
    - Method-Field Access: How many methods use each field
    
    DESIGN PRINCIPLES:
    - High Cohesion: Methods within a class work together closely
    - Low Coupling: Classes have minimal dependencies on each other
    """
    
    @staticmethod
    def calculate_coupling(code: str) -> Dict[str, Any]:
        """
        Calculate coupling metrics for Java code.
        
        Args:
            code: Java source code
            
        Returns:
            Dictionary with coupling metrics
        """
        import re
        
        # Find class name
        class_match = re.search(r'class\s+(\w+)', code)
        class_name = class_match.group(1) if class_match else 'Unknown'
        
        # Find imports (external dependencies)
        imports = re.findall(r'import\s+([\w.]+);', code)
        external_imports = [i for i in imports if not i.startswith('java.')]
        java_imports = [i for i in imports if i.startswith('java.')]
        
        # Primitive types to exclude
        primitives = {'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short', 'void', 'String'}
        
        # Find field type dependencies (various patterns)
        field_patterns = [
            r'private\s+(\w+)(?:<[^>]*>)?\s+\w+\s*[;=]',  # private Type field; or private Type field =
            r'protected\s+(\w+)(?:<[^>]*>)?\s+\w+\s*[;=]',
            r'public\s+(\w+)(?:<[^>]*>)?\s+\w+\s*[;=]',
            r'private\s+final\s+(\w+)(?:<[^>]*>)?\s+\w+\s*[;=]',
            r'public\s+final\s+(\w+)(?:<[^>]*>)?\s+\w+\s*[;=]',
        ]
        
        field_types = []
        for pattern in field_patterns:
            field_types.extend(re.findall(pattern, code))
        
        # Filter out primitives but KEEP collection types (List, Map, Set, etc.)
        java_collections = {'List', 'Map', 'Set', 'ArrayList', 'HashMap', 'HashSet', 'Collection'}
        custom_field_types = [t for t in field_types if t not in primitives and t[0].isupper() and t not in java_collections]
        
        # Find method parameter types (dependencies through parameters)
        param_types = re.findall(r'\(\s*(\w+)(?:<[^>]*>)?\s+\w+', code)
        custom_param_types = [t for t in param_types if t not in primitives and t[0].isupper() and t not in java_collections]
        
        # Find instantiation dependencies (new ClassName())
        instantiations = re.findall(r'new\s+(\w+)\s*[\(<]', code)
        # Filter out Java collections from instantiations
        custom_instantiations = [i for i in instantiations if i not in java_collections and i not in primitives]
        
        # Find method calls on other objects (object.method()) - identifies field usage
        object_calls = re.findall(r'(\w+)\.(\w+)\(', code)
        # Get unique object names that are likely field references (not this, super, System, etc.)
        exclude_objects = {'this', 'super', 'System', 'Math', 'String', 'Arrays', 'Collections', 'Objects', 'out'}
        
        # Only count objects that match our known field dependency types
        field_names = set()
        field_name_pattern = r'private\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]'
        field_names.update(re.findall(field_name_pattern, code))
        field_name_pattern2 = r'private\s+final\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]'
        field_names.update(re.findall(field_name_pattern2, code))
        
        # Count only calls to known field objects
        external_objects = set()
        for call in object_calls:
            obj_name = call[0]
            if obj_name in field_names and obj_name not in exclude_objects:
                external_objects.add(obj_name)
        
        # Calculate efferent coupling (Ce) - classes this class depends on
        all_dependencies = set(custom_field_types + custom_param_types + custom_instantiations)
        efferent_coupling = len(all_dependencies)
        
        # Count field objects actually used
        coupling_intensity = len(external_objects)
        
        # Coupling score (0-100, HIGHER IS BETTER - means less coupling)
        # Raw coupling = dependencies * 15 + external imports * 5
        # Then INVERT: 100 - raw_coupling = final score
        # So: 0 dependencies = 100 (perfect), 5 dependencies = 25 (bad)
        raw_coupling = min(100, efferent_coupling * 15 + len(external_imports) * 5)
        coupling_score = max(0, 100 - raw_coupling)  # Invert so higher = better
        
        # Level matches score: HIGH score = HIGH level = GOOD
        # This is consistent: HIGH = GOOD for both coupling and cohesion
        # HIGH (>= 70) = Few dependencies = GOOD
        # MEDIUM (40-69) = Some dependencies = OK  
        # LOW (< 40) = Many dependencies = BAD
        if coupling_score >= 70:
            coupling_level = 'HIGH'  # High score = Good (few dependencies)
        elif coupling_score >= 40:
            coupling_level = 'MEDIUM'  # Medium score = OK
        else:
            coupling_level = 'LOW'  # Low score = Bad (many dependencies)
        
        return {
            'class_name': class_name,
            'efferent_coupling': efferent_coupling,
            'import_count': len(imports),
            'external_imports': len(external_imports),
            'java_imports': len(java_imports),
            'field_dependencies': custom_field_types,
            'parameter_dependencies': list(set(custom_param_types)),
            'instantiation_dependencies': list(set(custom_instantiations)),
            'external_method_calls': coupling_intensity,
            'coupling_score': coupling_score,
            'coupling_level': coupling_level,
            'all_dependencies': list(all_dependencies),
            'objects_used': list(external_objects),
        }
    
    @staticmethod
    def calculate_cohesion(code: str) -> Dict[str, Any]:
        """
        Calculate cohesion metrics for Java code using LCOM4 approach.
        
        LCOM (Lack of Cohesion in Methods):
        - Measures how well methods in a class work together
        - Lower LCOM = Higher Cohesion = Better Design
        
        Args:
            code: Java source code
            
        Returns:
            Dictionary with cohesion metrics
        """
        import re
        
        # Find MAIN class name (first public class or first class)
        class_match = re.search(r'public\s+class\s+(\w+)', code)
        if not class_match:
            class_match = re.search(r'class\s+(\w+)', code)
        class_name = class_match.group(1) if class_match else 'Unknown'
        
        # Extract only the main class body (stop at next class declaration)
        main_class_pattern = rf'(public\s+)?class\s+{class_name}\s*[^{{]*\{{'
        main_class_match = re.search(main_class_pattern, code)
        
        if main_class_match:
            # Find the matching closing brace for the main class
            start_pos = main_class_match.end() - 1  # Position of opening brace
            brace_count = 1
            pos = start_pos + 1
            while pos < len(code) and brace_count > 0:
                if code[pos] == '{':
                    brace_count += 1
                elif code[pos] == '}':
                    brace_count -= 1
                pos += 1
            main_class_code = code[start_pos:pos]
        else:
            main_class_code = code
        
        # Find all fields in main class only
        fields = set()
        field_patterns = [
            r'private\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]',
            r'protected\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]',
            r'public\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]',
            r'private\s+final\s+\w+(?:<[^>]*>)?\s+(\w+)\s*[;=]',
        ]
        for pattern in field_patterns:
            fields.update(re.findall(pattern, main_class_code))
        
        # Filter out common non-field names
        fields = {f for f in fields if not f.isupper()}  # Remove constants
        
        # Find all methods in main class and their field usage
        method_pattern = r'(public|private|protected)\s+(?:static\s+)?(\w+)\s+(\w+)\s*\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.findall(method_pattern, main_class_code, re.DOTALL)
        
        # Track which fields each method uses
        method_field_usage = {}
        for modifier, return_type, method_name, method_body in methods:
            # Skip constructors and common utility methods
            if method_name in ['main', 'toString', 'hashCode', 'equals', class_name]:
                continue
            used_fields = set()
            for field in fields:
                if re.search(rf'\b{field}\b', method_body):
                    used_fields.add(field)
            method_field_usage[method_name] = used_fields
        
        # Calculate LCOM (simplified version)
        # LCOM = number of method pairs that don't share fields - pairs that do share
        method_names = list(method_field_usage.keys())
        shared_pairs = 0
        not_shared_pairs = 0
        
        for i in range(len(method_names)):
            for j in range(i + 1, len(method_names)):
                fields_i = method_field_usage[method_names[i]]
                fields_j = method_field_usage[method_names[j]]
                if fields_i & fields_j:  # Intersection
                    shared_pairs += 1
                else:
                    not_shared_pairs += 1
        
        lcom = max(0, not_shared_pairs - shared_pairs)
        
        # Calculate average field usage per method
        total_usage = sum(len(fields) for fields in method_field_usage.values())
        avg_field_usage = total_usage / len(method_field_usage) if method_field_usage else 0
        
        # Calculate cohesion score (0-100, higher is better)
        if len(methods) == 0:
            cohesion_score = 50
        else:
            # Higher shared pairs = higher cohesion
            total_pairs = shared_pairs + not_shared_pairs
            if total_pairs > 0:
                cohesion_ratio = shared_pairs / total_pairs
            else:
                cohesion_ratio = 0.5
            cohesion_score = int(cohesion_ratio * 100)
        
        # Group methods by fields they access (to identify potential class splits)
        field_to_methods = {}
        for method, used_fields in method_field_usage.items():
            for field in used_fields:
                if field not in field_to_methods:
                    field_to_methods[field] = []
                field_to_methods[field].append(method)
        
        # Identify responsibility clusters (methods that work on same fields)
        clusters = []
        processed_methods = set()
        
        for method, fields_used in method_field_usage.items():
            if method in processed_methods:
                continue
            cluster = {method}
            for field in fields_used:
                for other_method in field_to_methods.get(field, []):
                    cluster.add(other_method)
            if len(cluster) > 1:
                clusters.append(list(cluster))
            processed_methods.update(cluster)
        
        return {
            'class_name': class_name,
            'field_count': len(fields),
            'method_count': len(methods),
            'lcom': lcom,
            'shared_method_pairs': shared_pairs,
            'unshared_method_pairs': not_shared_pairs,
            'avg_field_usage_per_method': round(avg_field_usage, 2),
            'cohesion_score': cohesion_score,
            'cohesion_level': 'HIGH' if cohesion_score >= 70 else 'MEDIUM' if cohesion_score >= 40 else 'LOW',
            'fields': list(fields),
            'method_field_usage': {k: list(v) for k, v in method_field_usage.items()},
            'responsibility_clusters': clusters,
            'suggested_class_count': max(1, len(clusters)),
        }
    
    @staticmethod
    def get_improvement_analysis(before_coupling: Dict, after_coupling: Dict,
                                  before_cohesion: Dict, after_cohesion: Dict) -> Dict[str, Any]:
        """
        Analyze improvements in coupling and cohesion after refactoring.
        
        Args:
            before_coupling: Coupling metrics before refactoring
            after_coupling: Coupling metrics after refactoring
            before_cohesion: Cohesion metrics before refactoring
            after_cohesion: Cohesion metrics after refactoring
            
        Returns:
            Analysis of improvements
        """
        coupling_improvement = before_coupling['coupling_score'] - after_coupling['coupling_score']
        cohesion_improvement = after_cohesion['cohesion_score'] - before_cohesion['cohesion_score']
        
        return {
            'coupling_before': before_coupling['coupling_score'],
            'coupling_after': after_coupling['coupling_score'],
            'coupling_improvement': coupling_improvement,
            'coupling_improved': coupling_improvement > 0,
            'cohesion_before': before_cohesion['cohesion_score'],
            'cohesion_after': after_cohesion['cohesion_score'],
            'cohesion_improvement': cohesion_improvement,
            'cohesion_improved': cohesion_improvement > 0,
            'overall_improvement': (coupling_improvement + cohesion_improvement) / 2,
            'quality_improved': coupling_improvement > 0 or cohesion_improvement > 0,
        }


class VisualizationData:
    """
    Prepares data for GUI visualization components.
    """
    
    @staticmethod
    def prepare_pie_chart_data(metrics: Dict) -> List[Dict]:
        """
        Prepare data for a pie chart showing code composition.
        
        Args:
            metrics: Metrics dictionary
            
        Returns:
            List of pie chart segments
        """
        total = metrics.get('total_lines', 1)
        
        return [
            {
                'label': 'Code',
                'value': metrics.get('code_lines', 0),
                'percentage': round(metrics.get('code_lines', 0) / total * 100, 1),
                'color': '#2196F3'
            },
            {
                'label': 'Comments',
                'value': metrics.get('comment_lines', 0),
                'percentage': round(metrics.get('comment_lines', 0) / total * 100, 1),
                'color': '#4CAF50'
            },
            {
                'label': 'Blank',
                'value': metrics.get('blank_lines', 0),
                'percentage': round(metrics.get('blank_lines', 0) / total * 100, 1),
                'color': '#9E9E9E'
            }
        ]
    
    @staticmethod
    def prepare_bar_chart_data(comparison: Dict) -> List[Dict]:
        """
        Prepare data for a bar chart comparing before/after metrics.
        
        Args:
            comparison: Comparison dictionary from MetricsCollector
            
        Returns:
            List of bar chart data points
        """
        metrics = [
            ('LOC', 'loc_change', '#2196F3'),
            ('Methods', 'methods_change', '#4CAF50'),
            ('Classes', 'classes_change', '#FF9800'),
            ('Complexity', 'complexity_change', '#F44336'),
            ('Long Methods', 'long_methods_change', '#9C27B0'),
            ('Large Classes', 'large_classes_change', '#00BCD4')
        ]
        
        return [
            {
                'label': label,
                'value': comparison.get(key, 0),
                'color': color,
                'positive': comparison.get(key, 0) >= 0
            }
            for label, key, color in metrics
        ]
    
    @staticmethod
    def prepare_radar_chart_data(before: Dict, after: Dict) -> Dict:
        """
        Prepare data for a radar chart showing code quality dimensions.
        
        Args:
            before: Before metrics
            after: After metrics
            
        Returns:
            Radar chart data structure
        """
        # Normalize metrics to 0-100 scale
        def normalize(value, max_good, lower_is_better=True):
            if lower_is_better:
                return max(0, min(100, 100 - (value / max_good * 100)))
            return max(0, min(100, value / max_good * 100))
        
        dimensions = [
            'Conciseness',
            'Simplicity',
            'Modularity',
            'Readability',
            'Maintainability'
        ]
        
        before_values = [
            normalize(before.get('code_lines', 100), 500),
            normalize(before.get('avg_complexity', 5), 20),
            normalize(before.get('avg_method_length', 10), 50),
            100 - before.get('long_methods', 0) * 10,
            100 - before.get('large_classes', 0) * 20
        ]
        
        after_values = [
            normalize(after.get('code_lines', 100), 500),
            normalize(after.get('avg_complexity', 5), 20),
            normalize(after.get('avg_method_length', 10), 50),
            100 - after.get('long_methods', 0) * 10,
            100 - after.get('large_classes', 0) * 20
        ]
        
        return {
            'dimensions': dimensions,
            'before': {'values': before_values, 'label': 'Before', 'color': '#FF6B6B'},
            'after': {'values': after_values, 'label': 'After', 'color': '#4ECDC4'}
        }
