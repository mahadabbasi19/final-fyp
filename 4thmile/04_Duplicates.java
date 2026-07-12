// FEATURE: Duplicate Detection (token-normalized: catches renamed clones)
// sumPair and addPair are structurally identical.
public class Duplicates {

    public int sumPair(int x, int y) {
        int result = x + y;
        return result;
    }

    public int addPair(int a, int b) {
        int total = a + b;
        return total;
    }
}
