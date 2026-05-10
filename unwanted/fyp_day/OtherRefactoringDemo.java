/**
 * FILE 4: OtherRefactoringDemo.java
 * PURPOSE: Test other refactoring techniques
 * 
 * ISSUES TO FIX:
 * 1. LONG METHODS - Methods with 50+ lines
 * 2. DEEP NESTING - More than 3 levels of nesting
 * 3. DUPLICATE CODE - Same logic repeated multiple times
 * 4. LARGE CLASS - Too many methods and fields
 */
import java.util.List;
import java.util.ArrayList;

public class OtherRefactoringDemo {
    
    private String companyName;
    private String companyAddress;
    private String companyPhone;
    private String companyEmail;
    private String companyWebsite;
    private double taxRate;
    private double discountRate;
    private List<String> products;
    private List<Double> prices;
    private List<Integer> quantities;
    private List<String> customers;
    private List<String> orders;
    private int orderCount;
    private double totalRevenue;
    
    // ========== ISSUE 1: LONG METHOD ==========
    // This method is way too long (80+ lines)
    // Should be broken into smaller methods
    
    public void processCompleteOrder(String customerName, String customerEmail,
                                     String productName, int quantity,
                                     String shippingAddress, String billingAddress,
                                     String paymentMethod, String cardNumber) {
        // Step 1: Validate customer
        System.out.println("Starting order processing...");
        if (customerName == null || customerName.isEmpty()) {
            System.out.println("Error: Customer name is required");
            return;
        }
        if (customerEmail == null || customerEmail.isEmpty()) {
            System.out.println("Error: Customer email is required");
            return;
        }
        if (!customerEmail.contains("@")) {
            System.out.println("Error: Invalid email format");
            return;
        }
        System.out.println("Customer validated: " + customerName);
        
        // Step 2: Validate product
        if (productName == null || productName.isEmpty()) {
            System.out.println("Error: Product name is required");
            return;
        }
        if (quantity <= 0) {
            System.out.println("Error: Quantity must be positive");
            return;
        }
        if (quantity > 100) {
            System.out.println("Error: Maximum quantity is 100");
            return;
        }
        System.out.println("Product validated: " + productName + " x " + quantity);
        
        // Step 3: Validate shipping
        if (shippingAddress == null || shippingAddress.isEmpty()) {
            System.out.println("Error: Shipping address is required");
            return;
        }
        if (shippingAddress.length() < 10) {
            System.out.println("Error: Shipping address too short");
            return;
        }
        System.out.println("Shipping address validated");
        
        // Step 4: Validate billing
        if (billingAddress == null || billingAddress.isEmpty()) {
            billingAddress = shippingAddress;
            System.out.println("Using shipping address for billing");
        }
        System.out.println("Billing address validated");
        
        // Step 5: Validate payment
        if (paymentMethod == null || paymentMethod.isEmpty()) {
            System.out.println("Error: Payment method is required");
            return;
        }
        if (paymentMethod.equals("CARD")) {
            if (cardNumber == null || cardNumber.isEmpty()) {
                System.out.println("Error: Card number is required");
                return;
            }
            if (cardNumber.length() != 16) {
                System.out.println("Error: Invalid card number length");
                return;
            }
            System.out.println("Payment validated: Card ending in " + cardNumber.substring(12));
        } else if (paymentMethod.equals("PAYPAL")) {
            System.out.println("Payment validated: PayPal");
        } else {
            System.out.println("Error: Unknown payment method");
            return;
        }
        
        // Step 6: Calculate totals
        double unitPrice = 99.99;
        double subtotal = unitPrice * quantity;
        double tax = subtotal * 0.08;
        double shipping = 10.00;
        if (subtotal > 200) {
            shipping = 0;
        }
        double total = subtotal + tax + shipping;
        
        System.out.println("=== ORDER SUMMARY ===");
        System.out.println("Subtotal: $" + subtotal);
        System.out.println("Tax: $" + tax);
        System.out.println("Shipping: $" + shipping);
        System.out.println("Total: $" + total);
        
        // Step 7: Process payment
        System.out.println("Processing payment...");
        System.out.println("Payment successful!");
        
        // Step 8: Create order record
        String orderId = "ORD-" + System.currentTimeMillis();
        System.out.println("Order created: " + orderId);
        
        // Step 9: Send confirmation
        System.out.println("Sending confirmation email to " + customerEmail);
        System.out.println("Order complete!");
    }
    
    // ========== ISSUE 2: DEEP NESTING ==========
    // This method has 6+ levels of nesting
    // Should use guard clauses and early returns
    
    public String processUserRegistration(String username, String password, 
                                          String email, String phone, int age) {
        if (username != null) {
            if (!username.isEmpty()) {
                if (username.length() >= 3) {
                    if (username.length() <= 20) {
                        if (password != null) {
                            if (!password.isEmpty()) {
                                if (password.length() >= 8) {
                                    if (password.matches(".*[A-Z].*")) {
                                        if (password.matches(".*[0-9].*")) {
                                            if (email != null) {
                                                if (!email.isEmpty()) {
                                                    if (email.contains("@")) {
                                                        if (email.contains(".")) {
                                                            if (phone != null) {
                                                                if (phone.length() >= 10) {
                                                                    if (age >= 18) {
                                                                        if (age <= 120) {
                                                                            // Finally create user
                                                                            return "User created successfully!";
                                                                        } else {
                                                                            return "Age too high";
                                                                        }
                                                                    } else {
                                                                        return "Must be 18+";
                                                                    }
                                                                } else {
                                                                    return "Phone too short";
                                                                }
                                                            } else {
                                                                return "Phone required";
                                                            }
                                                        } else {
                                                            return "Invalid email domain";
                                                        }
                                                    } else {
                                                        return "Email needs @";
                                                    }
                                                } else {
                                                    return "Email empty";
                                                }
                                            } else {
                                                return "Email null";
                                            }
                                        } else {
                                            return "Password needs number";
                                        }
                                    } else {
                                        return "Password needs uppercase";
                                    }
                                } else {
                                    return "Password too short";
                                }
                            } else {
                                return "Password empty";
                            }
                        } else {
                            return "Password null";
                        }
                    } else {
                        return "Username too long";
                    }
                } else {
                    return "Username too short";
                }
            } else {
                return "Username empty";
            }
        } else {
            return "Username null";
        }
    }
    
    // ========== ISSUE 3: DUPLICATE CODE ==========
    // These three methods have almost identical logic
    // Should be refactored to a single parameterized method
    
    public double calculateGoldDiscount(double amount) {
        System.out.println("Calculating Gold discount...");
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
    
    public double calculateSilverDiscount(double amount) {
        System.out.println("Calculating Silver discount...");
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
    
    public double calculateBronzeDiscount(double amount) {
        System.out.println("Calculating Bronze discount...");
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
    
    // More duplicate code for tax calculation
    public double calculateUSATax(double amount) {
        System.out.println("Calculating USA tax...");
        double stateTax = amount * 0.05;
        double federalTax = amount * 0.03;
        double total = stateTax + federalTax;
        System.out.println("USA Tax: $" + total);
        return total;
    }
    
    public double calculateUKTax(double amount) {
        System.out.println("Calculating UK tax...");
        double vatTax = amount * 0.20;
        double total = vatTax;
        System.out.println("UK Tax: $" + total);
        return total;
    }
    
    public double calculateGermanyTax(double amount) {
        System.out.println("Calculating Germany tax...");
        double vatTax = amount * 0.19;
        double total = vatTax;
        System.out.println("Germany Tax: $" + total);
        return total;
    }
    
    // ========== ISSUE 4: LARGE CLASS - TOO MANY METHODS ==========
    // All these methods make this class too large
    // Some should be moved to separate utility classes
    
    public void method1() { System.out.println("Method 1"); }
    public void method2() { System.out.println("Method 2"); }
    public void method3() { System.out.println("Method 3"); }
    public void method4() { System.out.println("Method 4"); }
    public void method5() { System.out.println("Method 5"); }
    public void method6() { System.out.println("Method 6"); }
    public void method7() { System.out.println("Method 7"); }
    public void method8() { System.out.println("Method 8"); }
    public void method9() { System.out.println("Method 9"); }
    public void method10() { System.out.println("Method 10"); }
    
    public String formatCurrency(double amount) {
        return String.format("$%.2f", amount);
    }
    
    public String formatDate(long timestamp) {
        return new java.util.Date(timestamp).toString();
    }
    
    public String formatPhoneNumber(String phone) {
        if (phone.length() == 10) {
            return "(" + phone.substring(0, 3) + ") " + 
                   phone.substring(3, 6) + "-" + phone.substring(6);
        }
        return phone;
    }
    
    public boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
    
    public boolean isValidPhone(String phone) {
        return phone != null && phone.length() >= 10;
    }
    
    public static void main(String[] args) {
        OtherRefactoringDemo demo = new OtherRefactoringDemo();
        
        // Test long method
        demo.processCompleteOrder("John Doe", "john@email.com", 
                                  "Laptop", 2, 
                                  "123 Main St, City, Country",
                                  null, "CARD", "1234567890123456");
        
        // Test deep nesting
        System.out.println(demo.processUserRegistration(
            "john_doe", "Password123", "john@test.com", "1234567890", 25));
        
        // Test duplicate code
        demo.calculateGoldDiscount(750);
        demo.calculateSilverDiscount(750);
        demo.calculateBronzeDiscount(750);
    }
}
