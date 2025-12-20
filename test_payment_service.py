"""
Test script for analyzing PaymentService.java with the Refactoring Engine
"""

from java_refactoring_engine.ast_parser import JavaASTParser
from java_refactoring_engine.refactoring_engine import JavaRefactoringEngine

# Load and parse PaymentService.java
parser = JavaASTParser(r'sample_java_files/PaymentService.java')
parser.load_file()
parser.build_ast()
result = parser.extract_all()

print('='*60)
print('JAVA REFACTORING ENGINE - ANALYSIS REPORT')
print('='*60)
print('File: PaymentService.java')
print('-'*60)

print('\n[1] STRUCTURE ANALYSIS')
print('-'*40)
for cls in result['classes']:
    print(f"  Class: {cls['name']}")
    print(f"    Methods: {len(cls['methods'])}")
    print(f"    Fields: {len(cls['fields'])}")
    for m in cls['methods']:
        print(f"      - {m['name']}() | Lines: {m['body_lines']} | Complexity: {m['complexity']}")

print('\n[2] METRICS')
print('-'*40)
m = result['metrics']
print(f"  Total Lines: {m['total_lines']}")
print(f"  Code Lines: {m['code_lines']}")
print(f"  Comment Lines: {m['comment_lines']}")
print(f"  Total Methods: {m['total_methods']}")
print(f"  Avg Complexity: {m['avg_complexity']}")
print(f"  Max Complexity: {m['max_complexity']}")
print(f"  Long Methods (>20 lines): {m['long_methods']}")

# Analyze with refactoring engine
engine = JavaRefactoringEngine()
analysis = engine.analyze_code(parser.code)

print('\n[3] CODE SMELLS DETECTED')
print('-'*40)
for smell in analysis['code_smells']:
    print(f"  [{smell['severity'].upper()}] {smell['type']}")
    if 'class' in smell:
        print(f"    Class: {smell['class']}")
    if 'method' in smell:
        print(f"    Method: {smell['method']}")
    print(f"    {smell['description']}")
    print()

print('\n[4] REFACTORING OPPORTUNITIES')
print('-'*40)
for opp in analysis['refactoring_opportunities']:
    print(f"  Type: {opp['type']}")
    if 'class' in opp:
        print(f"    Class: {opp['class']}")
    if 'method' in opp:
        print(f"    Method: {opp['method']}")
    if 'description' in opp:
        print(f"    {opp['description']}")
    if 'recommendation' in opp:
        print(f"    Suggestion: {opp['recommendation']}")
    print()

print('='*60)
print('Analysis Complete!')
print('='*60)
