# CodeNova AI - Standalone Desktop Application

A modern, VSCode-like IDE for intelligent Java code refactoring and analysis powered by AI.

## 🎯 Quick Start

### **Option 1: Double-Click (Recommended)**
```
CodeNova-Standalone.bat
```

### **Option 2: PowerShell**
- Right-click `CodeNova-Standalone.ps1`
- Select "Run with PowerShell"

Both will automatically:
1. ✅ Start the backend API server (port 8000)
2. ✅ Launch the desktop IDE application
3. ✅ Load sample Java files

---

## 📋 Requirements

Before running, ensure you have:

### **Python 3.8+**
```bash
python --version
# If not installed: https://python.org
```

### **Node.js 14+**
```bash
node --version
# If not installed: https://nodejs.org
```

### **One-time Setup** (first run only)
```bash
# Install Python dependencies
cd java_refactoring_engine
pip install fastapi uvicorn pydantic javalang

# Install Node dependencies for desktop app
cd ../desktop-app
npm install
```

---

## 🎨 Application Interface

The desktop IDE includes:

- **Left Sidebar**: File explorer with quick access
- **Editor**: Main code editing area with syntax highlighting
- **Toolbar**: Quick access buttons for refactoring actions
- **Output Panel**: Results from analysis, refactoring, error checking
- **Status Bar**: Real-time status updates and information

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+R` | Refactor with AI |
| `Ctrl+Shift+A` | Analyze Code |
| `Ctrl+Shift+E` | Check Errors |

---

## 🚀 Features

### **1. Refactor with AI**
Intelligently refactor Java code using multiple techniques:
- Extract Methods
- Reduce Nesting  
- Remove Duplicates
- Decompose Behavior
- Change Structure

### **2. Analyze Code**
Get instant analysis:
- Code smells detection
- Coupling & cohesion metrics
- Refactoring opportunities
- Quality metrics

### **3. Check Errors**
Identify issues:
- Syntax errors
- Runtime errors
- Static analysis warnings

---

## 📁 Project Structure

```
FYP New/
├── CodeNova-Standalone.bat      ← Double-click to run! 🎯
├── CodeNova-Standalone.ps1      ← Or right-click here
│
├── desktop-app/                 (Electron IDE)
│   ├── main.js                  (Main process)
│   ├── preload.js               (IPC & API bridge)
│   ├── index.html               (UI)
│   ├── package.json
│   └── node_modules/
│
├── java_refactoring_engine/     (Backend API)
│   ├── main.py                  (FastAPI server)
│   ├── refactoring_engine.py
│   ├── ast_parser.py
│   ├── error_checker.py
│   └── [other modules]
│
└── sample_java_files/           (Test examples)
    ├── PaymentService.java
    ├── OrderProcessor.java
    └── [more samples]
```

---

## 🔧 Manual Launch (Advanced)

### **Terminal 1 - Backend**
```bash
cd java_refactoring_engine
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Output should show:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### **Terminal 2 - Desktop App**
```bash
cd desktop-app
npm install      # First time only
npm start        # Launch Electron app
```

---

## 📊 API Reference

The backend exposes these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/refactor` | POST | Refactor Java code |
| `/analyze` | POST | Analyze code quality |
| `/check-errors` | POST | Find errors |
| `/health` | GET | Server status |
| `/docs` | GET | Swagger UI |

### **Example API Call**
```bash
curl -X POST http://127.0.0.1:8000/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "java_code": "public class MyClass { ... }",
    "apply_all": true,
    "selected_refactorings": null
  }'
```

---

## 🧪 Testing

### **Pre-loaded Samples**
Click "Sample 1" or "Sample 2" in the toolbar to load examples:
- `PaymentService.java` - Payment processing with complex logic
- `OrderProcessor.java` - Order processing with long methods

### **Quick Test Flow**
1. Click "Sample 1" to load example code
2. Click "Refactor" button (or press Ctrl+Shift+R)
3. View results in the Output panel
4. Try other actions (Analyze, Check Errors)

---

## 🐛 Troubleshooting

### **"Python not found"**
- Install Python 3.8+ from [python.org](https://python.org)
- During installation, check "Add Python to PATH"
- Restart your computer

### **"Node.js not found"**
- Install Node.js 14+ from [nodejs.org](https://nodejs.org)
- Restart your computer

### **"Port 8000 already in use"**
- Another application is using port 8000
- Solution: Close the other app OR modify port in backend code
- The launcher tries to auto-kill existing processes on port 8000

### **API calls failing**
- Check backend console: Should show "Application startup complete"
- Verify API is running: Visit `http://127.0.0.1:8000/docs` in browser
- Check desktop app console for errors (Ctrl+Shift+I)

### **Desktop app won't start**
- Run: `npm install` in the `desktop-app` folder
- Ensure Node.js is in system PATH
- Try running from PowerShell with admin rights

---

## 📝 Sample Java Files

The `sample_java_files/` folder contains examples to test refactoring:

- **PaymentService.java** - Complex conditional logic
- **OrderProcessor.java** - Long method with multiple responsibilities
- **DataAnalyzer.java** - Poorly organized data processing
- And many more...

---

## 🔍 Developer Tools

### **Open DevTools in Desktop App**
- Press `Ctrl+Shift+I` to open browser console
- View JavaScript errors and network activity
- Check preload.js IPC communication

### **Backend Debug Mode**
- Check the backend console for:
  - Request/response logs
  - Refactoring engine activity
  - Error messages

---

## 🎯 Next Steps

1. **Run the App**: Double-click `CodeNova-Standalone.bat`
2. **Load a Sample**: Click "Sample 1" button
3. **Try Refactoring**: Click "Refactor" or press Ctrl+Shift+R
4. **Explore Analysis**: Click "Analyze" to see metrics
5. **Check Errors**: Click "Errors" to find issues

---

## 📚 Additional Resources

- **FastAPI Docs**: http://127.0.0.1:8000/docs
- **Electron docs**: https://www.electronjs.org/docs
- **Python FastAPI**: https://fastapi.tiangolo.com/

---

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review console output from both backend and desktop app
3. Ensure all dependencies are installed
4. Try restarting both services

---

**Enjoy CodeNova AI! 🎉**

Transform your Java code with intelligent refactoring.
