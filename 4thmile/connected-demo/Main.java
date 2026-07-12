public class Main {
    public static void main(String[] args) {
        Shelter shelter = new Shelter();
        shelter.add(new Dog());
        shelter.add(new Cat());
        shelter.makeAllSounds();
    }
}
