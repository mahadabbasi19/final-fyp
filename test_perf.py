"""Performance test for refactoring engine"""
import time
import sys

# Force fresh import
for mod in list(sys.modules.keys()):
    if 'refactoring' in mod or 'java_' in mod:
        del sys.modules[mod]

print('Testing performance...')

# Load the code
with open('sample_java_files/OrderProcessingService.java', 'r', encoding='utf-8') as f:
    code = f.read()
print(f'File loaded: {len(code)} chars, {len(code.splitlines())} lines')

print('Importing JavaRefactoringEngine...')
from java_refactoring_engine.refactoring_engine import JavaRefactoringEngine
print('Creating instance...')
engine = JavaRefactoringEngine()

print('Testing engine.refactor() with decompose_behavior...')
start = time.time()
result = engine.refactor(code, selected_refactorings=['decompose_behavior'])
elapsed = time.time()-start
print(f'engine.refactor (decompose_behavior): {elapsed:.2f}s')

if elapsed < 3:
    print('SUCCESS - Performance is acceptable!')
else:
    print('WARNING - Still too slow!')

print('Done!')
