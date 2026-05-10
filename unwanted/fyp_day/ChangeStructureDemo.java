/**
 * FILE 3: ChangeStructureDemo.java
 * PURPOSE: Test Change Structure refactoring
 * 
 * This is a GOD CLASS that violates Single Responsibility Principle.
 * It handles: Order Processing, Tax Calculation, Shipping, 
 * Inventory Management, Customer Management, and Notifications.
 * 
 * ISSUES TO FIX WITH CHANGE STRUCTURE:
 * - Multiple responsibilities in one class (God Class)
 * - Tight coupling between unrelated functionalities
 * - Low cohesion - methods don't work together
 * - Data clumping - collections that should be repositories
 * - Primitive obsession - String used for domain concepts
 * 
 * SHOULD BE SPLIT INTO:
 * - OrderService
 * - TaxCalculator
 * - ShippingService
 * - InventoryRepository
 * - CustomerRepository
 * - NotificationService
 */
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;

public class ChangeStructureDemo {
    
    // DATA CLUMPING: These should be extracted to Repository classes
    private List<String> inventory = new ArrayList<>();
    private Map<String, Double> prices = new HashMap<>();
    private List<String> customers = new ArrayList<>();
    private Map<String, String> customerTypes = new HashMap<>();
    private List<String> orderHistory = new ArrayList<>();
    
    // PRIMITIVE OBSESSION: These String parameters should be domain objects
    // country -> Country class
    // customerType -> CustomerType class
    
    public ChangeStructureDemo() {
        // Initialize inventory
        inventory.add("Laptop");
        inventory.add("Phone");
        inventory.add("Tablet");
        inventory.add("Headphones");
        
        // Initialize prices
        prices.put("Laptop", 999.99);
        prices.put("Phone", 699.99);
        prices.put("Tablet", 499.99);
        prices.put("Headphones", 149.99);
        
        // Initialize customers
        customers.add("John");
        customers.add("Jane");
        customers.add("Bob");
        
        customerTypes.put("John", "GOLD");
        customerTypes.put("Jane", "SILVER");
        customerTypes.put("Bob", "REGULAR");
    }
    
    // ========== ORDER PROCESSING RESPONSIBILITY ==========
    // Should be in OrderService class
    
    public double processOrder(String customer, String item, int quantity, String country) {
        // Validate customer
        if (!customers.contains(customer)) {
            System.out.println("Customer not found: " + customer);
            return 0;
        }
        
        // Check inventory
        if (!inventory.contains(item)) {
            System.out.println("Item not in inventory: " + item);
            return 0;
        }
        
        // Get price
        double unitPrice = prices.getOrDefault(item, 0.0);
        double subtotal = unitPrice * quantity;
        
        // Calculate tax (SHOULD BE IN TaxCalculator)
        double tax = calculateTax(subtotal, country);
        
        // Calculate shipping (SHOULD BE IN ShippingService)
        double shipping = calculateShipping(country, subtotal);
        
        // Apply customer discount
        String customerType = customerTypes.get(customer);
        double discount = calculateDiscount(subtotal, customerType);
        
        double total = subtotal + tax + shipping - discount;
        
        // Record order (SHOULD BE IN OrderRepository)
        String orderRecord = customer + "," + item + "," + quantity + "," + total;
        orderHistory.add(orderRecord);
        
        // Send notification (SHOULD BE IN NotificationService)
        sendOrderConfirmation(customer, item, total);
        
        return total;
    }
    
    // ========== TAX CALCULATION RESPONSIBILITY ==========
    // Should be in TaxCalculator class
    
    public double calculateTax(double amount, String country) {
        // PRIMITIVE OBSESSION: country should be a Country object
        if (country.equals("USA")) {
            return amount * 0.08;
        } else if (country.equals("UK")) {
            return amount * 0.20;
        } else if (country.equals("Germany")) {
            return amount * 0.19;
        } else if (country.equals("Japan")) {
            return amount * 0.10;
        } else if (country.equals("Canada")) {
            return amount * 0.13;
        } else if (country.equals("Australia")) {
            return amount * 0.10;
        } else {
            return amount * 0.15; // Default tax
        }
    }
    
    public double getTaxRate(String country) {
        if (country.equals("USA")) {
            return 0.08;
        } else if (country.equals("UK")) {
            return 0.20;
        } else if (country.equals("Germany")) {
            return 0.19;
        } else if (country.equals("Japan")) {
            return 0.10;
        } else {
            return 0.15;
        }
    }
    
    // ========== SHIPPING RESPONSIBILITY ==========
    // Should be in ShippingService class
    
    public double calculateShipping(String country, double orderAmount) {
        double baseShipping = 10.0;
        
        // Country-based shipping rates
        if (country.equals("USA")) {
            baseShipping = 5.0;
        } else if (country.equals("UK")) {
            baseShipping = 15.0;
        } else if (country.equals("Germany")) {
            baseShipping = 18.0;
        } else if (country.equals("Japan")) {
            baseShipping = 25.0;
        } else if (country.equals("Australia")) {
            baseShipping = 30.0;
        }
        
        // Free shipping for large orders
        if (orderAmount > 500) {
            return 0;
        } else if (orderAmount > 200) {
            return baseShipping * 0.5;
        }
        
        return baseShipping;
    }
    
    public String getShippingMethod(String country) {
        if (country.equals("USA") || country.equals("Canada")) {
            return "USPS Priority";
        } else if (country.equals("UK") || country.equals("Germany")) {
            return "DHL Express";
        } else {
            return "International Standard";
        }
    }
    
    // ========== DISCOUNT/PRICING RESPONSIBILITY ==========
    // Should be in PricingService class
    
    public double calculateDiscount(double amount, String customerType) {
        // PRIMITIVE OBSESSION: customerType should be CustomerType object
        if (customerType.equals("GOLD")) {
            return amount * 0.15;
        } else if (customerType.equals("SILVER")) {
            return amount * 0.10;
        } else if (customerType.equals("BRONZE")) {
            return amount * 0.05;
        } else {
            return 0;
        }
    }
    
    public double applyPromoCode(double amount, String promoCode) {
        if (promoCode.equals("SAVE10")) {
            return amount * 0.10;
        } else if (promoCode.equals("SAVE20")) {
            return amount * 0.20;
        } else if (promoCode.equals("FREESHIP")) {
            return 0; // Free shipping handled elsewhere
        }
        return 0;
    }
    
    // ========== INVENTORY RESPONSIBILITY ==========
    // Should be in InventoryRepository class
    
    public void addToInventory(String item, double price) {
        if (!inventory.contains(item)) {
            inventory.add(item);
            prices.put(item, price);
            System.out.println("Added to inventory: " + item);
        }
    }
    
    public void removeFromInventory(String item) {
        inventory.remove(item);
        prices.remove(item);
        System.out.println("Removed from inventory: " + item);
    }
    
    public boolean checkInventory(String item) {
        return inventory.contains(item);
    }
    
    public List<String> getAllInventory() {
        return new ArrayList<>(inventory);
    }
    
    // ========== CUSTOMER RESPONSIBILITY ==========
    // Should be in CustomerRepository class
    
    public void addCustomer(String name, String type) {
        if (!customers.contains(name)) {
            customers.add(name);
            customerTypes.put(name, type);
            System.out.println("Added customer: " + name + " (" + type + ")");
        }
    }
    
    public void upgradeCustomer(String name, String newType) {
        if (customers.contains(name)) {
            customerTypes.put(name, newType);
            sendNotification(name, "Congratulations! You've been upgraded to " + newType);
        }
    }
    
    public String getCustomerType(String name) {
        return customerTypes.getOrDefault(name, "REGULAR");
    }
    
    // ========== NOTIFICATION RESPONSIBILITY ==========
    // Should be in NotificationService class
    
    public void sendOrderConfirmation(String customer, String item, double total) {
        System.out.println("EMAIL to " + customer + ": Your order for " + item + " ($" + total + ") has been confirmed!");
    }
    
    public void sendNotification(String customer, String message) {
        System.out.println("NOTIFICATION to " + customer + ": " + message);
    }
    
    public void sendShippingUpdate(String customer, String trackingNumber) {
        System.out.println("SMS to " + customer + ": Your order has shipped! Tracking: " + trackingNumber);
    }
    
    // ========== REPORTING RESPONSIBILITY ==========
    // Should be in ReportingService class
    
    public void generateSalesReport() {
        System.out.println("=== SALES REPORT ===");
        double totalSales = 0;
        for (String order : orderHistory) {
            System.out.println(order);
            String[] parts = order.split(",");
            totalSales += Double.parseDouble(parts[3]);
        }
        System.out.println("Total Sales: $" + totalSales);
    }
    
    public void generateInventoryReport() {
        System.out.println("=== INVENTORY REPORT ===");
        for (String item : inventory) {
            System.out.println(item + ": $" + prices.get(item));
        }
    }
    
    public static void main(String[] args) {
        ChangeStructureDemo demo = new ChangeStructureDemo();
        
        // Process some orders
        demo.processOrder("John", "Laptop", 1, "USA");
        demo.processOrder("Jane", "Phone", 2, "UK");
        
        // Generate reports
        demo.generateSalesReport();
        demo.generateInventoryReport();
    }
}
