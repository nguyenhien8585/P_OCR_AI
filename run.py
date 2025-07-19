#!/usr/bin/env python3
"""
P_OCR PDF AI 2025 - Launcher Script
Quick start script for the OCR application
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if all required packages are installed"""
    print("🔍 Checking dependencies...")
    
    try:
        import streamlit
        import PIL
        import fitz
        import pdf2image
        import docx
        import requests
        print("✅ All Python packages installed")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def check_poppler():
    """Check if Poppler is installed"""
    print("🔍 Checking Poppler installation...")
    
    try:
        from pdf2image import convert_from_path
        # Try to convert a dummy PDF
        print("✅ Poppler is available")
        return True
    except Exception:
        print("❌ Poppler not found!")
        print("Installation instructions:")
        print("  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/")
        print("  macOS:   brew install poppler")
        print("  Ubuntu:  sudo apt-get install poppler-utils")
        return False

def setup_environment():
    """Setup environment variables if .env file exists"""
    env_file = Path(".env")
    if env_file.exists():
        print("📋 Loading environment variables from .env file...")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            print("✅ Environment variables loaded")
        except Exception as e:
            print(f"⚠️ Error loading .env file: {e}")
    else:
        print("💡 Tip: Create a .env file with your API keys (see .env.example)")

def test_apis():
    """Offer to test API configuration"""
    response = input("\n🧪 Test API configuration before starting? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        print("Running API tests...")
        try:
            subprocess.run([sys.executable, "test_apis.py"], check=True)
        except FileNotFoundError:
            print("❌ test_apis.py not found")
        except subprocess.CalledProcessError:
            print("❌ API test failed")
            return False
    
    return True

def main():
    """Main launcher function"""
    print("🚀 P_OCR PDF AI 2025 Launcher")
    print("=" * 40)
    
    # Check current directory
    if not Path("app.py").exists():
        print("❌ app.py not found in current directory!")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        print("\n📦 Installing dependencies...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          check=True)
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            sys.exit(1)
    
    # Check Poppler
    if not check_poppler():
        response = input("\nContinue without Poppler? (PDF features may not work) (y/N): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Test APIs
    if not test_apis():
        response = input("\nContinue despite API test issues? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            sys.exit(1)
    
    # Launch Streamlit
    print("\n🚀 Launching P_OCR PDF AI 2025...")
    print("📱 The application will open in your default browser")
    print("🛑 Press Ctrl+C to stop the application")
    print("=" * 40)
    
    try:
        # Start Streamlit
        env = os.environ.copy()
        env['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
        
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless", "true",
            "--server.port", "8501",
            "--server.address", "localhost"
        ], env=env)
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Open browser
        webbrowser.open("http://localhost:8501")
        
        # Wait for process
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping P_OCR PDF AI 2025...")
        process.terminate()
        print("✅ Application stopped successfully")
    
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
