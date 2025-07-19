#!/usr/bin/env python3
"""
Quick syntax checker for app.py
"""

import ast
import sys

def check_syntax():
    """Check app.py syntax"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to parse
        ast.parse(content)
        print("✅ app.py syntax is valid!")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in app.py:")
        print(f"   Line {e.lineno}: {e.msg}")
        if e.text:
            print(f"   Code: {e.text.strip()}")
        return False
    except FileNotFoundError:
        print("❌ app.py not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if check_syntax():
        print("🚀 Ready to run: streamlit run app.py")
        sys.exit(0)
    else:
        print("🔧 Please fix syntax errors first")
        sys.exit(1)
