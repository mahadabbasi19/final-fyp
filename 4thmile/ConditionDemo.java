public class ConditionDemo {

    // Engine applies De Morgan's Law:
    //   !(a >= b && a != 0)  ->  a < b || a == 0
    public boolean check(int a, int b) {
        if (!(a >= b && a != 0)) {
            return true;
        }
        return false;
    }

    // !(x || y)  ->  !x && !y
    public boolean both(boolean x, boolean y) {
        if (!(x || y)) {
            return true;
        }
        return false;
    }
}
