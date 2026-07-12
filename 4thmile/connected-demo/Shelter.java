import java.util.ArrayList;
import java.util.List;

public class Shelter {
    private List<Animal> animals = new ArrayList<>();

    public void add(Animal a) { animals.add(a); }

    public void makeAllSounds() {
        for (Animal a : animals) {
            System.out.println(a.sound());
        }
    }
}
