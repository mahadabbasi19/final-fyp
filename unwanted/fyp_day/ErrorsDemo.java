/**
 * FILE 1: ErrorsDemo.java
 * PURPOSE: Test error detection in the IDE
 * 
 * This file contains multiple syntax errors that your
 * Error Checker should detect and display in the Problems panel.
 */
public class ErrorsDemo {
    
    // ERROR 1: Unused import (will show as warning)
    import java.util.Scanner;
    import java.util.ArrayList;
    
    private String name
    private int age = 25;
    
    // ERROR 2: Missing semicolon above
    
    public ErrorsDemo() {
        this.name = "Test"  // ERROR 3: Missing semicolon
    }
    
    // ERROR 4: Unmatched braces - missing closing brace
    public void processData(String input) {
        if (input != null) {
            System.out.println("Processing: " + input);
            
            for (int i = 0; i < 10; i++ {  // ERROR 5: Missing closing parenthesis
                System.out.println(i);
            }
        
        // Missing closing brace for if statement
    }
    
    // ERROR 6: Type mismatch - assigning String to int
    public void typeMismatchDemo() {
        int number = "hello";
        boolean flag = "true";
        double price = "19.99";
    }
    
    // ERROR 7: Unclosed string literal
    public void unclosedString() {
        String message = "This string is not closed;
        System.out.println(message);
    }
    
    // ERROR 8: Missing return statement
    public int calculateSum(int a, int b) {
        int sum = a + b;
        // Missing: return sum;
    }
    
    // ERROR 9: Division by zero (runtime error detection)
    public void divisionError() {
        int x = 10;
        int y = 0;
        int result = x / 0;  // Direct division by zero
    }
    
    // ERROR 10: Unmatched brackets
    public void arrayError() {
        int[] numbers = new int[5;  // Missing closing bracket
        numbers[0] = 1;
        numbers[10] = 2;  // Array index out of bounds warning
    }
    
    // ERROR 11: Unclosed comment block
    public void commentError() {
        /* This is a multi-line comment
           that is never closed
        
        System.out.println("This code is inside comment");
    }
    
    // ERROR 12: Wrong method call
    public void wrongMethodCall() {
        String text = "Hello";
        int len = text.length();
        text.nonExistentMethod();  // Method doesn't exist
    }
    
    public static void main(String[] args) {
        ErrorsDemo demo = new ErrorsDemo();
        demo.processData("test")  // ERROR 13: Missing semicolon
        demo.typeMismatchDemo();
    }
}
