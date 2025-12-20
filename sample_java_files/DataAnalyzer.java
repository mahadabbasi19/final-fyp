// DataAnalyzer.java

import java.util.*;

public class DataAnalyzer {
    
    private List<Double> data;
    private String analysisType;
    
    public DataAnalyzer() {
        this.data = new ArrayList<>();
        this.analysisType = "default";
    }
    
    public void addData(double value) {
        data.add(value);
    }
    
    public double calculateMean() {
        if (data.isEmpty()) return 0;
        double sum = 0;
        for (double val : data) {
            sum += val;
        }
        return sum / data.size();
    }
    
    public double calculateMax() {
        if (data.isEmpty()) return 0;
        double max = data.get(0);
        for (double val : data) {
            if (val > max) max = val;
        }
        return max;
    }
    
    public double calculateMin() {
        if (data.isEmpty()) return 0;
        double min = data.get(0);
        for (double val : data) {
            if (val < min) min = val;
        }
        return min;
    }
    
    public void printAnalysis() {
        System.out.println("Analysis Type: " + analysisType);
        System.out.println("Data Count: " + data.size());
        System.out.println("Mean: " + calculateMean());
        System.out.println("Max: " + calculateMax());
        System.out.println("Min: " + calculateMin());
    }
    
    public static void main(String[] args) {
        DataAnalyzer analyzer = new DataAnalyzer();
        analyzer.addData(10.5);
        analyzer.addData(20.3);
        analyzer.addData(15.7);
        analyzer.printAnalysis();
    }
}

