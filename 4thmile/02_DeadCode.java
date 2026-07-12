// FEATURE: Dead Code Removal (unused private field + unused private method)
// This is the REFACTORED result: the unused Map/List imports, the unused
// private field, and the never-called private method have been removed.
public class DeadCode {

    public int add(int a, int b) {
        return a + b;
    }

    public void run() {
        System.out.println("Result: " + add(4, 5));
    }
}
