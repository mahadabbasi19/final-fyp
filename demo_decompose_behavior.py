"""
═══════════════════════════════════════════════════════════════════════════════
DECOMPOSE ITS BEHAVIOR - Kent Beck Refactoring Technique
Complete Demonstration for FYP/POC/Academic Evaluation
═══════════════════════════════════════════════════════════════════════════════

EXAM-READY DEFINITION:
"Decomposing Behavior is a refactoring technique that breaks down long or 
complex methods and classes into smaller, focused units where each unit 
handles exactly one responsibility, while preserving the program's external 
behavior completely."

═══════════════════════════════════════════════════════════════════════════════
"""

from java_refactoring_engine.refactoring_engine import (
    BehaviorDecomposer, 
    JavaRefactoringEngine,
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demonstrate_decompose_behavior():
    """
    Complete demonstration of Decompose Its Behavior refactoring.
    """
    
    print_section("KENT BECK'S 'DECOMPOSE ITS BEHAVIOR' REFACTORING")
    
    print("""
+---------------------------------------------------------------------+
|                     CONCEPTUAL EXPLANATION                          |
+---------------------------------------------------------------------+
|                                                                     |
|  WHAT IS DECOMPOSE ITS BEHAVIOR?                                    |
|  A refactoring technique that breaks down long or complex methods   |
|  and classes into smaller, focused units where each unit handles    |
|  exactly ONE responsibility.                                        |
|                                                                     |
|  WHY DOES IT EXIST?                                                 |
|  - Long methods are hard to understand and maintain                 |
|  - Mixed responsibilities violate Single Responsibility Principle   |
|  - Duplicate code increases maintenance burden                      |
|  - Complex methods are difficult to test                            |
|                                                                     |
|  CODE SMELLS IT ADDRESSES:                                          |
|  1. Long Method (>20 lines)                                         |
|  2. Large Class (>200 lines or >15 methods)                         |
|  3. Feature Envy (method uses other class's data excessively)       |
|  4. Duplicate Code (same logic repeated)                            |
|                                                                     |
|  PRINCIPLES APPLIED:                                                |
|  - Single Responsibility Principle (SRP)                            |
|  - Separation of Concerns                                           |
|  - High Cohesion / Low Coupling                                     |
|  - Extract Method Pattern                                           |
|  - Behavior Preservation                                            |
|                                                                     |
+---------------------------------------------------------------------+
    """)
    
    print_section("STEP 1: IDENTIFY RESPONSIBILITIES IN LONG METHOD")
    print("""
    The Behavior Decomposer analyzes the code and identifies:
    
    +----------------------------------------------------------------------+
    |  RESPONSIBILITY          |  LINES    |  PRINCIPLE VIOLATED           |
    +----------------------------------------------------------------------+
    |  Input Validation        |  1-15     |  Mixed with business logic    |
    |  Customer Lookup         |  16-25    |  Data access in processor     |
    |  Calculate Totals        |  26-35    |  Calculation logic mixed      |
    |  Apply Discounts         |  36-45    |  Business rules scattered     |
    |  Create Order            |  46-55    |  Object creation inline       |
    |  Save and Notify         |  56-65    |  Side effects at end          |
    +----------------------------------------------------------------------+
    
    ANALYSIS: 6 distinct responsibilities in ONE method = SRP violation!
    """)
    
    print_section("STEP 2: GROUP RELATED STATEMENTS")
    print("""
    Statements are grouped by:
    - Variables they operate on
    - Purpose they serve
    - Data they access
    
    Groups identified:
    1. validation_block: Null checks and format validation
    2. lookup_block: Database queries and status checks
    3. calculation_block: Arithmetic operations
    4. business_rules_block: Discount logic
    5. creation_block: Object instantiation
    6. persistence_block: Database and notification
    """)
    
    print_section("STEP 3: EXTRACT METHODS - Each with Single Responsibility")
    print("""
    +-----------------------------------------------------------------------------+
    |  EXTRACTED METHOD           |  RESPONSIBILITY        |  PRINCIPLE           |
    +-----------------------------------------------------------------------------+
    |  validateOrderInput()       |  Input validation      |  SRP                 |
    |  fetchAndValidateCustomer() |  Data access + rules   |  Separation Concerns |
    |  calculateOrderTotals()     |  Business calculation  |  High Cohesion       |
    |  createOrder()              |  Object creation       |  Factory Pattern     |
    |  saveAndNotify()            |  Side effects          |  Command Pattern     |
    +-----------------------------------------------------------------------------+
    """)
    
    print_section("STEP 4: VERIFY BEHAVIOR PRESERVATION")
    print("""
    BEHAVIOR PRESERVATION CHECKLIST:
    
    [x] Same inputs accepted (customerId, items, paymentMethod)
    [x] Same outputs returned (OrderResult with success/failure)
    [x] Same side effects (database save, email notification)
    [x] Same error handling (validation errors, customer not found)
    [x] Same business rules (discounts, eligibility)
    [x] Same execution order (validate -> lookup -> calculate -> save)
    
    The ONLY thing that changed is the STRUCTURE, not the BEHAVIOR!
    """)
    
    print_section("TESTING THE IMPLEMENTATION")
    
    # Initialize and test the decomposer
    decomposer = BehaviorDecomposer()
    print("BehaviorDecomposer initialized successfully!")
    
    # Test with sample code
    sample_code = '''
public class OrderProcessor {
    public OrderResult processOrder(String customerId, List<Item> items) {
        // Validation
        if (customerId == null) {
            return OrderResult.failure("Customer required");
        }
        if (items == null || items.isEmpty()) {
            return OrderResult.failure("Items required");
        }
        
        // Lookup
        Customer customer = database.findCustomer(customerId);
        if (customer == null) {
            return OrderResult.failure("Customer not found");
        }
        
        // Calculate
        BigDecimal total = BigDecimal.ZERO;
        for (Item item : items) {
            total = total.add(item.getPrice());
        }
        
        // Apply discount
        if (total.compareTo(BigDecimal.valueOf(100)) > 0) {
            total = total.multiply(BigDecimal.valueOf(0.9));
        }
        
        // Create order
        Order order = new Order();
        order.setCustomer(customer);
        order.setItems(items);
        order.setTotal(total);
        
        // Save
        database.save(order);
        
        return OrderResult.success(order);
    }
}
'''
    
    print("\nAnalyzing sample code...")
    analysis = decomposer.analyze_for_decomposition(sample_code)
    
    print(f"\nAnalysis Results:")
    print(f"  Needs decomposition: {analysis['needs_decomposition']}")
    print(f"  Long methods found: {len(analysis['long_methods'])}")
    print(f"  Reasons: {len(analysis['reasons'])}")
    
    for reason in analysis['reasons']:
        print(f"    - {reason}")
    
    print_section("WHY THIS MATTERS FOR FYP/POC/ACADEMIC EVALUATION")
    print("""
+-----------------------------------------------------------------------------+
|                         BENEFITS DEMONSTRATED                               |
+-----------------------------------------------------------------------------+
|                                                                             |
|  1. MAINTAINABILITY                                                         |
|     - Each method has ONE reason to change                                  |
|     - Changes are localized to specific methods                             |
|     - New developers can understand code faster                             |
|                                                                             |
|  2. TESTABILITY                                                             |
|     - Each extracted method can be unit tested independently                |
|     - Mock dependencies are easier to inject                                |
|     - Edge cases are easier to identify and test                            |
|                                                                             |
|  3. BUG REDUCTION                                                           |
|     - Smaller methods = fewer places for bugs to hide                       |
|     - Clear responsibilities = clear debugging targets                      |
|                                                                             |
|  4. SCALABILITY                                                             |
|     - Methods can be moved to separate classes as needed                    |
|     - Business rules can be extracted to strategy classes                   |
|     - Code can evolve without major rewrites                                |
|                                                                             |
|  5. REFACTORING SAFETY                                                      |
|     - Small changes = lower risk                                            |
|     - Behavior preservation = no regression                                 |
|     - Reversible steps = easy to undo if needed                             |
|                                                                             |
+-----------------------------------------------------------------------------+
    """)
    
    print_section("EXAM-READY SUMMARY")
    print("""
+-----------------------------------------------------------------------------+
|                                                                             |
|  DEFINITION:                                                                |
|  "Decomposing Behavior is a refactoring technique that breaks down long     |
|  or complex methods and classes into smaller, focused units where each      |
|  unit handles exactly one responsibility, while preserving the program's    |
|  external behavior completely."                                             |
|                                                                             |
|  KEY POINTS:                                                                |
|  - Kent Beck's Refactoring technique                                        |
|  - Targets: Long Method, Large Class, Feature Envy, Duplicate Code          |
|  - Applies: SRP, Separation of Concerns, High Cohesion, Low Coupling        |
|  - Process: Identify -> Group -> Extract -> Verify                          |
|  - Goal: Behavior preservation with structural improvement                  |
|                                                                             |
|  NON-NEGOTIABLE RULES:                                                      |
|  1. Never change behavior - only structure                                  |
|  2. Each method = one responsibility                                        |
|  3. Small, safe, incremental steps                                          |
|  4. Readability over cleverness                                             |
|  5. Don't over-decompose                                                    |
|                                                                             |
+-----------------------------------------------------------------------------+
    """)
    
    print("\n" + "=" * 70)
    print("  DEMONSTRATION COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate_decompose_behavior()
