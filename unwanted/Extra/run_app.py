"""
Java Refactoring Engine - Main Entry Point
==========================================
Run this file to start the Java Refactoring Engine GUI.
"""

import sys
import os

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from java_refactoring_engine.gui import main

if __name__ == "__main__":
    main()
