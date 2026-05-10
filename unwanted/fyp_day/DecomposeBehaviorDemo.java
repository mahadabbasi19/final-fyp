public class DecomposeBehaviorDemo {
    public void processOrder(int orderId) {
        // TODO: Add parameter validation for: int orderId
        // TODO: Add parameter validation for: int orderId
        // Long method to be decomposed
        if (orderId > 0) {
            System.out.println("Valid order");
            // ... more logic ...
            if (orderId % 2 == 0) {
                System.out.println("Even order");
            } else {
                System.out.println("Odd order");
            }
        } else {
            System.out.println("Invalid order");
        }
    }
}

