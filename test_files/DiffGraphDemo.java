// DiffGraphDemo.java - Test file for Diff Preview & Graph features
import java.util.HashMap;
import java.util.Map;

// Refactored using Change Structure - SRP Applied

public class DiffGraphDemo {
    // Extracted class references
    private final DiffGraphDemoCoreLogic diffGraphDemoCoreLogic = new DiffGraphDemoCoreLogic();


    private Map<String, Double> prices = new HashMap<>();
    private double totalRevenue = 0;
    private int orderCount = 0;

    // LONG METHOD - will trigger "Extract Method" refactoring
    public void processOrder(String customerId, String itemName, int quantity, String paymentType) {
        diffGraphDemoCoreLogic.processOrder(); // Delegated
    }

    // DUPLICATE CODE BLOCK 1 - will trigger "Remove Duplicates"
    public void generateReport() {
        diffGraphDemoCoreLogic.generateReport(); // Delegated
    }


    private String validateInput(Object out, Object isEmpty, Object positive, Object required, String customerId, int quantity, Object println, Object be, String itemName, Object name, Object is, Object must) {
        if (customerId == null || customerId.isEmpty()) {
        System.out.println("ERROR: Customer ID is required");
        return;
        }
        if (itemName == null || itemName.isEmpty()) {
        System.out.println("ERROR: Item name is required");
        return;
        }
        if (quantity <= 0) {
        System.out.println("ERROR: Quantity must be positive");
        return;
        }
        return itemName;
    }


    private void calculatePrice(Object discount, Object subtotal, Object prices, Object containsKey, int quantity, Object get, String itemName, Object basePrice, Object tax) {
        double basePrice = 0;
        if (prices.containsKey(itemName)) {
        basePrice = prices.get(itemName);
        } else {
        basePrice = 9.99;
        }
        
        double subtotal = basePrice * quantity;
        double tax = subtotal * 0.15;
        double discount = 0;
    }

    // DUPLICATE CODE BLOCK 2 - nearly identical to above
    public void printSummary() {
        System.out.println("===== SALES SUMMARY =====");
        System.out.println("Total Orders: " + orderCount);
        System.out.println("Total Revenue: $" + totalRevenue);
        System.out.println("Average Order: $" + (orderCount > 0 ? totalRevenue / orderCount : 0));
        System.out.println("Items Sold: " + items.size());
        System.out.println("=========================");
    }

    // Another method with nesting
    public String categorizeCustomer(int totalPurchases, double totalSpent) {
        diffGraphDemoCoreLogic.categorizeCustomer(); // Delegated
    }

    public void addPrice(String item, double price) {
        diffGraphDemoCoreLogic.addPrice(); // Delegated
    }

    public double getTotalRevenue() {
        return totalRevenue;
    }

    public int getOrderCount() {
        return orderCount;
    }
}

// DiffGraphDemoCoreLogic - Extracted for core_logic
public class DiffGraphDemoCoreLogic {

    private Object totalRevenue;
    private Object orderCount;

    public DiffGraphDemoCoreLogic() { }

    public void processOrder() {
        // TODO: Move processOrder implementation here
    }

    public void generateReport() {
        // TODO: Move generateReport implementation here
    }

    public void categorizeCustomer() {
        // TODO: Move categorizeCustomer implementation here
    }

    public void addPrice() {
        // TODO: Move addPrice implementation here
    }

}
