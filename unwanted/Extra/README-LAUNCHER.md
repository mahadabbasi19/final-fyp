# 🚀 CodeNova AI - Run Instructions

## Quick Start - Choose ONE Option Below

### **Option 1: Double-Click (Recommended - Windows)**
```
CodeNova-AI.bat
```
**Result:** Launches backend + VSCodium automatically

---

### **Option 2: Right-Click PowerShell (Windows)**
```
1. Right-click CodeNova-AI.ps1
2. Select "Run with PowerShell"
3. If blocked, run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
**Result:** Cleaner UI with colored output

---

### **Option 3: VBS Launcher (Minimized)**
```
CodeNova-AI.vbs
```
**Result:** Launches with minimal console windows

---

### **Option 4: Manual Terminal Launch**
```powershell
# Terminal 1 - Start Backend
cd "C:\Users\kkt\OneDrive\Desktop\FYP New\java_refactoring_engine"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Start VSCodium with Extension
cd "C:\Users\kkt\OneDrive\Desktop\FYP New\vscodium\vscode\extensions\codenova-logic"
code --extensionDevelopmentPath="." "../../.."
```

---

## 📋 What Happens When You Launch

✅ **Backend API starts** on `http://127.0.0.1:8000`  
✅ **VSCodium opens** with CodeNova extension loaded  
✅ **Sample Java files** loaded for testing  
✅ **Status messages** shown in console windows  

---

## 🎯 Test the Application

### In VSCodium:
1. Open any `.java` file (sample files are preloaded)
2. **Right-click** → select **"CodeNova: Refactor with AI"**
3. **OR** press **Ctrl+Shift+R**
4. See the refactoring suggestions appear

### Available Commands:
- `Ctrl+Shift+R` - Refactor with AI
- `Ctrl+Shift+A` - Analyze Code
- Right-click menu - All CodeNova options

### View API Docs:
- Visit: `http://127.0.0.1:8000/docs` in browser
- Shows all API endpoints and test interface

---

## 📁 File Structure

```
FYP New/
├── CodeNova-AI.bat          ← Double-click this! 🎯
├── CodeNova-AI.ps1          ← Or Right-click this
├── CodeNova-AI.vbs          ← Or run this
├── Create-Shortcut.vbs      ← Creates desktop shortcut
│
├── java_refactoring_engine/
│   ├── main.py              (FastAPI backend)
│   └── [other modules]
│
├── vscodium/
│   └── vscode/
│       └── extensions/
│           └── codenova-logic/
│               ├── src/     (TypeScript source)
│               └── dist/    (Compiled JavaScript)
│
└── sample_java_files/       (Test files)
    ├── PaymentService.java
    ├── OrderProcessingService.java
    └── [more examples]
```

---

## 🔧 Requirements

**Before running, make sure you have:**

1. **Python 3.8+** - [Download](https://python.org)
   ```bash
   python --version
   ```

2. **Node.js 14+** - [Download](https://nodejs.org)
   ```bash
   node --version
   ```

3. **Dependencies installed** (one-time setup):
   ```bash
   cd "java_refactoring_engine"
   pip install fastapi uvicorn pydantic javalang
   
   cd ../vscodium/vscode/extensions/codenova-logic
   npm install
   ```

---

## 🎨 Make It Even Easier - Create Desktop Shortcut

### Windows:
```bash
1. Right-click CodeNova-AI.bat
2. Send to → Desktop (create shortcut)
```

Or run:
```bash
Create-Shortcut.vbs
```

Then double-click the shortcut to launch!

---

## 📊 Backend API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/refactor` | POST | Refactor Java code |
| `/analyze` | POST | Analyze code quality |
| `/check-errors` | POST | Find errors |
| `/health` | GET | Server status |
| `/docs` | GET | Swagger UI (browser) |

---

## ⚠️ Troubleshooting

### "Python not found"
- Install Python from python.org
- Make sure to check "Add Python to PATH" during installation

### "Node.js not found"
- Install Node.js from nodejs.org
- Restart your terminal

### "Port 8000 already in use"
- Close other applications using port 8000
- Or modify the port in CodeNova-AI.bat

### Extension not loading
- Make sure `npm install` was run in the extension folder
- Check VSCodium debug console (View → Debug Console)

### API calls failing
- Verify backend console shows "Application startup complete"
- Check backend is running on http://127.0.0.1:8000

---

## 🚀 Usage Tips

1. **Keep both windows open** - Backend and VSCodium
2. **Check console for errors** - Helps with debugging
3. **Try different Java files** - See various refactoring scenarios
4. **View API docs** - Learn about all available options
5. **Check the examples** - sample_java_files/ has good test cases

---

## 📝 What CodeNova AI Can Do

✨ **Extract Methods** - Break down long functions  
✨ **Reduce Nesting** - Simplify complex conditionals  
✨ **Remove Duplicates** - Consolidate repeated code  
✨ **Decompose Behavior** - Separate concerns  
✨ **Change Structure** - Refactor class hierarchies  
✨ **Real-time Analysis** - Get instant feedback  

---

## 🎯 Next Steps

1. **Try the Basic Sample:**
   - Open `sample_java_files/PaymentService.java`
   - Press Ctrl+Shift+R or right-click

2. **Open Your Own Code:**
   - File → Open Folder
   - Select any folder with Java files
   - Run refactoring commands

3. **Check the Results:**
   - See diff view with suggestions
   - View metrics and analysis
   - Apply refactoring to your code

---

**Enjoy CodeNova AI! 🎉**

For issues or questions, check the backend and extension logs in the console windows.
