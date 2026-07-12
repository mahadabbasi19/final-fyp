import java.util.List;
import java.util.Map;          // unused — engine removes this

public class DeadCodeDemo {

    private int unusedField = 42;              // dead field — removed

    public int add(int a, int b) {
        return a + b;
    }

    private void neverCalled() {                // dead private method — removed
        System.out.println("I am never used");
    }

    public void run() {
        System.out.println("Sum = " + add(2, 3));
    }
}
