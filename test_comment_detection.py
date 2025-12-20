"""Test that comments are properly detected and not flagged as errors."""

from java_refactoring_engine.error_checker import ErrorChecker

# Test code with various comment styles
test_code = """
public class TestComments {
    // This is a single line comment with if else for
    /* This is a multi-line comment
       that spans multiple lines
       with keywords like public private void */
    
    /**
     * JavaDoc comment
     * @param name the user name
     * @return greeting message
     */
    public String greet(String name) {
        // Another single line comment
        return "Hello, " + name; // inline comment
    }
    
    /*
     * Block comment with apparent syntax error
     * int x = ;  // this should not be flagged
     * System.exit(0);  // this should not be flagged
     */
    
    public void test() {
        int value = 42;  // actual code
        System.out.println(value);
    }
}
"""

checker = ErrorChecker()
errors = checker.check_code(test_code)

print('=== Error Detection Test ===')
print(f'Total errors/warnings found: {len(errors)}')
print()

for e in errors:
    print(f'Line {e.line}: [{e.error_type.name}] {e.message}')

# Check if any comment lines were flagged
comment_line_numbers = [3, 4, 5, 6, 8, 9, 10, 11, 12, 15, 17, 19, 20, 21, 22, 23]
flagged_comments = [e for e in errors if e.line in comment_line_numbers]

if flagged_comments:
    print()
    print('=== ISSUE: Comment lines incorrectly flagged ===')
    for e in flagged_comments:
        print(f'Line {e.line}: {e.message}')
else:
    print()
    print('=== SUCCESS: No comment lines were flagged as errors ===')
