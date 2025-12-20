// UserManagementSystem.java

import java.util.*;

public class UserManagementSystem {
    
    private List<User> users;
    private Map<String, String> userCredentials;
    private String databasePath;
    
    public UserManagementSystem(String dbPath) {
        this.databasePath = dbPath;
        this.users = new ArrayList<>();
        this.userCredentials = new HashMap<>();
    }
    
    public boolean registerUser(String username, String password, String email, String firstName, String lastName) {
        if (username == null || username.isEmpty()) {
            System.out.println("Error: Username cannot be empty");
            return false;
        }
        if (username.length() < 3) {
            System.out.println("Error: Username must be at least 3 characters");
            return false;
        }
        
        if (password == null || password.isEmpty()) {
            System.out.println("Error: Password cannot be empty");
            return false;
        }
        if (password.length() < 8) {
            System.out.println("Error: Password must be at least 8 characters");
            return false;
        }
        
        if (email != null) {
            if (!email.isEmpty()) {
                if (email.contains("@")) {
                    if (email.contains(".")) {
                        System.out.println("Email format valid");
                    } else {
                        System.out.println("Error: Email must contain a dot");
                        return false;
                    }
                } else {
                    System.out.println("Error: Email must contain @");
                    return false;
                }
            }
        }
        
        for (User user : users) {
            if (user.getUsername().equals(username)) {
                System.out.println("Error: Username already exists");
                return false;
            }
        }
        
        User newUser = new User(username, password, email, firstName, lastName);
        users.add(newUser);
        userCredentials.put(username, password);
        
        System.out.println("User registered successfully: " + username);
        return true;
    }
    
    public boolean login(String username, String password) {
        String storedPassword = userCredentials.get(username);
        if (storedPassword != null && storedPassword.equals(password)) {
            System.out.println("Login successful: " + username);
            return true;
        }
        System.out.println("Login failed: Invalid credentials");
        return false;
    }
    
    public List<User> getAllUsers() {
        return new ArrayList<>(users);
    }
}

class User {
    private String username;
    private String password;
    private String email;
    private String firstName;
    private String lastName;
    
    public User(String username, String password, String email, String firstName, String lastName) {
        this.username = username;
        this.password = password;
        this.email = email;
        this.firstName = firstName;
        this.lastName = lastName;
    }
    
    public String getUsername() { return username; }
    public String getEmail() { return email; }
}
