// ChangeStructureDemo.java

import java.util.*;

public class ChangeStructureDemo {
    
    private List<Order> orders;
    private Map<String, Customer> customers;
    private List<String> validationErrors;
    private double taxRate;
    private double discountRate;
    private double shippingRate;
    private List<String> auditLog;
    private boolean debugMode;
    
    public ChangeStructureDemo() {
        this.orders = new ArrayList<>();
        this.customers = new HashMap<>();
        this.validationErrors = new ArrayList<>();
        this.auditLog = new ArrayList<>();
        this.taxRate = 0.10;
        this.discountRate = 0.05;
        this.shippingRate = 5.00;
    }
    
    public Order loadOrder(String orderId) {
        logAction("Loading order: " + orderId);
        for (Order order : orders) {
            if (order.getId().equals(orderId)) {
                return order;
            }
        }
        return null;
    }
    
    public void saveOrder(Order order) {
        logAction("Saving order: " + order.getId());
        orders.add(order);
    }
    
    public void deleteOrder(String orderId) {
        logAction("Deleting order: " + orderId);
        orders.removeIf(o -> o.getId().equals(orderId));
    }
    
    public boolean validateOrder(Order order) {
        validationErrors.clear();
        if (order == null) {
            validationErrors.add("Order cannot be null");
            return false;
        }
        if (order.getId() == null || order.getId().isEmpty()) {
            validationErrors.add("Order ID is required");
        }
        if (order.getAmount() < 1) {
            validationErrors.add("Order amount must be at least 1");
        }
        return validationErrors.isEmpty();
    }
    
    public double calculateTax(double amount) {
        logAction("Calculating tax for: " + amount);
        return amount * taxRate;
    }
    
    public double calculateDiscount(double amount, String customerType) {
        logAction("Calculating discount");
        if ("PREMIUM".equals(customerType)) {
            return amount * (discountRate * 2);
        }
        return amount * discountRate;
    }
    
    public double calculateShipping(int itemCount) {
        return shippingRate * itemCount;
    }
    
    public double calculateTotal(Order order) {
        double subtotal = order.getAmount();
        double tax = calculateTax(subtotal);
        double discount = calculateDiscount(subtotal, order.getCustomerType());
        double shipping = calculateShipping(order.getItemCount());
        return subtotal + tax - discount + shipping;
    }
    
    public void sendOrderConfirmation(Order order, String email) {
        logAction("Sending confirmation to: " + email);
        System.out.println("Email sent to " + email + " for order " + order.getId());
    }
    
    public void sendShippingNotification(Order order, String email) {
        logAction("Sending shipping notification");
        System.out.println("Shipping email sent to " + email);
    }
    
    public void logAction(String action) {
        String entry = new Date() + " - " + action;
        auditLog.add(entry);
        if (debugMode) {
            System.out.println("[DEBUG] " + entry);
        }
    }
    
    public void logError(String error) {
        String entry = new Date() + " - ERROR: " + error;
        auditLog.add(entry);
        System.err.println(entry);
    }
    
    public List<String> getAuditLog() {
        return new ArrayList<>(auditLog);
    }
    
    public void setTaxRate(double rate) {
        this.taxRate = rate;
    }
    
    public void setDiscountRate(double rate) {
        this.discountRate = rate;
    }
}

class Order {
    private String id;
    private double amount;
    private String customerType;
    private int itemCount;
    private String status;
    
    public String getId() { return id; }
    public double getAmount() { return amount; }
    public String getCustomerType() { return customerType; }
    public int getItemCount() { return itemCount; }
    public String getStatus() { return status; }
}
