import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner input = new Scanner(System.in);

        // Taking input from user
        System.out.print("Enter first number: ");
        double num1 = input.nextDouble();

        System.out.print("Enter second number: ");
        double num2 = input.nextDouble();

        // Performing operations
        double add = num1 + num2;
        double subtract = num1 - num2;
        double multiply = num1 * num2;

        System.out.println("Addition: " + add);
        System.out.println("Subtraction: " + subtract);
        System.out.println("Multiplication: " + multiply);

        // Division check
        if (num2 != 0) {
            double divide = num1 / num2;
            System.out.println("Division: " + divide);
        } else {
            System.out.println("Division: Cannot divide by zero");
        }

        input.close();
    }
}