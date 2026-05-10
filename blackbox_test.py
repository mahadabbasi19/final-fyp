"""
Black-Box Testing for CodeNova IDE Backend API
Tests API endpoints as an external consumer would — no internal knowledge used.
"""
import requests
import json
import time

BASE = "http://127.0.0.1:8000"
RESULTS = []

def test(name, fn):
    try:
        passed, detail = fn()
        status = "PASS" if passed else "FAIL"
    except Exception as e:
        passed, detail, status = False, str(e), "FAIL"
    RESULTS.append((name, status, detail))
    print(f"  [{status}] {name}")
    if not passed:
        print(f"         → {detail}")


# ============================================================
# 1. HEALTH ENDPOINT
# ============================================================
def t_health():
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        return False, f"Status {r.status_code}"
    d = r.json()
    if d.get("status") != "healthy":
        return False, f"Expected healthy, got {d}"
    return True, "OK"

# ============================================================
# 2. ERROR CHECKING — valid Java with errors
# ============================================================
def t_error_check_missing_semicolon():
    """Should detect missing semicolon"""
    code = 'public class Test {\n  public void foo() {\n    int x = 5\n  }\n}'
    r = requests.post(f"{BASE}/check-errors", json={"java_code": code}, timeout=15)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text}"
    d = r.json()
    if not d.get("has_errors"):
        return False, "Expected errors but got has_errors=false"
    if len(d.get("syntax_errors", [])) == 0:
        return False, "Expected syntax_errors but list is empty"
    return True, f"Found {len(d['syntax_errors'])} syntax error(s)"

def t_error_check_missing_bracket():
    """Should detect missing closing bracket"""
    code = 'public class Test {\n  public void foo() {\n    System.out.println("hi");\n  \n}'
    r = requests.post(f"{BASE}/check-errors", json={"java_code": code}, timeout=15)
    d = r.json()
    if not d.get("has_errors"):
        return False, "Expected errors for missing bracket but got has_errors=false"
    all_errors = d.get("syntax_errors", []) + d.get("runtime_errors", [])
    return True, f"Found {len(all_errors)} error(s)"

def t_error_check_clean_code():
    """Clean Java code should have no syntax errors"""
    code = 'public class Test {\n  public void foo() {\n    int x = 5;\n    System.out.println(x);\n  }\n}'
    r = requests.post(f"{BASE}/check-errors", json={"java_code": code}, timeout=15)
    d = r.json()
    syntax_errs = d.get("syntax_errors", [])
    if len(syntax_errs) > 0:
        return False, f"Clean code reported {len(syntax_errs)} syntax error(s): {syntax_errs[0].get('message')}"
    return True, "No false positives"

def t_error_check_empty_code():
    """Empty code should return 400"""
    r = requests.post(f"{BASE}/check-errors", json={"java_code": ""}, timeout=10)
    if r.status_code != 400:
        return False, f"Empty code should return 400, got {r.status_code}"
    return True, "400 returned correctly"

# ============================================================
# 3. REFACTORING
# ============================================================
def t_refactor_basic():
    """Refactor endpoint should return refactored code"""
    code = '''public class Test {
    public void processOrder(int qty, double price, String name, boolean express) {
        double total = 0;
        if (qty > 0) {
            if (price > 0) {
                total = qty * price;
                if (express) {
                    total = total + 10;
                }
                if (total > 100) {
                    total = total * 0.9;
                }
                System.out.println("Order for " + name + ": $" + total);
            }
        }
    }
}'''
    r = requests.post(f"{BASE}/refactor", json={"java_code": code, "apply_all": True}, timeout=30)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "refactored_code" not in d:
        return False, f"No refactored_code in response. Keys: {list(d.keys())}"
    return True, "Refactored code returned"

def t_refactor_review():
    """Refactor review should return diff + session_id"""
    code = '''public class Calculator {
    public int add(int a, int b) { return a + b; }
    public int subtract(int a, int b) { return a - b; }
    public void unusedMethod() {}
}'''
    r = requests.post(f"{BASE}/refactor/review", json={"java_code": code}, timeout=30)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "session_id" not in d:
        return False, f"No session_id. Keys: {list(d.keys())}"
    if "original_code" not in d or "refactored_code" not in d:
        return False, f"Missing original/refactored code. Keys: {list(d.keys())}"
    return True, f"Session {d['session_id'][:8]}... created"

# ============================================================
# 4. ANALYSIS
# ============================================================
def t_analyze_basic():
    """Analyze should return metrics, smells, opportunities"""
    code = '''public class UserService {
    private String dbUrl;
    private String dbUser;
    private String dbPass;
    public void createUser(String name, String email, String phone, String address, String city, String zip) {
        System.out.println("Creating user: " + name);
        System.out.println("Email: " + email);
        System.out.println("Phone: " + phone);
    }
    public void deleteUser(String name) { System.out.println("Deleting: " + name); }
}'''
    r = requests.post(f"{BASE}/analyze", json={"java_code": code}, timeout=15)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "metrics" not in d:
        return False, f"No metrics. Keys: {list(d.keys())}"
    m = d["metrics"]
    if m.get("total_lines", 0) == 0:
        return False, "total_lines is 0"
    return True, f"Lines={m.get('total_lines')}, Methods={m.get('total_methods')}"

# ============================================================
# 5. CHAT (AI)
# ============================================================
def t_chat_simple():
    """Chat should respond to a simple question"""
    r = requests.post(f"{BASE}/chat", json={"user_message": "What is a Java interface?"}, timeout=30)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "reply" not in d:
        return False, f"No reply field. Keys: {list(d.keys())}"
    if len(d["reply"]) < 20:
        return False, f"Reply too short: {d['reply']}"
    return True, f"Reply length: {len(d['reply'])} chars"

def t_chat_with_code():
    """Chat with code context should include mode"""
    code = 'public class Foo { public void bar() { System.out.println("hello"); } }'
    r = requests.post(f"{BASE}/chat", json={"user_message": "Explain this code", "code": code}, timeout=30)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "reply" not in d:
        return False, f"No reply. Keys: {list(d.keys())}"
    if "mode" not in d:
        return False, f"No mode field. Keys: {list(d.keys())}"
    return True, f"Mode={d.get('mode')}, Reply={len(d['reply'])} chars"

# ============================================================
# 6. GIT ENDPOINTS
# ============================================================
def t_git_status_valid_repo():
    """Git status on a valid repo should return branch + changes"""
    r = requests.post(f"{BASE}/git/status", json={"repo_path": r"C:\Users\kkt\OneDrive\Desktop\FYP New"}, timeout=15)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "branch" not in d:
        return False, f"No branch field. Keys: {list(d.keys())}"
    if "changes" not in d:
        return False, f"No changes field. Keys: {list(d.keys())}"
    return True, f"Branch={d['branch']}, Changes={len(d['changes'])}"

def t_git_status_invalid_repo():
    """Git status on non-repo should return error"""
    r = requests.post(f"{BASE}/git/status", json={"repo_path": r"C:\Windows\Temp"}, timeout=10)
    if r.status_code == 200:
        d = r.json()
        if d.get("branch"):
            return False, "Non-repo path returned valid branch — should error"
    return True, f"Correctly errored: status {r.status_code}"

def t_git_branches():
    """Git branches should list local and remote"""
    r = requests.post(f"{BASE}/git/branches", json={"repo_path": r"C:\Users\kkt\OneDrive\Desktop\FYP New"}, timeout=10)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "current" not in d:
        return False, f"No 'current' field. Keys: {list(d.keys())}"
    if "local" not in d:
        return False, f"No 'local' field. Keys: {list(d.keys())}"
    return True, f"Current={d['current']}, Local={d['local']}"

def t_git_log():
    """Git log should return commit history"""
    r = requests.post(f"{BASE}/git/log", json={"repo_path": r"C:\Users\kkt\OneDrive\Desktop\FYP New", "max_count": 5}, timeout=10)
    if r.status_code != 200:
        return False, f"Status {r.status_code}: {r.text[:200]}"
    d = r.json()
    if "commits" not in d and "entries" not in d and not isinstance(d, list):
        return False, f"Unexpected response shape. Keys: {list(d.keys()) if isinstance(d, dict) else 'list'}"
    return True, f"Log returned: {d.get('count', len(d.get('commits', d.get('entries', d))))} commit(s)"

# ============================================================
# 7. EDGE CASES / SECURITY
# ============================================================
def t_refactor_empty_code():
    """Refactoring empty code should return 400"""
    r = requests.post(f"{BASE}/refactor", json={"java_code": ""}, timeout=10)
    if r.status_code != 400:
        return False, f"Empty code should return 400, got {r.status_code}"
    return True, "400 returned"

def t_refactor_non_java():
    """Refactoring non-Java code should handle gracefully"""
    code = "def hello():\n    print('hello world')\n"
    r = requests.post(f"{BASE}/refactor", json={"java_code": code, "apply_all": True}, timeout=15)
    # Should either return 400/422 or return without crashing (200 with empty actions)
    if r.status_code >= 500:
        return False, f"Server error {r.status_code} on non-Java code — should handle gracefully"
    return True, f"Handled: status {r.status_code}"

def t_chat_empty_message():
    """Chat with empty message should return error"""
    r = requests.post(f"{BASE}/chat", json={"user_message": ""}, timeout=10)
    if r.status_code == 200:
        d = r.json()
        if d.get("reply"):
            return False, "Empty message should not produce a reply"
    return True, f"Handled: status {r.status_code}"

def t_check_errors_massive_code():
    """Error checking with very large code should not timeout"""
    code = "public class Big {\n" + "  public void m{}() {{ int x{} = {}; }}\n".format("{}", "{}", "{}").replace("{}", "{}") 
    # Build a large Java file
    methods = "\n".join([f"  public void method{i}() {{ int x = {i}; System.out.println(x); }}" for i in range(200)])
    code = f"public class BigClass {{\n{methods}\n}}"
    r = requests.post(f"{BASE}/check-errors", json={"java_code": code}, timeout=30)
    if r.status_code != 200:
        return False, f"Status {r.status_code} on large code"
    d = r.json()
    return True, f"Large code handled: {len(d.get('syntax_errors', []))} syntax, {len(d.get('warnings', []))} warnings"

def t_git_commit_no_message():
    """Git commit with empty message should fail"""
    r = requests.post(f"{BASE}/git/commit", json={"repo_path": r"C:\Users\kkt\OneDrive\Desktop\FYP New", "message": ""}, timeout=10)
    if r.status_code == 200:
        d = r.json()
        if d.get("hash"):
            return False, "Empty commit message should not succeed"
    return True, f"Handled: status {r.status_code}"

def t_error_check_multiple_errors():
    """Should detect MULTIPLE errors in one file, not just one"""
    code = '''public class Multi {
    public void a() {
        int x = 5
        String s = "hello"
        System.out.println(x)
        if (true) {
            int y = 10
        }
    }
}'''
    r = requests.post(f"{BASE}/check-errors", json={"java_code": code}, timeout=15)
    d = r.json()
    syntax = d.get("syntax_errors", [])
    runtime = d.get("runtime_errors", [])
    total = len(syntax) + len(runtime)
    # There are 4 missing semicolons — should catch at least 2
    if total < 2:
        return False, f"Only {total} error(s) found for 4 missing semicolons. Expected >=2. Errors: {[e.get('message') for e in syntax]}"
    return True, f"Found {total} errors"


# ============================================================
# RUN ALL TESTS
# ============================================================
print("=" * 60)
print("  CodeNova IDE — Black-Box Test Suite")
print("=" * 60)

tests = [
    t_health,
    t_error_check_missing_semicolon,
    t_error_check_missing_bracket,
    t_error_check_clean_code,
    t_error_check_empty_code,
    t_error_check_multiple_errors,
    t_refactor_basic,
    t_refactor_review,
    t_refactor_empty_code,
    t_refactor_non_java,
    t_analyze_basic,
    t_chat_simple,
    t_chat_with_code,
    t_chat_empty_message,
    t_git_status_valid_repo,
    t_git_status_invalid_repo,
    t_git_branches,
    t_git_log,
    t_git_commit_no_message,
    t_check_errors_massive_code,
]

for t in tests:
    test(t.__name__, t)

print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
print(f"  TOTAL: {len(RESULTS)} | PASS: {passed} | FAIL: {failed}")
print("=" * 60)

if failed > 0:
    print("\n  FAILED TESTS:")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"    ✗ {name}")
            print(f"      {detail}")
