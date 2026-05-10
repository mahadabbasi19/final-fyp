import java.util.*;

public class LegacyOrderProcessor {

    private List<String> inventory = new ArrayList<>();
    private Map<String, Double> prices = new HashMap<>();
    private List<String> logs = new ArrayList<>();

    public void processOrder(String customerName, String customerType, List<String> items, double discountCode, boolean isExpress, String country) {
        if (customerName != null && !customerName.isEmpty()) {
            if (items != null && !items.isEmpty()) {
                for (String item : items) {
                    if (inventory.contains(item)) {
                        double price = prices.getOrDefault(item, 0.0);
                        double tax = 0.0;
                        if (country.equals("USA")) {
                            tax = price * 0.08;
                        } else if (country.equals("UK")) {
                            tax = price * 0.20;
                        }

                        double finalPrice = price + tax;
                        if (customerType.equals("GOLD")) {
                            finalPrice = finalPrice - (finalPrice * 0.15);
                        }
                        
                        System.out.println("Processing item: " + item + " for " + customerName);
                        logs.add("Item " + item + " processed at " + new Date());
                    } else {
                        System.out.println("Out of stock: " + item);
                    }
                }
            }
        }
        double shippingCost = 0.0;
        if (isExpress) {
            if (country.equals("USA")) {
                shippingCost = 25.0;
            } else if (country.equals("UK")) {
                shippingCost = 40.0;
            }
        } else {
            if (country.equals("USA")) {
                shippingCost = 5.0;
            } else if (country.equals("UK")) {
                shippingCost = 10.0;
            }
        }
        saveToDatabase(customerName, items, shippingCost);
    }

    private void saveToDatabase(String name, List<String> items, double cost) {
        System.out.println("Connecting to DB...");
        System.out.println("Order saved for " + name);
    }
}