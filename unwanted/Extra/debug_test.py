import re

# Test 1: The shipping cost structure
print("=== Test 1: Shipping cost pattern ===")
code = '''double shippingCost = 0.0;
        if (isExpress) {
            if (country.equals("USA")) {
                shippingCost = 25.0;
            }
        }'''

init_pattern = r'double\s+(shipping\w*|cost\w*)\s*=\s*0\.0\s*;'
match = re.search(init_pattern, code, re.IGNORECASE)
if match:
    print(f'Found variable: {match.group(1)}')
    after_init = code[match.end():]
    
    # Original pattern looks for var.xxx
    if_match = re.search(r'\s*if\s*\(\s*(\w+)[\.\s]', after_init)
    if if_match:
        print(f'Pattern 1 match - condition var: {if_match.group(1)}')
    else:
        print('Pattern 1 no match')
    
    # Check for boolean pattern if (boolVar)
    if_match2 = re.search(r'\s*if\s*\(\s*(\w+)\s*\)', after_init)
    if if_match2:
        print(f'Boolean pattern match: {if_match2.group(1)}')

# Test 2: Tax calculation inside loop
print("\n=== Test 2: Tax calculation pattern ===")
tax_code = '''double price = prices.getOrDefault(item, 0.0);
                        double tax = 0.0;
                        if (country.equals("USA")) {
                            tax = price * 0.08;
                        } else if (country.equals("UK")) {
                            tax = price * 0.20;
                        }'''

tax_pattern = r'double\s+(tax\w*)\s*=\s*0\.0\s*;'
match = re.search(tax_pattern, tax_code, re.IGNORECASE)
if match:
    print(f'Found tax variable: {match.group(1)}')
    after_init = tax_code[match.end():]
    if_match = re.search(r'\s*if\s*\(\s*(\w+)[\.\s]', after_init)
    if if_match:
        print(f'Condition var: {if_match.group(1)}')
        
        # Check first block content
        block_start = tax_code.find('{', match.end())
        pos = block_start + 1
        brace_count = 1
        while pos < len(tax_code) and brace_count > 0:
            if tax_code[pos] == '{':
                brace_count += 1
            elif tax_code[pos] == '}':
                brace_count -= 1
            pos += 1
        first_block = tax_code[block_start+1:pos-1]
        print(f'First block: {repr(first_block)}')
        
        # Check if it modifies our variable
        var_name = match.group(1)
        if re.search(rf'{re.escape(var_name)}\s*=', first_block):
            print(f'Block modifies {var_name}')
        else:
            print(f'Block does NOT modify {var_name}')
