// FEATURE: Real-time Error Detection (open the PROBLEMS tab)
//   1 syntax error + 3 runtime risks + warnings, updated live as you type.
public class Errors {

    public void run() {
        int x = 10                          // SYNTAX: missing semicolon

        String s;
        System.out.println(s.length());     // RUNTIME: possible NullPointer

        int r = 10 / 0;                     // RUNTIME: division by zero

        int[] arr = new int[5];
        System.out.println(arr[10]);        // RUNTIME: index out of bounds
    }
}
