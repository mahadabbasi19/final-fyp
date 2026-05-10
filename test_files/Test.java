public class Test {
    public static void main(String[] args) {

        int number = 10;
        String result = "";

        System.out.println("Java If-Else Example");
        System.out.println("--------------------");

        if (number > 0) {
            System.out.println("Number is positive");
            result = "Positive";

            if (number % 2 == 0) {
                System.out.println("It is even");
            } else {
                System.out.println("It is odd");
            }

        } else if (number == 0) {
            System.out.println("Number is zero");
            result = "Zero";

        } else {
            System.out.println("Number is negative");
            result = "Negative";

            if (number < -100) {
                System.out.println("Very small negative number");
            } else {
                System.out.println("Normal negative number");
            }
        }

        System.out.println("--------------------");
        System.out.println("Final Result: " + result);
        System.out.println("Program Finished");
        System.out.println("Thank you for using Java");
    }
}