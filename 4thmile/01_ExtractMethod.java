import java.util.ArrayList;   // unused — engine removes this too
import java.util.List;

// FEATURE: Extract Method + Unused Import Removal
// Click the Refactoring wand -> "Refactor (Preview)".
// The engine splits this long method into calculateTotal / applyDiscount /
// addTax helpers and removes the unused ArrayList import.
public class OrderProcessor {

    public void processOrder(String customer, List<Double> prices,
                             String discountCode, String city) {
        System.out.println("Processing order for " + customer);

        // 1. Calculate total
        double total = 0;
        for (int i = 0; i < prices.size(); i++) {
            total += prices.get(i);
        }

        // 2. Apply discount
        if (discountCode != null) {
            if (discountCode.equals("SUMMER10")) {
                total = total - (total * 0.10);
            } else if (discountCode.equals("WINTER20")) {
                total = total - (total * 0.20);
            }
        }

        // 3. Add tax based on city
        if (city.equalsIgnoreCase("New York")) {
            total += total * 0.08875;
        } else if (city.equalsIgnoreCase("Los Angeles")) {
            total += total * 0.095;
        } else {
            total += total * 0.05;
        }

        // 4. Print invoice
        System.out.println("Total for " + customer + ": $" + total);
    }
}
