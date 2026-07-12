// FEATURE: Code Analysis + Metrics + AI Health Dashboard
// A deliberately complex method: high cyclomatic complexity + nesting.
// Use "Analyze Code", the Metrics panel, or ask the AI "show code health".
public class Metrics {

    public String classify(int score, boolean active, String tier) {
        if (active) {
            if (score >= 90) {
                if (tier.equals("gold")) {
                    return "elite";
                } else {
                    return "excellent";
                }
            } else if (score >= 70) {
                return "good";
            } else if (score >= 50) {
                return "average";
            } else {
                return "poor";
            }
        } else {
            return "inactive";
        }
    }
}
