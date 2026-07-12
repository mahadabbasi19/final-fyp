import java.util.ArrayList;
import java.util.List;

public class OrderManager {

    public void processOrder(String customerName, String customerEmail, List<String> items,
                             List<Double> prices, String discountCode, String city,
                             String street, String zipCode) {
        System.out.println("Starting process...");

        // 1. Calculate total
        double total = calculateTotal(prices);

        // 2. Apply discount codes (Magic Strings & Hardcoded Logic)
        total = applyDiscountCodesMagic(total, discountCode);

        // 3. Add tax based on city (Hardcoded data)
        total = addTaxBasedOn(total, city);

        // 4. Print invoice
        System.out.println("Invoice for: " + customerName);
        System.out.println("Shipping to: " + street + ", " + city + ", " + zipCode);
        for (int i = 0; i < items.size(); i++) {
            System.out.println("- " + items.get(i) + ": $" + prices.get(i));
        }
        System.out.println("Total Amount: $" + total);
    }

    private double calculateTotal(List prices) {
        double total = 0;
        for (int i = 0; i < prices.size(); i++) {
        total += prices.get(i);
        }
        return total;
    }


    private double applyDiscountCodesMagic(double total, String discountCode) {
        if (discountCode != null) {
        if (discountCode.equals("SUMMER10")) {
        total = total - (total * 0.10);
        } else if (discountCode.equals("WINTER20")) {
        total = total - (total * 0.20);
        }
        }
        return total;
    }


    private double addTaxBasedOn(double total, String city) {
        if (city.equalsIgnoreCase("New York")) {
        total += total * 0.08875;
        } else if (city.equalsIgnoreCase("Los Angeles")) {
        total += total * 0.095;
        } else {
        total += total * 0.05; // Default tax
        }
        return total;
    }

}
