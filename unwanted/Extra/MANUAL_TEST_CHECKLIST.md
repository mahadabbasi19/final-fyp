# 🧪 10-Minute Manual Test Checklist
## Java Refactoring Engine - Complete Testing Guide

**Time Required:** 10 minutes  
**Test Date:** _______________  
**Tester Name:** _______________

---

## 🚀 Pre-Test Setup (30 seconds)

1. Open terminal in project folder
2. Run the application:
   ```
   python run_app.py
   ```
3. ✅ Application launches without errors: [ ]

---

## 📁 PART 1: File Explorer (1 minute)

### Test 1.1: Open Folder
- [ ] Click **"Open"** button in Explorer panel
- [ ] Navigate to `sample_java_files` folder
- [ ] Select the folder
- **Expected:** Folder contents appear in tree view

### Test 1.2: File Navigation  
- [ ] Click on any `.java` file (e.g., `Calculator.java`)
- **Expected:** File content loads in editor

### Test 1.3: Create New File
- [ ] Click the **"+"** button
- [ ] Enter filename: `TestManual.java`
- **Expected:** New file created and opened

---

## ✏️ PART 2: Code Editor (1.5 minutes)

### Test 2.1: Syntax Highlighting
- [ ] Open `Calculator.java`
- **Expected:** Keywords colored (public, class, int, etc.)

### Test 2.2: Line Numbers
- [ ] Check left side of editor
- **Expected:** Line numbers displayed

### Test 2.3: Edit Code
- [ ] Type something in the editor
- [ ] Press `Ctrl+S` to save
- **Expected:** File saved, no errors

### Test 2.4: Font & Readability
- [ ] Check if code is readable
- **Expected:** Monospace font, good contrast

---

## 🔴 PART 3: Error Detection (1.5 minutes)

### Test 3.1: Open Error Sample
- [ ] Open `ErrorTestSample.java`
- [ ] Click **"Error Panel"** tab at bottom
- **Expected:** Errors detected and listed

### Test 3.2: Real-time Error Detection
- [ ] In any Java file, inside a method, type: `int x = "hello";`
- [ ] Wait 1-2 seconds for the error checker
- **Expected:** Error appears: "Type mismatch: cannot assign String to int"

### Test 3.3: Error Navigation
- [ ] Click on an error in Error Panel
- **Expected:** Cursor jumps to error location

### Test 3.4: Fix Errors
- [ ] Delete the bad code you typed
- **Expected:** Error disappears from panel

---

## 🔧 PART 4: Refactoring Operations (3 minutes)

### Test 4.1: Extract Method
- [ ] Open `Calculator.java`
- [ ] Select multiple lines of code
- [ ] In **Refactoring Engine** tab, click **"Extract Method"**
- [ ] Enter method name: `extractedMethod`
- **Expected:** Selected code moved to new method

### Test 4.2: Rename Variable
- [ ] Find a variable in the code
- [ ] Click **"Rename"** button
- [ ] Enter new name
- **Expected:** Variable renamed throughout code

### Test 4.3: Rename Method
- [ ] Click on a method name
- [ ] Use Rename feature
- **Expected:** Method name updated everywhere

### Test 4.4: Decompose Behavior
- [ ] Open `DecomposeBehaviorDemo.java`
- [ ] Find a long method
- [ ] Click **"Decompose Behavior"**
- **Expected:** Method split into smaller methods

### Test 4.5: Inline Variable
- [ ] Find a simple variable assignment
- [ ] Click **"Inline Variable"**
- **Expected:** Variable replaced with its value

---

## 📊 PART 5: Code Metrics (1 minute)

### Test 5.1: View Metrics
- [ ] Open `CouplingCohesionDemo.java`
- [ ] Click **"Metrics"** tab at bottom
- [ ] Click **"Analyze"** or similar button
- **Expected:** Metrics displayed (LOC, Complexity, etc.)

### Test 5.2: Coupling & Cohesion
- [ ] Check for Coupling score
- [ ] Check for Cohesion score
- **Expected:** Numeric values displayed

### Test 5.3: Visualization
- [ ] Look for charts/graphs option
- [ ] Click to generate visualization
- **Expected:** Visual representation appears

---

## 🔄 PART 6: History & Undo (1 minute)

### Test 6.1: Perform a Refactoring
- [ ] Do any refactoring operation

### Test 6.2: Undo
- [ ] Press `Ctrl+Z` or click Undo
- **Expected:** Refactoring reversed

### Test 6.3: Redo
- [ ] Press `Ctrl+Y` or click Redo
- **Expected:** Refactoring re-applied

### Test 6.4: History Log
- [ ] Look for History panel/tab
- [ ] Check recent operations
- **Expected:** Operations listed with timestamps

---

## 💬 PART 7: AI Chat (Optional - 30 seconds)

### Test 7.1: AI Panel Visibility
- [ ] Find AI Chat panel (right side)
- **Expected:** Chat interface visible

### Test 7.2: Send Message
- [ ] Type: "Explain this code"
- [ ] Press Enter/Send
- **Expected:** Response generated (if API configured)

---

## 🖥️ PART 8: Terminal (30 seconds)

### Test 8.1: Terminal Tab
- [ ] Click **"Terminal"** tab at bottom
- **Expected:** Terminal interface appears

### Test 8.2: Command Execution
- [ ] Type: `dir` (Windows) or `ls` (Mac/Linux)
- **Expected:** Shows directory contents

---

## 📝 Test Results Summary

| Section | Pass | Fail | Notes |
|---------|------|------|-------|
| File Explorer | | | |
| Code Editor | | | |
| Error Detection | | | |
| Refactoring | | | |
| Code Metrics | | | |
| History/Undo | | | |
| AI Chat | | | |
| Terminal | | | |

---

## 🐛 Issues Found

| # | Description | Severity (High/Med/Low) |
|---|-------------|------------------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

---

## 📋 Quick Test Files Reference

| File | Best for Testing |
|------|-----------------|
| `Calculator.java` | Basic refactoring (Extract, Rename) |
| `ErrorTestSample.java` | Error detection |
| `DecomposeBehaviorDemo.java` | Decompose behavior |
| `CouplingCohesionDemo.java` | Metrics analysis |
| `PaymentService.java` | Complex refactoring |
| `UserManagementSystem.java` | Large file handling |

---

## ✅ Final Checklist

- [ ] All major features tested
- [ ] No crashes during testing
- [ ] UI responsive throughout
- [ ] Files saved correctly
- [ ] Undo/Redo working

**Overall Status:** ⬜ PASS / ⬜ FAIL

**Comments:**
_____________________________________________
_____________________________________________
_____________________________________________

---

*Generated for Java Refactoring Engine FYP Project*
