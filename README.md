# Java Refactoring Engine

A Python-based GUI application for analyzing, refactoring, and improving Java source code quality.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

---

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation Guide](#-installation-guide)
  - [Step 1: Install Python](#step-1-install-python)
  - [Step 2: Verify Python Installation](#step-2-verify-python-installation)
  - [Step 3: Download the Project](#step-3-download-the-project)
  - [Step 4: Install Dependencies](#step-4-install-dependencies)
- [Running the Application](#-running-the-application)
- [Project Structure](#-project-structure)
- [Usage Guide](#-usage-guide)
- [Sample Files](#-sample-files)
- [Troubleshooting](#-troubleshooting)
- [Contributors](#-contributors)

---

## ✨ Features

- **Code Analysis**: Analyze Java source code for potential issues
- **Error Detection**: Detect syntax errors and common coding mistakes
- **Refactoring Operations**: 
  - Extract Method
  - Rename Variable/Method/Class
  - Decompose Behavior
  - And more...
- **Code Metrics**: Calculate coupling, cohesion, and other code quality metrics
- **History Tracking**: Track all refactoring changes with undo/redo support
- **Modern GUI**: Clean and intuitive user interface built with CustomTkinter

---

## 📌 Prerequisites

Before starting, ensure you have the following:

- **Operating System**: Windows 10/11, macOS, or Linux
- **Internet Connection**: Required for downloading Python and libraries
- **Administrator Access**: May be required for installation on some systems

---

## 🔧 Installation Guide

### Step 1: Install Python

#### For Windows:

1. **Download Python**
   - Go to the official Python website: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - Click on **"Download Python 3.12.x"** (or the latest version)
   - The download will start automatically

2. **Run the Installer**
   - Locate the downloaded file (usually in `Downloads` folder)
   - Double-click `python-3.12.x-amd64.exe` to run the installer

3. **IMPORTANT Installation Options**
   - ✅ **Check the box "Add python.exe to PATH"** (This is crucial!)
   - ✅ Check "Use admin privileges when installing py.exe"
   - Click **"Install Now"**

   ![Python Installation](https://docs.python.org/3/_images/win_installer.png)

4. **Complete Installation**
   - Wait for the installation to complete
   - Click **"Close"** when finished

#### For macOS:

1. Download Python from [https://www.python.org/downloads/macos/](https://www.python.org/downloads/macos/)
2. Open the downloaded `.pkg` file
3. Follow the installation wizard
4. Python will be installed to `/usr/local/bin/python3`

#### For Linux (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk
```

---

### Step 2: Verify Python Installation

Open a terminal/command prompt and run these commands:

#### Windows (Command Prompt or PowerShell):

```cmd
python --version
```

Expected output: `Python 3.12.x` (or your installed version)

```cmd
pip --version
```

Expected output: `pip 24.x.x from ...`

#### macOS/Linux:

```bash
python3 --version
pip3 --version
```

> ⚠️ **If you get "python is not recognized"**: Python was not added to PATH. Reinstall Python and ensure you check "Add python.exe to PATH".

---

### Step 3: Download the Project

#### Option A: Clone from Git (if using version control)

```cmd
git clone <repository-url>
cd "FYP New"
```

#### Option B: Download as ZIP

1. Download the project ZIP file
2. Extract to a location (e.g., `C:\Users\YourName\Desktop\FYP New`)
3. Open Command Prompt/Terminal
4. Navigate to the project folder:

```cmd
cd "C:\Users\YourName\Desktop\FYP New"
```

---

### Step 4: Install Dependencies

#### Windows:

Open **Command Prompt** or **PowerShell** and run:

```cmd
# Navigate to project directory
cd "C:\Users\YourName\Desktop\FYP New"

# Install all required libraries
pip install -r requirements.txt
```

#### macOS/Linux:

```bash
# Navigate to project directory
cd ~/Desktop/FYP\ New

# Install all required libraries
pip3 install -r requirements.txt
```

#### Manual Installation (if requirements.txt fails):

```cmd
pip install customtkinter>=5.2.0
pip install javalang>=0.13.0
```

---

## 🚀 Running the Application

### Method 1: Using Command Line (Recommended)

#### Windows:

```cmd
cd "C:\Users\YourName\Desktop\FYP New"
python run_app.py
```

#### macOS/Linux:

```bash
cd ~/Desktop/FYP\ New
python3 run_app.py
```

### Method 2: Double-Click (Windows)

1. Navigate to the project folder
2. Double-click on `run_app.py`
3. The application will launch

### Method 3: Using VS Code

1. Open VS Code
2. Open the project folder (`File > Open Folder`)
3. Open `run_app.py`
4. Press `F5` or click **Run > Run Without Debugging**

---

## 📁 Project Structure

```
FYP New/
│
├── run_app.py                    # Main entry point - RUN THIS FILE
├── requirements.txt              # Python dependencies
├── README.md                     # This file
│
├── java_refactoring_engine/      # Main application package
│   ├── __init__.py              # Package initializer
│   ├── gui.py                   # Graphical User Interface
│   ├── ast_parser.py            # Java Abstract Syntax Tree parser
│   ├── refactoring_engine.py    # Core refactoring operations
│   ├── error_checker.py         # Error detection module
│   ├── metrics.py               # Code metrics calculator
│   └── history.py               # Undo/Redo history management
│
├── sample_java_files/            # Example Java files for testing
│   ├── PaymentService.java
│   ├── UserManagementSystem.java
│   ├── OrderProcessingService.java
│   ├── DataAnalyzer.java
│   └── ... (more sample files)
│
└── test_*.py                     # Unit test files
```

---

## 📖 Usage Guide

### Loading a Java File

1. Launch the application using `python run_app.py`
2. Click **"Open File"** or use `Ctrl+O`
3. Browse and select a `.java` file
4. The file content will appear in the editor

### Performing Refactoring

1. Load a Java file
2. Select the code you want to refactor
3. Choose a refactoring operation from the menu:
   - **Extract Method**: Extract selected code into a new method
   - **Rename**: Rename variables, methods, or classes
   - **Decompose Behavior**: Break down complex methods
4. Follow the prompts to complete the refactoring
5. Review the changes in the editor

### Analyzing Code

1. Load a Java file
2. Click **"Analyze"** to check for:
   - Syntax errors
   - Code quality issues
   - Coupling and cohesion metrics

### Saving Changes

1. After refactoring, click **"Save"** or use `Ctrl+S`
2. Choose the save location
3. Your refactored code will be saved

---

## 📂 Sample Files

The `sample_java_files/` folder contains example Java files you can use to test the application:

| File | Description |
|------|-------------|
| `PaymentService.java` | Payment processing service |
| `UserManagementSystem.java` | User management functionality |
| `OrderProcessingService.java` | Order processing logic |
| `DataAnalyzer.java` | Data analysis utilities |
| `DecomposeBehaviorDemo.java` | Demo for behavior decomposition |
| `CouplingCohesionDemo.java` | Demo for metrics analysis |

---

## ❓ Troubleshooting

### Common Issues and Solutions

#### 1. "python is not recognized as an internal or external command"

**Solution**: Python is not in your PATH.
- Reinstall Python and check **"Add python.exe to PATH"**
- Or add Python manually to PATH:
  1. Search "Environment Variables" in Windows
  2. Edit "Path" under System Variables
  3. Add `C:\Users\YourName\AppData\Local\Programs\Python\Python312\`
  4. Add `C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts\`

#### 2. "No module named 'customtkinter'"

**Solution**: Install the required packages:
```cmd
pip install customtkinter javalang
```

#### 3. "No module named 'tkinter'"

**Solution** (Linux):
```bash
sudo apt-get install python3-tk
```

**Solution** (Windows): Reinstall Python and ensure "tcl/tk and IDLE" is checked.

#### 4. "ModuleNotFoundError: No module named 'java_refactoring_engine'"

**Solution**: Run from the project directory:
```cmd
cd "C:\Users\YourName\Desktop\FYP New"
python run_app.py
```

#### 5. Application window doesn't appear

**Solution**: 
- Ensure you're running `run_app.py`, not other files
- Check if any error messages appear in the terminal
- Try running with `python -u run_app.py` for unbuffered output

#### 6. "Permission denied" error

**Solution** (Windows): Run Command Prompt as Administrator
**Solution** (macOS/Linux): Use `sudo pip3 install -r requirements.txt`

---

## 🔄 Quick Start Commands Summary

```cmd
# 1. Check Python installation
python --version

# 2. Navigate to project
cd "C:\Users\YourName\Desktop\FYP New"

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python run_app.py
```

---

## 🧪 Running Tests

To run the test suite:

```cmd
# Run all tests
python -m pytest

# Run specific test file
python test_all_files.py
python test_payment_service.py
```

---

## 💻 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8+ | 3.10+ |
| RAM | 2 GB | 4 GB |
| Disk Space | 100 MB | 500 MB |
| Display | 1024x768 | 1920x1080 |

---

## 👥 Contributors

- [Add your team member names here]

---

## 📄 License

This project is developed as part of a Final Year Project (FYP).

---

## 📞 Support

If you encounter any issues:
1. Check the Troubleshooting section above
2. Contact the project team
3. Create an issue in the project repository

---

**Last Updated**: December 2024
