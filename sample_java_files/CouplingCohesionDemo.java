// CouplingCohesionDemo.java

import java.util.*;
import java.sql.Connection;

public class CouplingCohesionDemo {
    
    private List<String> dataList;
    private Map<String, Integer> dataMap;
    private DatabaseHandler dbHandler;
    private EmailSender emailSender;
    private LogWriter logWriter;
    private ConfigReader configReader;
    private ReportGenerator reportGen;
    
    public CouplingCohesionDemo() {
        this.dataList = new ArrayList<>();
        this.dataMap = new HashMap<>();
        this.dbHandler = new DatabaseHandler();
        this.emailSender = new EmailSender();
        this.logWriter = new LogWriter();
        this.configReader = new ConfigReader();
        this.reportGen = new ReportGenerator();
    }
    
    public void processData(String input) {
        logWriter.log("Processing: " + input);
        String config = configReader.read("settings");
        dataList.add(input);
        dbHandler.save(input);
        emailSender.send("Data processed: " + input);
    }
    
    public void generateReport() {
        logWriter.log("Generating report");
        List<String> data = dbHandler.loadAll();
        String report = reportGen.create(data);
        emailSender.send(report);
    }
    
    public void updateConfig(String key, String value) {
        configReader.write(key, value);
        logWriter.log("Config updated: " + key);
    }
    
    public void backupData() {
        List<String> all = dbHandler.loadAll();
        for (String item : all) {
            logWriter.log("Backup: " + item);
        }
    }
    
    public void notifyUsers(List<String> emails) {
        String report = reportGen.create(dataList);
        for (String email : emails) {
            emailSender.sendTo(email, report);
        }
        logWriter.log("Notified " + emails.size() + " users");
    }
    
    public void cleanupOldData(int days) {
        logWriter.log("Cleanup started");
        dbHandler.deleteOlderThan(days);
        logWriter.log("Cleanup completed");
    }
    
    public Map<String, Object> getStatistics() {
        Map<String, Object> stats = new HashMap<>();
        stats.put("total", dataList.size());
        stats.put("dbCount", dbHandler.count());
        stats.put("lastUpdate", configReader.read("lastUpdate"));
        return stats;
    }
    
    public void syncWithRemote(String url) {
        logWriter.log("Syncing with: " + url);
        List<String> local = dbHandler.loadAll();
        List<String> remote = fetchRemote(url);
        for (String item : remote) {
            if (!local.contains(item)) {
                dbHandler.save(item);
                dataList.add(item);
            }
        }
        emailSender.send("Sync completed");
    }
    
    private List<String> fetchRemote(String url) {
        return new ArrayList<>();
    }
    
    public void validateData() {
        for (String item : dataList) {
            if (item == null || item.isEmpty()) {
                logWriter.log("Invalid data found");
            }
        }
    }
    
    public void exportToFile(String filename) {
        logWriter.log("Exporting to: " + filename);
        List<String> all = dbHandler.loadAll();
        String content = reportGen.format(all);
        writeFile(filename, content);
    }
    
    private void writeFile(String name, String content) {
        System.out.println("Writing to " + name);
    }
}

class DatabaseHandler {
    public void save(String data) {}
    public List<String> loadAll() { return new ArrayList<>(); }
    public void deleteOlderThan(int days) {}
    public int count() { return 0; }
}

class EmailSender {
    public void send(String msg) {}
    public void sendTo(String email, String msg) {}
}

class LogWriter {
    public void log(String msg) { System.out.println(msg); }
}

class ConfigReader {
    public String read(String key) { return ""; }
    public void write(String key, String val) {}
}

class ReportGenerator {
    public String create(List<String> data) { return ""; }
    public String format(List<String> data) { return ""; }
}
