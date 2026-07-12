// FEATURE: Condition Simplification (De Morgan's Law)
//   !(a >= b && a != 0)   ->   a < b || a == 0
//   !(x || y)             ->   !x && !y
public class Conditions {

    public boolean checkRange(int a, int b) {
        if (!(a >= b && a != 0)) {
            return true;
        }
        return false;
    }

    public boolean neither(boolean x, boolean y) {
        if (!(x || y)) {
            return true;
        }
        return false;
    }
}
