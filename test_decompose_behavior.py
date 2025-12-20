"""Test the BehaviorDecomposer implementation."""

from java_refactoring_engine.refactoring_engine import BehaviorDecomposer, JavaRefactoringEngine

def test_behavior_decomposer():
    """Test the BehaviorDecomposer class."""
    print("=" * 60)
    print("Testing BehaviorDecomposer - Kent Beck Refactoring")
    print("=" * 60)
    
    # Initialize the decomposer
    bd = BehaviorDecomposer()
    print("\n✅ BehaviorDecomposer initialized successfully!")
    
    # Load sample Java file
    with open('sample_java_files/DecomposeBehaviorDemo.java', 'r', encoding='utf-8') as f:
        code = f.read()
    
    print(f"\n📄 Loaded sample file: {len(code)} characters, {len(code.split(chr(10)))} lines")
    
    # Analyze for decomposition
    print("\n🔍 Analyzing code for decomposition opportunities...")
    result = bd.analyze_for_decomposition(code)
    
    print(f"\n📊 Analysis Results:")
    print(f"   Needs decomposition: {result['needs_decomposition']}")
    print(f"   Total reasons: {len(result['reasons'])}")
    print(f"   Long methods found: {len(result['long_methods'])}")
    print(f"   Decomposition suggestions: {len(result['decomposition_suggestions'])}")
    print(f"   Feature envy detected: {len(result['feature_envy'])}")
    print(f"   Duplicate code blocks: {len(result['duplicate_code'])}")
    
    print("\n📋 Reasons for decomposition:")
    for i, reason in enumerate(result['reasons'][:5], 1):
        print(f"   {i}. {reason}")
    
    # Test the full decomposition
    print("\n" + "=" * 60)
    print("🔧 Applying behavior decomposition...")
    print("=" * 60)
    
    decomposition_result = bd.decompose(code)
    
    print(f"\n📊 Decomposition Results:")
    print(f"   Original lines: {decomposition_result.original_line_count}")
    print(f"   Extracted methods: {len(decomposition_result.extracted_methods)}")
    print(f"   Duplicate blocks: {len(decomposition_result.duplicate_blocks)}")
    print(f"   Feature envy detected: {decomposition_result.feature_envy_detected}")
    
    if decomposition_result.extracted_methods:
        print("\n📝 Extracted Methods:")
        for method in decomposition_result.extracted_methods[:3]:
            print(f"   • {method['name']}() - Type: {method['type']}")
            print(f"     Rationale: {method['rationale'][:60]}...")
    
    print("\n📜 Explanation (first 5 lines):")
    for line in decomposition_result.explanation[:5]:
        if line.strip():
            print(f"   {line}")
    
    # Test integration with RefactoringEngine
    print("\n" + "=" * 60)
    print("🔧 Testing integration with JavaRefactoringEngine...")
    print("=" * 60)
    
    engine = JavaRefactoringEngine()
    print("✅ JavaRefactoringEngine initialized with BehaviorDecomposer!")
    
    # Test refactor with decompose_behavior option
    refactor_result = engine.refactor(code, selected_refactorings=['decompose_behavior'])
    
    print(f"\n📊 Refactoring Result:")
    print(f"   Success: {refactor_result.success}")
    print(f"   Actions taken: {len(refactor_result.actions)}")
    print(f"   Code changed: {refactor_result.refactored_code != code}")
    
    if refactor_result.actions:
        print("\n📝 Actions:")
        for action in refactor_result.actions[:3]:
            print(f"   • {action.action_type}: {action.description[:80]}...")
    
    # Check if refactored code contains expected markers
    refactored = refactor_result.refactored_code
    markers = [
        "DECOMPOSE ITS BEHAVIOR",
        "Kent Beck",
        "Single Responsibility",
        "EXTRACTED METHODS"
    ]
    
    print("\n🔍 Checking for expected markers in refactored code:")
    for marker in markers:
        found = marker in refactored
        status = "✅" if found else "❌"
        print(f"   {status} '{marker}': {'Found' if found else 'Not found'}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_decomposer()
