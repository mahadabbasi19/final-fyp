// ErrorTestSample.java

public class ErrorTestSample {
    
    public void missingSemicolon() {
        int x = 10
        System.out.println(x);
    }
    
    public void unclosedParen() {
        System.out.println("Hello"
    }
    
    public void unclosedBrace() {
        if (true) {
            System.out.println("test");
    }
    
    public void extraBrace() {
        int y = 5;
    }
    }
    
    public void unclosedBracket() {
        int[] arr = new int[5;
    }
    
    public void correctMethod() {
        String message = "This is correct";
        System.out.println(message);
    }
}
