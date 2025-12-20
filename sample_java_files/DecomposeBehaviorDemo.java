// DecomposeBehaviorDemo.java

import java.util.*;
import java.math.BigDecimal;

public class DecomposeBehaviorDemo {
    
    private List<Invoice> invoices;
    private Map<String, Customer> customers;
    private Map<String, Product> products;
    
    private static final double TAX_RATE = 0.10;
    private static final double DISCOUNT_THRESHOLD = 1000.0;
    private static final double DISCOUNT_RATE = 0.05;
    
    public DecomposeBehaviorDemo() {
        this.invoices = new ArrayList<>();
        this.customers = new HashMap<>();
        this.products = new HashMap<>();
    }
    
    public InvoiceResult processInvoice(String invoiceId, String customerId, List<LineItem> items, String paymentMethod, boolean applyDiscount) {
        InvoiceResult result = new InvoiceResult();
        
        if (invoiceId == null || invoiceId.isEmpty()) {
            result.setSuccess(false);
            result.setMessage("Invoice ID is required");
            return result;
        }
        
        if (customerId == null || customerId.isEmpty()) {
            result.setSuccess(false);
            result.setMessage("Customer ID is required");
            return result;
        }
        
        Customer customer = customers.get(customerId);
        if (customer == null) {
            result.setSuccess(false);
            result.setMessage("Customer not found");
            return result;
        }
        
        if (items == null || items.isEmpty()) {
            result.setSuccess(false);
            result.setMessage("Invoice must have items");
            return result;
        }
        
        double subtotal = 0;
        for (LineItem item : items) {
            if (item != null) {
                Product product = products.get(item.getProductId());
                if (product != null) {
                    double itemTotal = product.getPrice() * item.getQuantity();
                    subtotal += itemTotal;
                }
            }
        }
        
        double tax = subtotal * TAX_RATE;
        double discount = 0;
        if (applyDiscount && subtotal > DISCOUNT_THRESHOLD) {
            discount = subtotal * DISCOUNT_RATE;
        }
        
        double total = subtotal + tax - discount;
        
        Invoice invoice = new Invoice();
        invoice.setId(invoiceId);
        invoice.setCustomerId(customerId);
        invoice.setSubtotal(subtotal);
        invoice.setTax(tax);
        invoice.setDiscount(discount);
        invoice.setTotal(total);
        
        invoices.add(invoice);
        
        result.setSuccess(true);
        result.setMessage("Invoice processed successfully");
        result.setTotal(total);
        return result;
    }
    
    public void printInvoiceSummary(String invoiceId) {
        for (Invoice inv : invoices) {
            if (inv.getId().equals(invoiceId)) {
                System.out.println("Invoice: " + inv.getId());
                System.out.println("Subtotal: " + inv.getSubtotal());
                System.out.println("Tax: " + inv.getTax());
                System.out.println("Discount: " + inv.getDiscount());
                System.out.println("Total: " + inv.getTotal());
            }
        }
    }
}

class Invoice {
    private String id;
    private String customerId;
    private double subtotal;
    private double tax;
    private double discount;
    private double total;
    
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }
    public double getSubtotal() { return subtotal; }
    public void setSubtotal(double subtotal) { this.subtotal = subtotal; }
    public double getTax() { return tax; }
    public void setTax(double tax) { this.tax = tax; }
    public double getDiscount() { return discount; }
    public void setDiscount(double discount) { this.discount = discount; }
    public double getTotal() { return total; }
    public void setTotal(double total) { this.total = total; }
}

class LineItem {
    private String productId;
    private int quantity;
    public String getProductId() { return productId; }
    public int getQuantity() { return quantity; }
}

class InvoiceResult {
    private boolean success;
    private String message;
    private double total;
    
    public boolean isSuccess() { return success; }
    public void setSuccess(boolean success) { this.success = success; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public double getTotal() { return total; }
    public void setTotal(double total) { this.total = total; }
}

