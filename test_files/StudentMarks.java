public class StudentMarks {
    public static void main(String[] args) {
        int marks1 = 85;
        int marks2 = 72;
        int marks3 = 90;
        int marks4 = 66;
        int marks5 = 78;

        int total = marks1 + marks2 + marks3 + marks4 + marks5;
        double average = total / 5;

        System.out.println("Marks 1: " + marks1);
        System.out.println("Marks 2: " + marks2);
        System.out.println("Marks 3: " + marks3);
        System.out.println("Marks 4: " + marks4);
        System.out.println("Marks 5: " + marks5);

        if (marks1 >= 50) {
            System.out.println("Marks 1: Pass");
        } else {
            System.out.println("Marks 1: Fail");
        }

        if (marks2 >= 50) {
            System.out.println("Marks 2: Pass");
        } else {
            System.out.println("Marks 2: Fail");
        }

        if (marks3 >= 50) {
            System.out.println("Marks 3: Pass");
        } else {
            System.out.println("Marks 3: Fail");
        }

        if (marks4 >= 50) {
            System.out.println("Marks 4: Pass");
        } else {
            System.out.println("Marks 4: Fail");
        }

        if (marks5 >= 50) {
            System.out.println("Marks 5: Pass");
        } else {
            System.out.println("Marks 5: Fail");
        }

        System.out.println("Total Marks: " + total);
        System.out.println("Average Marks: " + average);
    }
}