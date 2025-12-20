// SimpleTest.java

public class SimpleTest {
    
    private String name;
    private int count;
    
    public SimpleTest() {
        this.name = "Test";
        this.count = 0;
    }
    
    public void sayHello() {
        System.out.println("Hello, " + name);
    }
    
    public int getCount() {
        return count;
    }
    
    public void incrementCount() {
        count++;
    }
    
    public static void main(String[] args) {
        SimpleTest test = new SimpleTest();
        test.sayHello();
        test.incrementCount();
        System.out.println("Count: " + test.getCount());
    }
}
