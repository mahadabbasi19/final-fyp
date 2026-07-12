public class ErrorDemo {

    public void run() {
        int x = 10          // SYNTAX: missing semicolon

        String s;
        System.out.println(s.length());   // RUNTIME risk: s may be null (NPE)

        int result = 10 / 0;              // RUNTIME: division by zero

        int[] arr = new int[5];
        System.out.println(arr[10]);      // RUNTIME: index out of bounds
    }
}
