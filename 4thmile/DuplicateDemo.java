public class DuplicateDemo {

    // These two methods are structurally identical (renamed variables only).
    // The engine's token-normalized detector flags them as duplicates.
    public int sumPair(int x, int y) {
        int result = x + y;
        return result;
    }

    public int addPair(int a, int b) {
        int total = a + b;
        return total;
    }
}
