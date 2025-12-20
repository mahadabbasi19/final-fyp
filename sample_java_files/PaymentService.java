// PaymentService.java

import java.util.HashMap;
import java.util.Map;

public class PaymentService {
    private final Map<Integer, Double> customerBalances = new HashMap<>();
    private final SecurityLogger logger = new SecurityLogger();

    public PaymentService() {
        customerBalances.put(101, 500.0);
        customerBalances.put(102, 1000.0);
    }

    public boolean processPayment(int customerId, double amount, String type, String details) {
        if (!customerBalances.containsKey(customerId) || amount <= 0) {
            logger.logFailedAttempt(customerId, amount, "Invalid input");
            return false;
        }
        
        if (customerBalances.get(customerId) < amount) {
             logger.logFailedAttempt(customerId, amount, "Insufficient funds");
            return false;
        }

        boolean transactionResult = false;
        String processingDetails = "";

        switch (type.toLowerCase()) {
            case "credit":
                if (details.contains("EXPIRED")) {
                    processingDetails = "Credit card expired.";
                    logger.logFailedAttempt(customerId, amount, processingDetails);
                    return false;
                }
                System.out.println("Processing Credit Card payment...");
                transactionResult = true; 
                processingDetails = "Processed via Credit Card.";
                break;

            case "paypal":
                if (details.contains("EXPIRED")) {
                    processingDetails = "PayPal token expired.";
                    logger.logFailedAttempt(customerId, amount, processingDetails);
                    return false;
                }
                System.out.println("Processing PayPal payment...");
                transactionResult = true;
                processingDetails = "Processed via PayPal.";
                break;
                
            case "crypto":
                if (details.contains("EXPIRED")) {
                    processingDetails = "Crypto wallet expired.";
                    logger.logFailedAttempt(customerId, amount, processingDetails);
                    return false;
                }
                System.out.println("Processing Crypto payment...");
                transactionResult = Math.random() > 0.1; 
                processingDetails = "Processed via Crypto.";
                break;

            default:
                processingDetails = "Unknown payment type.";
                transactionResult = false;
                break;
        }
        
        if (transactionResult) {
            customerBalances.put(customerId, customerBalances.get(customerId) - amount);
            logger.logSuccessfulTransaction(customerId, amount, type);
            return true;
        } else {
            logger.logFailedAttempt(customerId, amount, "Transaction failed: " + processingDetails);
            return false;
        }
    }

    public double getBalance(int customerId) {
        return customerBalances.getOrDefault(customerId, 0.0);
    }
}

class SecurityLogger {
    public void logFailedAttempt(int customerId, double amount, String reason) {
        System.out.println("FAILED: Customer " + customerId + ", Amount: " + amount + ", Reason: " + reason);
    }
    
    public void logSuccessfulTransaction(int customerId, double amount, String type) {
        System.out.println("SUCCESS: Customer " + customerId + ", Amount: " + amount + ", Type: " + type);
    }
}
