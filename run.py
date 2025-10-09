#!/usr/bin/env python3
"""
Document Processing Suite Launcher
Simple launcher script for the unified document processor
"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from document_processor_gui import main
    
    if __name__ == "__main__":
        print("Starting Document Processing Suite...")
        main()

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("\nPlease ensure you have installed all required dependencies:")
    print("pip install -r requirements.txt")
    sys.exit(1)
    
except Exception as e:
    print(f"Error starting application: {e}")
    sys.exit(1)
