"""Quick test for teacher code pattern."""

from java_refactoring_engine.refactoring_engine import StructureChanger, validate_java_braces
import re

test_code = '''
import java.util.*;

public class OrderService {
    private List<String> inventory = new ArrayList<>();
    private Map<String, Double> prices = new HashMap<>();

    public void processOrder(String name, String type, List<String> items) {
        if (name != null && !name.isEmpty()) {
            if (items != null && !items.isEmpty()) {
                for (String item : items) {
                    if (inventory.contains(item)) {
                        double price = prices.getOrDefault(item, 0.0);
                        if (type.equals("VIP")) {
                            price = price * 0.9;
                        } else if (type.equals("GOLD")) {
                            price = price * 0.85;
                        }
                        System.out.println("Processing: " + item);
                    }
                }
            }
        }
    }
}
'''

changer = StructureChanger()
result = changer.change_structure(test_code)

print('Success:', result.success)

is_valid, msg = validate_java_braces(result.refactored_code)
print('Braces balanced:', is_valid)
if not is_valid:
    print('Error:', msg)

hanging_else = re.search(r';\s*else\s+(if\s*\(|{)', result.refactored_code)
if hanging_else:
    print('SYNTAX ERROR: Hanging else')
else:
    print('[OK] No hanging else issues')

# Show the processItems helper method
print('\n=== Helper method ===')
lines = result.refactored_code.split('\n')
in_helper = False
helper_end = 0
for i, line in enumerate(lines, 1):
    if 'private void processItems' in line:
        in_helper = True
    if in_helper:
        print(f'{i:3}: {line}')
        helper_end = i
        if line.strip() == '}':
            # Check if this is the end of the method (not a nested block)
            # by counting braces
            pass
    if in_helper and i > helper_end + 50:  # Safety limit
        break
