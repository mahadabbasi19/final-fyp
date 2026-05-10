/**
 * FILE 5: AllRefactoringDemo.java
 * PURPOSE: Test ALL refactoring techniques together
 * 
 * This is the ULTIMATE TEST FILE - a nightmare class that has:
 * 
 * 1. DECOMPOSE BEHAVIOR ISSUES:
 *    - Methods doing multiple unrelated tasks
 *    - Complex conditional logic that should be extracted
 * 
 * 2. CHANGE STRUCTURE ISSUES:
 *    - God Class with multiple responsibilities
 *    - Data clumping (collections as fields)
 *    - Primitive obsession (String for domain concepts)
 *    - Low cohesion / High coupling
 * 
 * 3. LONG METHODS:
 *    - Methods with 50+ lines
 *    - Too many operations in one method
 * 
 * 4. DEEP NESTING:
 *    - 5+ levels of if/for/while nesting
 *    - Arrow code antipattern
 * 
 * 5. DUPLICATE CODE:
 *    - Same logic repeated in multiple methods
 *    - Copy-paste programming
 * 
 * 6. LARGE CLASS:
 *    - Too many fields (15+)
 *    - Too many methods (20+)
 *    - Multiple unrelated responsibilities
 * 
 * USE THIS TO DEMONSTRATE YOUR REFACTORING ENGINE'S FULL CAPABILITIES!
 */
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.Date;

public class AllRefactoringDemo {
    
    // ===== DATA CLUMPING: Should be Repository classes =====
    private List<String> products = new ArrayList<>();
    private Map<String, Double> prices = new HashMap<>();
    private List<String> customers = new ArrayList<>();
    private Map<String, String> customerTiers = new HashMap<>();
    private List<String> orders = new ArrayList<>();
    private Map<String, Double> countryTaxRates = new HashMap<>();
    private List<String> notifications = new ArrayList<>();
    private Map<String, Integer> inventory = new HashMap<>();
    
    // ===== TOO MANY FIELDS (Large Class) =====
    private String companyName = "MegaCorp";
    private String companyAddress = "123 Business St";
    private String companyPhone = "555-0100";
    private String companyEmail = "info@megacorp.com";
    private double defaultTaxRate = 0.08;
    private double defaultShippingRate = 9.99;
    private int maxOrderQuantity = 100;
    private int minOrderQuantity = 1;
    private double freeShippingThreshold = 200.0;
    private String defaultCurrency = "USD";
    
    public AllRefactoringDemo() {
        initializeData();
    }
    
    private void initializeData() {
        // Products
        products.add("Laptop"); prices.put("Laptop", 999.99); inventory.put("Laptop", 50);
        products.add("Phone"); prices.put("Phone", 699.99); inventory.put("Phone", 100);
        products.add("Tablet"); prices.put("Tablet", 499.99); inventory.put("Tablet", 75);
        products.add("Watch"); prices.put("Watch", 299.99); inventory.put("Watch", 200);
        products.add("Headphones"); prices.put("Headphones", 149.99); inventory.put("Headphones", 150);
        
        // Customers
        customers.add("Alice"); customerTiers.put("Alice", "GOLD");
        customers.add("Bob"); customerTiers.put("Bob", "SILVER");
        customers.add("Charlie"); customerTiers.put("Charlie", "BRONZE");
        customers.add("Diana"); customerTiers.put("Diana", "REGULAR");
        
        // Tax rates by country
        countryTaxRates.put("USA", 0.08);
        countryTaxRates.put("UK", 0.20);
        countryTaxRates.put("Germany", 0.19);
        countryTaxRates.put("Japan", 0.10);
        countryTaxRates.put("Canada", 0.13);
        countryTaxRates.put("Australia", 0.10);
        countryTaxRates.put("France", 0.20);
        countryTaxRates.put("Italy", 0.22);
    }
    
    // ===================================================================
    // MEGA METHOD: Contains ALL issues combined
    // - Long method (100+ lines)
    // - Multiple responsibilities
    // - Deep nesting
    // - Duplicate code patterns
    // - IO mixed with calculations
    // ===================================================================
    
    public double processCompleteOrderWithAllFeatures(
            String customerName, String customerEmail, String customerPhone,
            String productName, int quantity,
            String shippingAddress, String billingAddress,
            String country, String paymentMethod, String cardNumber,
            String promoCode, boolean giftWrap, String giftMessage) {
        
        // ===== VALIDATION BLOCK (DEEP NESTING - 8 levels!) =====
        if (customerName != null) {
            if (!customerName.isEmpty()) {
                if (customerName.length() >= 2) {
                    if (customerEmail != null) {
                        if (!customerEmail.isEmpty()) {
                            if (customerEmail.contains("@")) {
                                if (customerEmail.contains(".")) {
                                    if (productName != null) {
                                        if (!productName.isEmpty()) {
                                            if (products.contains(productName)) {
                                                if (quantity > 0) {
                                                    if (quantity <= maxOrderQuantity) {
                                                        if (inventory.get(productName) >= quantity) {
                                                            // Valid - continue processing
                                                            System.out.println("Validation passed!");
                                                        } else {
                                                            System.out.println("Error: Not enough inventory");
                                                            return 0;
                                                        }
                                                    } else {
                                                        System.out.println("Error: Quantity exceeds maximum");
                                                        return 0;
                                                    }
                                                } else {
                                                    System.out.println("Error: Quantity must be positive");
                                                    return 0;
                                                }
                                            } else {
                                                System.out.println("Error: Product not found");
                                                return 0;
                                            }
                                        } else {
                                            System.out.println("Error: Product name empty");
                                            return 0;
                                        }
                                    } else {
                                        System.out.println("Error: Product name null");
                                        return 0;
                                    }
                                } else {
                                    System.out.println("Error: Email missing domain");
                                    return 0;
                                }
                            } else {
                                System.out.println("Error: Email missing @");
                                return 0;
                            }
                        } else {
                            System.out.println("Error: Email empty");
                            return 0;
                        }
                    } else {
                        System.out.println("Error: Email null");
                        return 0;
                    }
                } else {
                    System.out.println("Error: Name too short");
                    return 0;
                }
            } else {
                System.out.println("Error: Name empty");
                return 0;
            }
        } else {
            System.out.println("Error: Name null");
            return 0;
        }
        
        // ===== PRICE CALCULATION (Should be extracted) =====
        double unitPrice = prices.get(productName);
        double subtotal = unitPrice * quantity;
        System.out.println("Subtotal: $" + subtotal);
        
        // ===== TAX CALCULATION (DUPLICATE CODE - same pattern as other methods) =====
        double tax = 0;
        if (country != null) {
            if (country.equals("USA")) {
                tax = subtotal * 0.08;
                System.out.println("USA Tax (8%): $" + tax);
            } else if (country.equals("UK")) {
                tax = subtotal * 0.20;
                System.out.println("UK VAT (20%): $" + tax);
            } else if (country.equals("Germany")) {
                tax = subtotal * 0.19;
                System.out.println("Germany VAT (19%): $" + tax);
            } else if (country.equals("Japan")) {
                tax = subtotal * 0.10;
                System.out.println("Japan Tax (10%): $" + tax);
            } else if (country.equals("Canada")) {
                tax = subtotal * 0.13;
                System.out.println("Canada Tax (13%): $" + tax);
            } else if (country.equals("Australia")) {
                tax = subtotal * 0.10;
                System.out.println("Australia GST (10%): $" + tax);
            } else if (country.equals("France")) {
                tax = subtotal * 0.20;
                System.out.println("France VAT (20%): $" + tax);
            } else {
                tax = subtotal * defaultTaxRate;
                System.out.println("Default Tax: $" + tax);
            }
        }
        
        // ===== SHIPPING CALCULATION (DUPLICATE CODE) =====
        double shipping = 0;
        if (country != null) {
            if (country.equals("USA")) {
                shipping = 5.99;
            } else if (country.equals("UK")) {
                shipping = 12.99;
            } else if (country.equals("Germany")) {
                shipping = 14.99;
            } else if (country.equals("Japan")) {
                shipping = 24.99;
            } else if (country.equals("Canada")) {
                shipping = 8.99;
            } else if (country.equals("Australia")) {
                shipping = 29.99;
            } else {
                shipping = defaultShippingRate;
            }
        }
        // Free shipping for large orders
        if (subtotal >= freeShippingThreshold) {
            shipping = 0;
            System.out.println("FREE SHIPPING!");
        } else {
            System.out.println("Shipping: $" + shipping);
        }
        
        // ===== DISCOUNT CALCULATION (DUPLICATE CODE - same as other methods) =====
        double discount = 0;
        String customerTier = customerTiers.getOrDefault(customerName, "REGULAR");
        if (customerTier.equals("GOLD")) {
            if (subtotal > 1000) {
                discount = subtotal * 0.20;
            } else if (subtotal > 500) {
                discount = subtotal * 0.15;
            } else if (subtotal > 100) {
                discount = subtotal * 0.10;
            } else {
                discount = subtotal * 0.05;
            }
            System.out.println("Gold Member Discount: $" + discount);
        } else if (customerTier.equals("SILVER")) {
            if (subtotal > 1000) {
                discount = subtotal * 0.15;
            } else if (subtotal > 500) {
                discount = subtotal * 0.10;
            } else if (subtotal > 100) {
                discount = subtotal * 0.07;
            } else {
                discount = subtotal * 0.03;
            }
            System.out.println("Silver Member Discount: $" + discount);
        } else if (customerTier.equals("BRONZE")) {
            if (subtotal > 1000) {
                discount = subtotal * 0.10;
            } else if (subtotal > 500) {
                discount = subtotal * 0.07;
            } else if (subtotal > 100) {
                discount = subtotal * 0.05;
            } else {
                discount = subtotal * 0.02;
            }
            System.out.println("Bronze Member Discount: $" + discount);
        }
        
        // ===== PROMO CODE (Should be extracted) =====
        double promoDiscount = 0;
        if (promoCode != null && !promoCode.isEmpty()) {
            if (promoCode.equals("SAVE10")) {
                promoDiscount = subtotal * 0.10;
                System.out.println("Promo SAVE10: -$" + promoDiscount);
            } else if (promoCode.equals("SAVE20")) {
                promoDiscount = subtotal * 0.20;
                System.out.println("Promo SAVE20: -$" + promoDiscount);
            } else if (promoCode.equals("SAVE50")) {
                promoDiscount = 50;
                System.out.println("Promo SAVE50: -$" + promoDiscount);
            } else if (promoCode.equals("NEWUSER")) {
                promoDiscount = subtotal * 0.25;
                System.out.println("New User Discount: -$" + promoDiscount);
            } else {
                System.out.println("Invalid promo code: " + promoCode);
            }
        }
        
        // ===== GIFT WRAP (Should be extracted) =====
        double giftWrapFee = 0;
        if (giftWrap) {
            giftWrapFee = 5.99;
            System.out.println("Gift Wrap: $" + giftWrapFee);
            if (giftMessage != null && !giftMessage.isEmpty()) {
                System.out.println("Gift Message: " + giftMessage);
            }
        }
        
        // ===== CALCULATE TOTAL =====
        double total = subtotal + tax + shipping - discount - promoDiscount + giftWrapFee;
        System.out.println("========================================");
        System.out.println("TOTAL: $" + String.format("%.2f", total));
        System.out.println("========================================");
        
        // ===== PAYMENT PROCESSING (Should be separate class) =====
        if (paymentMethod != null) {
            if (paymentMethod.equals("CARD")) {
                if (cardNumber != null && cardNumber.length() == 16) {
                    System.out.println("Processing card payment...");
                    System.out.println("Card: **** **** **** " + cardNumber.substring(12));
                    System.out.println("Payment successful!");
                } else {
                    System.out.println("Error: Invalid card number");
                    return 0;
                }
            } else if (paymentMethod.equals("PAYPAL")) {
                System.out.println("Redirecting to PayPal...");
                System.out.println("PayPal payment successful!");
            } else if (paymentMethod.equals("CRYPTO")) {
                System.out.println("Generating crypto wallet address...");
                System.out.println("Crypto payment successful!");
            } else {
                System.out.println("Error: Unknown payment method");
                return 0;
            }
        }
        
        // ===== UPDATE INVENTORY (Should be separate) =====
        int currentStock = inventory.get(productName);
        inventory.put(productName, currentStock - quantity);
        System.out.println("Inventory updated: " + productName + " now has " + 
                          inventory.get(productName) + " units");
        
        // ===== CREATE ORDER RECORD (Should be separate) =====
        String orderId = "ORD-" + System.currentTimeMillis();
        String orderRecord = orderId + "," + customerName + "," + productName + "," + 
                            quantity + "," + total + "," + new Date();
        orders.add(orderRecord);
        System.out.println("Order created: " + orderId);
        
        // ===== SEND NOTIFICATIONS (Should be separate NotificationService) =====
        String emailNotification = "EMAIL to " + customerEmail + ": Order " + orderId + 
                                   " confirmed! Total: $" + String.format("%.2f", total);
        notifications.add(emailNotification);
        System.out.println(emailNotification);
        
        if (customerPhone != null && !customerPhone.isEmpty()) {
            String smsNotification = "SMS to " + customerPhone + ": Your order " + 
                                    orderId + " is being processed!";
            notifications.add(smsNotification);
            System.out.println(smsNotification);
        }
        
        return total;
    }
    
    // ===== MORE DUPLICATE CODE: Tax calculation repeated =====
    
    public double calculateTaxForUSA(double amount) {
        System.out.println("Calculating USA tax...");
        double stateTax = amount * 0.05;
        double federalTax = amount * 0.03;
        double totalTax = stateTax + federalTax;
        System.out.println("State tax: $" + stateTax);
        System.out.println("Federal tax: $" + federalTax);
        System.out.println("Total USA tax: $" + totalTax);
        return totalTax;
    }
    
    public double calculateTaxForUK(double amount) {
        System.out.println("Calculating UK tax...");
        double vatTax = amount * 0.20;
        System.out.println("VAT (20%): $" + vatTax);
        System.out.println("Total UK tax: $" + vatTax);
        return vatTax;
    }
    
    public double calculateTaxForGermany(double amount) {
        System.out.println("Calculating Germany tax...");
        double vatTax = amount * 0.19;
        System.out.println("VAT (19%): $" + vatTax);
        System.out.println("Total Germany tax: $" + vatTax);
        return vatTax;
    }
    
    public double calculateTaxForJapan(double amount) {
        System.out.println("Calculating Japan tax...");
        double consumptionTax = amount * 0.10;
        System.out.println("Consumption tax (10%): $" + consumptionTax);
        System.out.println("Total Japan tax: $" + consumptionTax);
        return consumptionTax;
    }
    
    // ===== MORE DUPLICATE CODE: Discount calculation repeated =====
    
    public double calculateGoldMemberDiscount(double amount) {
        System.out.println("Gold member discount calculation...");
        double discount = 0;
        if (amount > 1000) {
            discount = amount * 0.20;
        } else if (amount > 500) {
            discount = amount * 0.15;
        } else if (amount > 100) {
            discount = amount * 0.10;
        } else {
            discount = amount * 0.05;
        }
        System.out.println("Gold discount: $" + discount);
        return discount;
    }
    
    public double calculateSilverMemberDiscount(double amount) {
        System.out.println("Silver member discount calculation...");
        double discount = 0;
        if (amount > 1000) {
            discount = amount * 0.15;
        } else if (amount > 500) {
            discount = amount * 0.10;
        } else if (amount > 100) {
            discount = amount * 0.07;
        } else {
            discount = amount * 0.03;
        }
        System.out.println("Silver discount: $" + discount);
        return discount;
    }
    
    public double calculateBronzeMemberDiscount(double amount) {
        System.out.println("Bronze member discount calculation...");
        double discount = 0;
        if (amount > 1000) {
            discount = amount * 0.10;
        } else if (amount > 500) {
            discount = amount * 0.07;
        } else if (amount > 100) {
            discount = amount * 0.05;
        } else {
            discount = amount * 0.02;
        }
        System.out.println("Bronze discount: $" + discount);
        return discount;
    }
    
    // ===== UTILITY METHODS (Should be in separate Utils class) =====
    
    public String formatPrice(double price) {
        return "$" + String.format("%.2f", price);
    }
    
    public String formatDate(Date date) {
        return date.toString();
    }
    
    public boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
    
    public boolean isValidPhone(String phone) {
        return phone != null && phone.length() >= 10;
    }
    
    public boolean isValidCardNumber(String card) {
        return card != null && card.length() == 16 && card.matches("\\d+");
    }
    
    // ===== REPORTING METHODS (Should be in ReportService) =====
    
    public void generateOrderReport() {
        System.out.println("\n===== ORDER REPORT =====");
        double totalRevenue = 0;
        for (String order : orders) {
            System.out.println(order);
            String[] parts = order.split(",");
            if (parts.length >= 5) {
                totalRevenue += Double.parseDouble(parts[4]);
            }
        }
        System.out.println("Total Revenue: " + formatPrice(totalRevenue));
        System.out.println("Total Orders: " + orders.size());
        System.out.println("========================\n");
    }
    
    public void generateInventoryReport() {
        System.out.println("\n===== INVENTORY REPORT =====");
        for (String product : products) {
            int stock = inventory.getOrDefault(product, 0);
            double price = prices.getOrDefault(product, 0.0);
            System.out.println(product + ": " + stock + " units @ " + formatPrice(price));
        }
        System.out.println("============================\n");
    }
    
    public void generateCustomerReport() {
        System.out.println("\n===== CUSTOMER REPORT =====");
        for (String customer : customers) {
            String tier = customerTiers.getOrDefault(customer, "REGULAR");
            System.out.println(customer + " - " + tier + " member");
        }
        System.out.println("===========================\n");
    }
    
    // ===== MAIN METHOD FOR TESTING =====
    
    public static void main(String[] args) {
        AllRefactoringDemo demo = new AllRefactoringDemo();
        
        System.out.println("=".repeat(60));
        System.out.println("TESTING ALL REFACTORING DEMO");
        System.out.println("=".repeat(60));
        
        // Test the mega method
        double total = demo.processCompleteOrderWithAllFeatures(
            "Alice",                              // customerName
            "alice@email.com",                    // customerEmail
            "555-1234",                           // customerPhone
            "Laptop",                             // productName
            2,                                    // quantity
            "123 Main St, New York, NY 10001",   // shippingAddress
            null,                                 // billingAddress (use shipping)
            "USA",                                // country
            "CARD",                               // paymentMethod
            "1234567890123456",                   // cardNumber
            "SAVE10",                             // promoCode
            true,                                 // giftWrap
            "Happy Birthday!"                     // giftMessage
        );
        
        System.out.println("\nOrder completed. Total charged: " + demo.formatPrice(total));
        
        // Generate reports
        demo.generateOrderReport();
        demo.generateInventoryReport();
        demo.generateCustomerReport();
    }
}
