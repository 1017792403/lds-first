#!/usr/bin/env python3
"""Stock Analyzer Launcher"""
import os
import sys
import subprocess

proj_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(proj_dir)
sys.path.insert(0, proj_dir)

try:
    import flask
except ImportError:
    print("Installing Flask...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "-q"])
    print("Done.")

from stock_analyzer.app import main
main()
