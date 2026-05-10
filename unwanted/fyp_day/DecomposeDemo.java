/**
 * FILE 2: DecomposeDemo.java
 * PURPOSE: Test Decompose Behavior refactoring
 * 
 * This file has methods with complex logic that should be
 * decomposed into smaller, focused helper methods.
 * 
 * ISSUES TO FIX WITH DECOMPOSE BEHAVIOR:
 * - Long methods doing multiple things
 * - Complex conditional logic
 * - Nested loops and conditions
 * - Code that should be extracted to helper methods
 */
public class DecomposeDemo {
    
    private double taxRate = 0.08;
    private double discountRate = 0.10;
    
    /**
     * PROBLEM: This method does TOO MANY things:
     * 1. Validates the order
     * 2. Calculates subtotal
     * 3. Applies discounts
     * 4. Calculates tax
     * 5. Calculates shipping
     * 6. Generates receipt
     * 
     * SHOULD BE DECOMPOSED INTO: validateOrder(), calculateSubtotal(),
     * applyDiscount(), calculateTax(), calculateShipping(), generateReceipt()
     */
    public double processOrder(String[] items, double[] prices, int[] quantities, 
                               String customerType, String shippingMethod) {
        // Step 1: Validate order (should be separate method)
        if (items == null || items.length == 0) {
            System.out.println("Error: No items in order");
            return 0;
        }
        if (prices == null || prices.length != items.length) {
            System.out.println("Error: Price mismatch");
            return 0;
        }
        if (quantities == null || quantities.length != items.length) {
            System.out.println("Error: Quantity mismatch");
            return 0;
        }
        for (int i = 0; i < quantities.length; i++) {
            if (quantities[i] <= 0) {
                System.out.println("Error: Invalid quantity for " + items[i]);
                return 0;
            }
        }
        
        // Step 2: Calculate subtotal (should be separate method)
        double subtotal = 0;
        System.out.println("=== ORDER DETAILS ===");
        for (int i = 0; i < items.length; i++) {
            double itemTotal = prices[i] * quantities[i];
            subtotal += itemTotal;
            System.out.println(items[i] + " x " + quantities[i] + " = $" + itemTotal);
        }
        System.out.println("Subtotal: $" + subtotal);
        
        // Step 3: Apply discount based on customer type (should be separate method)
        double discount = 0;
        if (customerType != null) {
            if (customerType.equals("GOLD")) {
                discount = subtotal * 0.15;
                System.out.println("Gold Member Discount (15%): -$" + discount);
            } else if (customerType.equals("SILVER")) {
                discount = subtotal * 0.10;
                System.out.println("Silver Member Discount (10%): -$" + discount);
            } else if (customerType.equals("BRONZE")) {
                discount = subtotal * 0.05;
                System.out.println("Bronze Member Discount (5%): -$" + discount);
            } else {
                System.out.println("Regular Customer - No discount");
            }
        }
        double afterDiscount = subtotal - discount;
        
        // Step 4: Calculate tax (should be separate method)
        double tax = afterDiscount * taxRate;
        System.out.println("Tax (8%): +$" + tax);
        
        // Step 5: Calculate shipping (should be separate method)
        double shipping = 0;
        if (shippingMethod != null) {
            if (shippingMethod.equals("EXPRESS")) {
                shipping = 25.00;
                System.out.println("Express Shipping: +$" + shipping);
            } else if (shippingMethod.equals("STANDARD")) {
                shipping = 10.00;
                System.out.println("Standard Shipping: +$" + shipping);
            } else if (shippingMethod.equals("ECONOMY")) {
                shipping = 5.00;
                System.out.println("Economy Shipping: +$" + shipping);
            } else {
                shipping = 15.00;
                System.out.println("Default Shipping: +$" + shipping);
            }
        }
        
        // Step 6: Calculate and print total (should be separate method)
        double total = afterDiscount + tax + shipping;
        System.out.println("===================");
        System.out.println("TOTAL: $" + total);
        System.out.println("===================");
        
        return total;
    }
    
    /**
     * PROBLEM: Complex nested conditionals that should be decomposed
     * into guard clauses and helper methods
     */
    public String validateUser(String username, String password, String email, int age) {
        if (username != null) {
            if (username.length() >= 3) {
                if (username.length() <= 20) {
                    if (!username.contains(" ")) {
                        if (password != null) {
                            if (password.length() >= 8) {
                                if (password.matches(".*[A-Z].*")) {
                                    if (password.matches(".*[0-9].*")) {
                                        if (email != null) {
                                            if (email.contains("@")) {
                                                if (email.contains(".")) {
                                                    if (age >= 18) {
                                                        if (age <= 120) {
                                                            return "VALID";
                                                        } else {
                                                            return "Invalid age: too old";
                                                        }
                                                    } else {
                                                        return "Invalid age: must be 18+";
                                                    }
                                                } else {
                                                    return "Invalid email: missing domain";
                                                }
                                            } else {
                                                return "Invalid email: missing @";
                                            }
                                        } else {
                                            return "Email is required";
                                        }
                                    } else {
                                        return "Password must contain a number";
                                    }
                                } else {
                                    return "Password must contain uppercase";
                                }
                            } else {
                                return "Password too short";
                            }
                        } else {
                            return "Password is required";
                        }
                    } else {
                        return "Username cannot contain spaces";
                    }
                } else {
                    return "Username too long";
                }
            } else {
                return "Username too short";
            }
        } else {
            return "Username is required";
        }
    }
    
    /**
     * PROBLEM: Method with multiple responsibilities mixed together
     */
    public void generateReport(String[] data, String reportType, String format) {
        // Validation logic
        if (data == null || data.length == 0) {
            System.out.println("No data to report");
            return;
        }
        
        // Header generation
        String header = "";
        if (reportType.equals("SALES")) {
            header = "====== SALES REPORT ======";
        } else if (reportType.equals("INVENTORY")) {
            header = "====== INVENTORY REPORT ======";
        } else if (reportType.equals("CUSTOMER")) {
            header = "====== CUSTOMER REPORT ======";
        } else {
            header = "====== GENERAL REPORT ======";
        }
        
        // Formatting logic
        if (format.equals("HTML")) {
            System.out.println("<html><body>");
            System.out.println("<h1>" + header + "</h1>");
            System.out.println("<ul>");
            for (String item : data) {
                System.out.println("<li>" + item + "</li>");
            }
            System.out.println("</ul>");
            System.out.println("</body></html>");
        } else if (format.equals("CSV")) {
            System.out.println(header);
            for (String item : data) {
                System.out.println(item + ",");
            }
        } else {
            System.out.println(header);
            for (String item : data) {
                System.out.println("- " + item);
            }
        }
        
        // Footer generation
        System.out.println("Generated at: " + new java.util.Date());
        System.out.println("Total items: " + data.length);
    }
    
    public static void main(String[] args) {
        DecomposeDemo demo = new DecomposeDemo();
        
        String[] items = {"Laptop", "Mouse", "Keyboard"};
        double[] prices = {999.99, 29.99, 79.99};
        int[] quantities = {1, 2, 1};
        
        demo.processOrder(items, prices, quantities, "GOLD", "EXPRESS");
        
        System.out.println("\n" + demo.validateUser("john_doe", "Password123", "john@email.com", 25));
    }
}
