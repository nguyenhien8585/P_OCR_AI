#!/usr/bin/env python3
"""
Debug script for P_OCR PDF AI 2025
Check for common issues and dependencies
"""

import sys
import importlib

def check_imports():
    """Check all required imports"""
    print("🔍 Checking imports...")
    
    required_modules = [
        'streamlit',
        'PIL',
        'fitz',
        'pdf2image', 
        'docx',
        'requests',
        'numpy'
    ]
    
    optional_modules = [
        'cv2'
    ]
    
    # Check required modules
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            return False
    
    # Check optional modules
    for module in optional_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} (optional)")
        except ImportError:
            print(f"⚠️ {module} (optional): Not available - some features disabled")
    
    return True

def check_app_syntax():
    """Check app.py syntax"""
    print("\n🔍 Checking app.py syntax...")
    
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to compile
        compile(content, 'app.py', 'exec')
        print("✅ app.py syntax is valid")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in app.py line {e.lineno}: {e.msg}")
        return False
    except FileNotFoundError:
        print("❌ app.py not found")
        return False

def check_classes():
    """Check if classes are properly defined"""
    print("\n🔍 Checking class definitions...")
    
    try:
        from app import ImageProcessor, OCRProcessor, WordExporter
        
        # Test ImageProcessor
        processor = ImageProcessor()
        print("✅ ImageProcessor")
        
        # Test OCRProcessor  
        ocr = OCRProcessor()
        print("✅ OCRProcessor")
        
        # Test WordExporter
        exporter = WordExporter()
        print("✅ WordExporter")
        
        return True
        
    except Exception as e:
        print(f"❌ Class definition error: {e}")
        return False

def check_methods():
    """Check critical methods"""
    print("\n🔍 Checking method signatures...")
    
    try:
        from app import OCRProcessor
        import inspect
        
        # Check extract_images_from_pdf method
        ocr = OCRProcessor()
        method = getattr(ocr, 'extract_images_from_pdf')
        sig = inspect.signature(method)
        
        print(f"✅ extract_images_from_pdf signature: {sig}")
        
        # Check if enhance parameter exists
        if 'enhance' in sig.parameters:
            print("✅ 'enhance' parameter found")
        else:
            print("❌ 'enhance' parameter missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Method check error: {e}")
        return False

def run_basic_test():
    """Run basic functionality test"""
    print("\n🧪 Running basic test...")
    
    try:
        from app import ImageProcessor
        from PIL import Image
        import io
        
        # Create test image
        test_img = Image.new('RGB', (100, 100), color='white')
        
        # Test image processing
        processor = ImageProcessor()
        
        # Test enhance
        enhanced = processor.enhance_image(test_img)
        print("✅ Image enhancement works")
        
        # Test resize
        resized = processor.resize_for_word(test_img)
        print("✅ Image resize works")
        
        # Test smart crop (may fail without OpenCV)
        try:
            cropped = processor.smart_crop(test_img)
            print("✅ Smart crop works")
        except Exception as e:
            print(f"⚠️ Smart crop failed (likely no OpenCV): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic test failed: {e}")
        return False

def main():
    """Main debug function"""
    print("🚀 P_OCR PDF AI 2025 Debug Tool")
    print("=" * 50)
    
    all_good = True
    
    # Run all checks
    all_good &= check_imports()
    all_good &= check_app_syntax() 
    all_good &= check_classes()
    all_good &= check_methods()
    all_good &= run_basic_test()
    
    print("\n" + "=" * 50)
    if all_good:
        print("🎉 All checks passed! App should work fine.")
        print("💡 Try running: streamlit run app.py")
    else:
        print("❌ Some issues found. Please fix them before running the app.")
        print("💡 Common solutions:")
        print("   - Install missing packages: pip install -r requirements.txt")
        print("   - Check app.py syntax carefully")
        print("   - Install OpenCV: pip install opencv-python")

if __name__ == "__main__":
    main()
