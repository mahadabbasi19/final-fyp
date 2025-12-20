// OrderProcessingService.java

import java.util.*;
import java.math.BigDecimal;

public class OrderProcessingService {
    
    private List<Order> orders;
    private Map<String, Product> productCatalog;
    private Map<String, Customer> customers;
    
    public OrderProcessingService() {
        this.orders = new ArrayList<>();
        this.productCatalog = new HashMap<>();
        this.customers = new HashMap<>();
    }
    
    public boolean processOrder(String customerId, List<OrderItem> items, String paymentMethod) {
        if (customerId == null || customerId.isEmpty()) {
            System.out.println("Error: Customer ID is required");
            return false;
        }
        
        Customer customer = customers.get(customerId);
        if (customer == null) {
            System.out.println("Error: Customer not found");
            return false;
        }
        
        if (items == null || items.isEmpty()) {
            System.out.println("Error: Order must contain items");
            return false;
        }
        
        BigDecimal total = BigDecimal.ZERO;
        for (OrderItem item : items) {
            if (item != null) {
                Product product = productCatalog.get(item.getProductId());
                if (product != null) {
                    total = total.add(product.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
                }
            }
        }
        
        System.out.println("Order processed. Total: " + total);
        return true;
    }
    
    public void addProduct(String id, String name, double price) {
        Product product = new Product(id, name, BigDecimal.valueOf(price));
        productCatalog.put(id, product);
    }
    
    public void addCustomer(String id, String name) {
        Customer customer = new Customer(id, name);
        customers.put(id, customer);
    }
}

class Order {
    private String id;
    private String customerId;
    public String getId() { return id; }
    public String getCustomerId() { return customerId; }
}

class OrderItem {
    private String productId;
    private int quantity;
    public String getProductId() { return productId; }
    public int getQuantity() { return quantity; }
}

class Product {
    private String id;
    private String name;
    private BigDecimal price;
    public Product(String id, String name, BigDecimal price) {
        this.id = id;
        this.name = name;
        this.price = price;
    }
    public BigDecimal getPrice() { return price; }
}

class Customer {
    private String id;
    private String name;
    public Customer(String id, String name) {
        this.id = id;
        this.name = name;
    }
}

