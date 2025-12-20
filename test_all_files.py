"""
Comprehensive Test Script - Java Refactoring Engine
====================================================
Tests all sample Java files and shows unique analysis for each file.
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from java_refactoring_engine.ast_parser import JavaASTParser
from java_refactoring_engine.refactoring_engine import (
    JavaRefactoringEngine,
    DuplicateDetector,
    MethodExtractor,
    ConditionalReducer,
    ClassSplitter
)
from java_refactoring_engine.metrics import MetricsCollector


def analyze_file(file_path: str, file_name: str):
    """Analyze a single Java file and display comprehensive results."""
    
    print("\n" + "=" * 80)
    print(f"ANALYZING: {file_name}")
    print("=" * 80)
    
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Initialize components
    parser = JavaASTParser()
    engine = JavaRefactoringEngine()
    duplicate_detector = DuplicateDetector(similarity_threshold=0.7)
    conditional_reducer = ConditionalReducer(max_nesting=3)
    class_splitter = ClassSplitter(max_lines=200, max_methods=15)
    
    # Parse and extract structure
    parser.load_code(code)
    if not parser.build_ast():
        print(f"  ERROR: Failed to parse {file_name}")
        return None
    
    structure = parser.extract_all()
    
    # ============= SECTION 1: FILE STRUCTURE =============
    print("\n" + "-" * 40)
    print("1. FILE STRUCTURE")
    print("-" * 40)
    
    total_methods = 0
    total_fields = 0
    total_complexity = 0
    
    for cls in structure.get('classes', []):
        print(f"\n  CLASS: {cls['name']}")
        print(f"    Lines: {cls.get('total_lines', 0)}")
        print(f"    Extends: {cls.get('extends', 'None')}")
        print(f"    Implements: {', '.join(cls.get('implements', [])) or 'None'}")
        
        # Methods
        methods = cls.get('methods', [])
        total_methods += len(methods)
        print(f"    Methods ({len(methods)}):")
        for method in methods:
            complexity = method.get('complexity', 1)
            total_complexity += complexity
            params = ', '.join([p.get('type', '?') + ' ' + p.get('name', '?') 
                              for p in method.get('parameters', [])])
            print(f"      - {method['name']}({params})")
            print(f"        Return: {method.get('return_type', 'void')}, "
                  f"Lines: {method.get('total_lines', 0)}, "
                  f"Complexity: {complexity}")
        
        # Fields
        fields = cls.get('fields', [])
        total_fields += len(fields)
        if fields:
            print(f"    Fields ({len(fields)}):")
            for field in fields:
                print(f"      - {field.get('type', '?')} {field['name']}")
    
    # ============= SECTION 2: CODE METRICS =============
    print("\n" + "-" * 40)
    print("2. CODE METRICS")
    print("-" * 40)
    
    metrics = parser.metrics
    print(f"  Total Lines: {metrics.total_lines}")
    print(f"  Code Lines (LOC): {metrics.code_lines}")
    print(f"  Comment Lines: {metrics.comment_lines}")
    print(f"  Blank Lines: {metrics.blank_lines}")
    print(f"  Total Classes: {metrics.total_classes}")
    print(f"  Total Methods: {metrics.total_methods}")
    print(f"  Total Fields: {metrics.total_fields}")
    print(f"  Max Complexity: {metrics.max_complexity}")
    print(f"  Avg Complexity: {metrics.avg_complexity:.2f}")
    
    # Code to comment ratio
    if metrics.code_lines > 0:
        comment_ratio = (metrics.comment_lines / metrics.code_lines) * 100
        print(f"  Comment Ratio: {comment_ratio:.1f}%")
    
    # ============= SECTION 3: CODE SMELLS =============
    print("\n" + "-" * 40)
    print("3. CODE SMELLS DETECTED")
    print("-" * 40)
    
    code_smells = []
    
    # Long methods (> 30 lines)
    for cls in structure.get('classes', []):
        for method in cls.get('methods', []):
            lines = method.get('total_lines', 0)
            if lines > 30:
                smell = {
                    'type': 'Long Method',
                    'severity': 'High' if lines > 50 else 'Medium',
                    'location': f"{cls['name']}.{method['name']}()",
                    'detail': f"{lines} lines (recommended: <30)"
                }
                code_smells.append(smell)
    
    # High complexity methods (> 10)
    for cls in structure.get('classes', []):
        for method in cls.get('methods', []):
            complexity = method.get('complexity', 1)
            if complexity > 10:
                smell = {
                    'type': 'High Complexity',
                    'severity': 'High' if complexity > 15 else 'Medium',
                    'location': f"{cls['name']}.{method['name']}()",
                    'detail': f"Cyclomatic complexity: {complexity} (recommended: <10)"
                }
                code_smells.append(smell)
    
    # Large classes (> 200 lines)
    for cls in structure.get('classes', []):
        lines = cls.get('total_lines', 0)
        if lines > 200:
            smell = {
                'type': 'Large Class',
                'severity': 'High' if lines > 300 else 'Medium',
                'location': cls['name'],
                'detail': f"{lines} lines (recommended: <200)"
            }
            code_smells.append(smell)
    
    # Too many methods in a class (> 15)
    for cls in structure.get('classes', []):
        method_count = len(cls.get('methods', []))
        if method_count > 15:
            smell = {
                'type': 'God Class (too many methods)',
                'severity': 'High' if method_count > 20 else 'Medium',
                'location': cls['name'],
                'detail': f"{method_count} methods (recommended: <15)"
            }
            code_smells.append(smell)
    
    # Analyze conditionals for each method
    for cls in structure.get('classes', []):
        for method in cls.get('methods', []):
            start = method.get('start_line', 0)
            end = method.get('end_line', start + 10)
            method_code = '\n'.join(code.split('\n')[start-1:end])
            
            # Count nested if statements
            if_count = method_code.count('if (')
            else_if_count = method_code.count('else if')
            switch_count = method_code.count('switch (')
            
            if if_count + else_if_count > 5:
                smell = {
                    'type': 'Complex Conditional',
                    'severity': 'Medium',
                    'location': f"{cls['name']}.{method['name']}()",
                    'detail': f"{if_count} if statements, {else_if_count} else-if branches"
                }
                code_smells.append(smell)
            
            if switch_count > 0:
                # Check case count
                case_count = method_code.count('case ')
                if case_count > 4:
                    smell = {
                        'type': 'Switch Statement (consider polymorphism)',
                        'severity': 'Low' if case_count < 7 else 'Medium',
                        'location': f"{cls['name']}.{method['name']}()",
                        'detail': f"Switch with {case_count} cases"
                    }
                    code_smells.append(smell)
    
    # Check for duplicate code patterns
    lines = code.split('\n')
    for i in range(len(lines) - 5):
        block1 = '\n'.join(lines[i:i+5])
        for j in range(i + 5, len(lines) - 5):
            block2 = '\n'.join(lines[j:j+5])
            # Simple similarity check
            if len(block1.strip()) > 30 and len(block2.strip()) > 30:
                similarity = len(set(block1.split()) & set(block2.split())) / max(len(block1.split()), 1)
                if similarity > 0.8:
                    smell = {
                        'type': 'Duplicate Code',
                        'severity': 'Medium',
                        'location': f"Lines {i+1}-{i+5} and {j+1}-{j+5}",
                        'detail': f"Similar code blocks detected ({similarity*100:.0f}% similarity)"
                    }
                    code_smells.append(smell)
                    break  # Only report once per block
    
    if code_smells:
        for i, smell in enumerate(code_smells, 1):
            print(f"\n  [{i}] {smell['type']} ({smell['severity']})")
            print(f"      Location: {smell['location']}")
            print(f"      Details: {smell['detail']}")
    else:
        print("  No significant code smells detected.")
    
    # ============= SECTION 4: REFACTORING SUGGESTIONS =============
    print("\n" + "-" * 40)
    print("4. REFACTORING SUGGESTIONS")
    print("-" * 40)
    
    suggestions = []
    
    # Based on code smells, generate suggestions
    for smell in code_smells:
        if smell['type'] == 'Long Method':
            suggestions.append({
                'action': 'Extract Method',
                'target': smell['location'],
                'reason': f"Method too long ({smell['detail']})",
                'benefit': 'Improved readability, testability, and reusability',
                'priority': 'High' if smell['severity'] == 'High' else 'Medium'
            })
        
        elif smell['type'] == 'High Complexity':
            suggestions.append({
                'action': 'Decompose Conditional / Extract Methods',
                'target': smell['location'],
                'reason': f"High cyclomatic complexity ({smell['detail']})",
                'benefit': 'Reduced cognitive load, easier testing',
                'priority': 'High'
            })
        
        elif smell['type'] == 'Large Class':
            suggestions.append({
                'action': 'Split Class (Single Responsibility)',
                'target': smell['location'],
                'reason': f"Class too large ({smell['detail']})",
                'benefit': 'Better separation of concerns, easier maintenance',
                'priority': 'High'
            })
        
        elif smell['type'] == 'God Class (too many methods)':
            suggestions.append({
                'action': 'Extract Class',
                'target': smell['location'],
                'reason': f"Too many methods ({smell['detail']})",
                'benefit': 'Single Responsibility Principle compliance',
                'priority': 'High'
            })
        
        elif smell['type'] == 'Switch Statement (consider polymorphism)':
            suggestions.append({
                'action': 'Replace Conditional with Polymorphism',
                'target': smell['location'],
                'reason': smell['detail'],
                'benefit': 'Open/Closed principle, easier extension',
                'priority': 'Medium'
            })
        
        elif smell['type'] == 'Complex Conditional':
            suggestions.append({
                'action': 'Apply Guard Clauses / Simplify Conditionals',
                'target': smell['location'],
                'reason': smell['detail'],
                'benefit': 'Reduced nesting, clearer logic flow',
                'priority': 'Medium'
            })
        
        elif smell['type'] == 'Duplicate Code':
            suggestions.append({
                'action': 'Extract Common Method (Rule of Three)',
                'target': smell['location'],
                'reason': smell['detail'],
                'benefit': 'DRY principle, single point of change',
                'priority': 'Medium'
            })
    
    # Additional analysis-based suggestions
    for cls in structure.get('classes', []):
        # Check method naming conventions
        for method in cls.get('methods', []):
            name = method['name']
            if name[0].isupper():
                suggestions.append({
                    'action': 'Rename Method (camelCase)',
                    'target': f"{cls['name']}.{name}()",
                    'reason': 'Method name starts with uppercase',
                    'benefit': 'Java naming convention compliance',
                    'priority': 'Low'
                })
    
    if suggestions:
        for i, sugg in enumerate(suggestions, 1):
            print(f"\n  [{i}] {sugg['action']} (Priority: {sugg['priority']})")
            print(f"      Target: {sugg['target']}")
            print(f"      Reason: {sugg['reason']}")
            print(f"      Benefit: {sugg['benefit']}")
    else:
        print("  Code quality is good. Minor improvements may be possible.")
    
    # ============= SECTION 5: CLASS SPLITTING ANALYSIS =============
    print("\n" + "-" * 40)
    print("5. CLASS SPLITTING ANALYSIS")
    print("-" * 40)
    
    for cls in structure.get('classes', []):
        methods = cls.get('methods', [])
        
        # Group methods by prefix
        method_groups = {}
        for method in methods:
            name = method['name']
            # Determine group based on prefix
            prefixes = ['get', 'set', 'is', 'has', 'find', 'search', 'load', 'save', 
                       'read', 'write', 'update', 'delete', 'validate', 'check',
                       'calculate', 'compute', 'process', 'handle', 'on', 'render',
                       'display', 'format', 'parse', 'convert', 'transform']
            
            group = 'Core'
            name_lower = name.lower()
            for prefix in prefixes:
                if name_lower.startswith(prefix):
                    if prefix in ['get', 'set', 'is', 'has']:
                        group = 'Accessor/Mutator'
                    elif prefix in ['find', 'search']:
                        group = 'Query'
                    elif prefix in ['load', 'save', 'read', 'write', 'update', 'delete']:
                        group = 'DataAccess'
                    elif prefix in ['validate', 'check']:
                        group = 'Validation'
                    elif prefix in ['calculate', 'compute']:
                        group = 'Calculation'
                    elif prefix in ['process']:
                        group = 'Processing'
                    elif prefix in ['handle', 'on']:
                        group = 'EventHandler'
                    elif prefix in ['render', 'display', 'format']:
                        group = 'Presentation'
                    elif prefix in ['parse', 'convert', 'transform']:
                        group = 'Transformation'
                    break
            
            if group not in method_groups:
                method_groups[group] = []
            method_groups[group].append(name)
        
        print(f"\n  Class: {cls['name']}")
        print(f"    Detected Responsibilities: {len(method_groups)}")
        
        for group, group_methods in method_groups.items():
            if len(group_methods) >= 2:
                print(f"\n    {group} ({len(group_methods)} methods):")
                for m in group_methods:
                    print(f"      - {m}()")
        
        if len(method_groups) > 3:
            print(f"\n    SUGGESTION: Consider splitting {cls['name']} into:")
            for group in method_groups.keys():
                if group != 'Core' and group != 'Accessor/Mutator':
                    print(f"      - {cls['name']}{group}")
    
    # ============= SECTION 6: SUMMARY =============
    print("\n" + "-" * 40)
    print("6. ANALYSIS SUMMARY")
    print("-" * 40)
    
    # Calculate quality score (0-100)
    quality_score = 100
    
    # Deductions
    for smell in code_smells:
        if smell['severity'] == 'High':
            quality_score -= 15
        elif smell['severity'] == 'Medium':
            quality_score -= 8
        else:
            quality_score -= 3
    
    # Bonus for good practices
    if metrics.comment_lines > metrics.code_lines * 0.1:
        quality_score += 5  # Good commenting
    
    quality_score = max(0, min(100, quality_score))
    
    quality_label = 'Excellent' if quality_score >= 90 else \
                   'Good' if quality_score >= 75 else \
                   'Fair' if quality_score >= 60 else \
                   'Needs Improvement' if quality_score >= 40 else 'Poor'
    
    print(f"\n  Code Quality Score: {quality_score}/100 ({quality_label})")
    print(f"  Total Code Smells: {len(code_smells)}")
    print(f"  Refactoring Suggestions: {len(suggestions)}")
    
    # Priority breakdown
    high_priority = len([s for s in suggestions if s['priority'] == 'High'])
    medium_priority = len([s for s in suggestions if s['priority'] == 'Medium'])
    low_priority = len([s for s in suggestions if s['priority'] == 'Low'])
    
    print(f"  Priority Breakdown: {high_priority} High, {medium_priority} Medium, {low_priority} Low")
    
    return {
        'file': file_name,
        'metrics': metrics.to_dict(),
        'code_smells': len(code_smells),
        'suggestions': len(suggestions),
        'quality_score': quality_score
    }


def main():
    """Main entry point."""
    print("\n" + "=" * 80)
    print("JAVA REFACTORING ENGINE - COMPREHENSIVE FILE ANALYSIS")
    print("=" * 80)
    
    # Find all Java files
    sample_dir = Path(__file__).parent / 'sample_java_files'
    
    if not sample_dir.exists():
        print(f"ERROR: Sample directory not found: {sample_dir}")
        return
    
    java_files = list(sample_dir.glob('*.java'))
    
    if not java_files:
        print("ERROR: No Java files found in sample_java_files directory")
        return
    
    print(f"\nFound {len(java_files)} Java file(s) to analyze:")
    for f in java_files:
        print(f"  - {f.name}")
    
    # Analyze each file
    results = []
    for java_file in sorted(java_files):
        result = analyze_file(str(java_file), java_file.name)
        if result:
            results.append(result)
    
    # Final comparison
    if len(results) > 1:
        print("\n" + "=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)
        
        print(f"\n{'File':<35} {'LOC':>8} {'Methods':>10} {'Smells':>10} {'Score':>10}")
        print("-" * 75)
        
        for r in results:
            print(f"{r['file']:<35} {r['metrics']['code_lines']:>8} "
                  f"{r['metrics']['total_methods']:>10} {r['code_smells']:>10} "
                  f"{r['quality_score']:>9}/100")
        
        # Best and worst
        best = max(results, key=lambda x: x['quality_score'])
        worst = min(results, key=lambda x: x['quality_score'])
        
        print(f"\nBest Quality: {best['file']} (Score: {best['quality_score']}/100)")
        print(f"Needs Work:   {worst['file']} (Score: {worst['quality_score']}/100)")


if __name__ == '__main__':
    main()
