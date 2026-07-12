import java.util.List;
import java.util.Map;      // unused import  -> removed

// FEATURE: Dead Code Removal (unused private field + unused private method)
public class DeadCode {

    private int unusedCounter = 0;          // never used -> removed

    public int add(int a, int b) {
        return a + b;
    }

    private void debugLog() {               // never called -> removed
        System.out.println("debug");
    }

    public void run() {
        System.out.println("Result: " + add(4, 5));
    }
}
