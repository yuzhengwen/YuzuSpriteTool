"""Launcher for Yuzu Sprite Tool. The application lives in the sprite_tool package.

Run with run.bat, or:  .venv\\Scripts\\python.exe main.py
"""
import sys

from sprite_tool.app import main

if __name__ == "__main__":
    sys.exit(main())
