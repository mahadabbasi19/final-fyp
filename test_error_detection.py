"""
Test Script for Java Error Detection Tool
==========================================
This script tests the error checker module independently
to verify all error detection capabilities.

Tests:
1. Syntax errors (missing semicolons, unmatched braces)
2. Runtime errors (null pointer, array bounds, division by zero)
3. Static analysis warnings (unused variables, naming conventions)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from java_refactoring_engine.error_checker import (
    ErrorChecker,
    JavaError,
    ErrorType,
    ErrorSeverity,
    JavaSyntaxChecker,
    RuntimeErrorDetector,
    StaticAnalyzer
)


def print_separator(title: str):
    """Print a section separator."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_errors(errors: list, title: str):
    """Print a list of errors."""
    print(f"\n{title} ({len(errors)} found):")
    print("-" * 40)
    
    if not errors:
        print("  ✅ No issues detected!")
        return
    
    for i, error in enumerate(errors, 1):
        icon = {
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.INFO: "ℹ️"
        }.get(error.severity, "•")
        
        print(f"  {icon} [{i}] Line {error.line}: {error.message}")
        if error.suggestion:
            print(f"       💡 {error.suggestion}")


def test_syntax_errors():
    """Test syntax error detection."""
    print_separator("SYNTAX ERROR DETECTION TEST")
    
    # Code with syntax errors
    code_with_syntax_errors = """
public class TestClass {
    public static void main(String[] args) {
        int x = 10
        String name = "Hello"
        
        if (x > 5) {
            System.out.println("Greater")
        
        for (int i = 0; i < 10; i++ {
            System.out.println(i);
        }
    }
}
"""
    
    print("\nTest Code (with intentional syntax errors):")
    print("-" * 40)
    for i, line in enumerate(code_with_syntax_errors.split('\n'), 1):
        print(f"{i:3}: {line}")
    
    checker = JavaSyntaxChecker()
    errors = checker.check_syntax(code_with_syntax_errors)
    print_errors(errors, "Syntax Errors Detected")


def test_runtime_errors():
    """Test runtime error detection."""
    print_separator("RUNTIME ERROR DETECTION TEST")
    
    # Code with potential runtime errors
    code_with_runtime_errors = """
public class RuntimeTest {
    public void processData() {
        String str;
        System.out.println(str.length());
        
        int[] numbers = new int[5];
        System.out.println(numbers[10]);
        
        int divisor = 0;
        int result = 100 / divisor;
        
        int negIndex = 5;
        System.out.println(numbers[negIndex - 10]);
        
        FileInputStream fis = new FileInputStream("file.txt");
        
        long bigNumber = 9999999999999999;
    }
}
"""
    
    print("\nTest Code (with potential runtime errors):")
    print("-" * 40)
    for i, line in enumerate(code_with_runtime_errors.split('\n'), 1):
        print(f"{i:3}: {line}")
    
    detector = RuntimeErrorDetector()
    errors = detector.detect_runtime_errors(code_with_runtime_errors)
    print_errors(errors, "Runtime Warnings Detected")


def test_static_analysis():
    """Test static analysis warnings."""
    print_separator("STATIC ANALYSIS TEST")
    
    # Code with code smells
    code_with_smells = """
public class badClassName {
    private static final int magicNumber = 42;
    
    public void VeryLongMethodThatDoesTooMuch() {
        int unusedVariable = 100;
        String anotherUnused = "test";
        
        int x = 10;
        return;
        System.out.println("Unreachable");
        
        if (x > 5) {
            if (x > 10) {
                if (x > 15) {
                    if (x > 20) {
                        if (x > 25) {
                            System.out.println("Deep nesting");
                        }
                    }
                }
            }
        }
        
        try {
            int y = 10 / 0;
        } catch (Exception e) {
        }
        
        System.exit(0);
    }
    
    public void duplicateCode1() {
        int a = 10;
        int b = 20;
        int sum = a + b;
        System.out.println(sum);
    }
    
    public void duplicateCode2() {
        int a = 10;
        int b = 20;
        int sum = a + b;
        System.out.println(sum);
    }
}
"""
    
    print("\nTest Code (with code smells):")
    print("-" * 40)
    for i, line in enumerate(code_with_smells.split('\n'), 1):
        print(f"{i:3}: {line}")
    
    analyzer = StaticAnalyzer()
    warnings = analyzer.analyze(code_with_smells)
    print_errors(warnings, "Static Analysis Warnings")


def test_full_analysis():
    """Test complete error checking."""
    print_separator("FULL ERROR ANALYSIS TEST")
    
    # Comprehensive test code
    test_code = """
public class OrderProcessor {
    private static final int max = 100;
    
    public void ProcessOrder(String orderId) {
        String data;
        int count = 0;
        
        if (orderId != null) {
            if (orderId.length() > 0) {
                System.out.println(data.toString());
            }
        }
        
        int[] items = new int[10];
        for (int i = 0; i <= 10; i++) {
            items[i] = i * 2
        }
        
        double price = 100.0 / count;
        
        try {
            processPayment();
        } catch (Exception e) {
        }
        
        FileInputStream file = new FileInputStream("orders.txt");
    }
    
    private void processPayment() {
        System.out.println("Processing");
    }
}
"""
    
    print("\nTest Code (comprehensive test):")
    print("-" * 40)
    for i, line in enumerate(test_code.split('\n'), 1):
        print(f"{i:3}: {line}")
    
    # Full analysis
    checker = ErrorChecker()
    all_errors = checker.check_code(test_code, include_warnings=True)
    
    # Separate by type
    syntax = [e for e in all_errors if e.error_type == ErrorType.SYNTAX]
    runtime = [e for e in all_errors if e.error_type == ErrorType.RUNTIME]
    warnings = [e for e in all_errors if e.error_type == ErrorType.WARNING]
    
    print_errors(syntax, "Syntax Errors")
    print_errors(runtime, "Runtime Warnings")
    print_errors(warnings, "Code Quality Warnings")
    
    # Summary
    summary = checker.get_error_summary(all_errors)
    print("\n" + "=" * 60)
    print("  ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"  ❌ Syntax Errors:    {summary['syntax_errors']}")
    print(f"  ⚠️  Runtime Warnings: {summary['runtime_warnings']}")
    print(f"  💡 Code Warnings:    {summary['code_warnings']}")
    print(f"  ℹ️  Info Messages:    {summary['info']}")
    print(f"  📊 Total Issues:     {summary['total']}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  JAVA ERROR DETECTION TOOL - TEST SUITE")
    print("=" * 60)
    
    test_syntax_errors()
    test_runtime_errors()
    test_static_analysis()
    test_full_analysis()
    
    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
