import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        while (true) {
            System.out.println("1.Add 2.Subtract 3.Multiply 4.Divide 5.Modulus 6.Power 7.Exit");
            int choice = sc.nextInt();
            if (choice == 7) {
                break;
            }
            double a = sc.nextDouble();
            double b = sc.nextDouble();
            switch (choice) {
                case 1:
                    System.out.println(a + b);
                    break;
                case 2:
                    System.out.println(a - b);
                    break;
                case 3:
                    System.out.println(a * b);
                    break;
                case 4:
                    if (b == 0) {
                        System.out.println("Error");
                    } else {
                        System.out.println(a / b);
                    }
                    break;
                case 5:
                    System.out.println(a % b);
                    break;
                case 6:
                    System.out.println(Math.pow(a, b));
                    break;
                default:
                    System.out.println("Invalid");
            }
        }
        sc.close();
    }
}
