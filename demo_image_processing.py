#!/usr/bin/env python3
"""
Demo script for image processing features in P_OCR PDF AI 2025
Shows before/after comparison of image enhancement
"""

import os
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import cv2

class ImageProcessor:
    """Replicated ImageProcessor class for demo"""
    
    @staticmethod
    def enhance_image(image: Image.Image) -> Image.Image:
        """Enhance image quality for better OCR"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Auto-level (improve brightness)
            image = ImageOps.autocontrast(image)
            
            return image
        except Exception as e:
            print(f"Cannot enhance image: {e}")
            return image
    
    @staticmethod
    def smart_crop(image: Image.Image) -> Image.Image:
        """Smart crop to remove unnecessary borders"""
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.width - x, w + 2 * padding)
                h = min(image.height - y, h + 2 * padding)
                
                cropped = image.crop((x, y, x + w, y + h))
                
                if w * h < 0.8 * image.width * image.height:
                    return cropped
            
            return image
        except Exception as e:
            print(f"Cannot smart crop: {e}")
            return image
    
    @staticmethod
    def resize_for_word(image: Image.Image, max_width: int = 800) -> Image.Image:
        """Resize image appropriately for Word document"""
        try:
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            return image
        except Exception as e:
            print(f"Cannot resize image: {e}")
            return image
    
    @staticmethod
    def process_image_for_word(image: Image.Image) -> Image.Image:
        """Complete image processing pipeline"""
        print("🔍 Processing image...")
        
        print("  1. Smart cropping...")
        image = ImageProcessor.smart_crop(image)
        
        print("  2. Enhancing quality...")
        image = ImageProcessor.enhance_image(image)
        
        print("  3. Resizing for Word...")
        image = ImageProcessor.resize_for_word(image)
        
        print("✅ Image processing complete!")
        return image

def demo_image_processing(input_path: str, output_dir: str = "demo_output"):
    """Demo image processing with before/after comparison"""
    
    if not os.path.exists(input_path):
        print(f"❌ Input image not found: {input_path}")
        return
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🖼️ Processing image: {input_path}")
    
    # Load original image
    original = Image.open(input_path)
    print(f"📏 Original size: {original.width}×{original.height}px")
    
    # Process image
    processor = ImageProcessor()
    processed = processor.process_image_for_word(original.copy())
    print(f"📏 Processed size: {processed.width}×{processed.height}px")
    
    # Save results
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    original_output = os.path.join(output_dir, f"{base_name}_original.png")
    processed_output = os.path.join(output_dir, f"{base_name}_processed.png")
    
    original.save(original_output, "PNG")
    processed.save(processed_output, "PNG")
    
    print(f"💾 Saved comparison:")
    print(f"   Original: {original_output}")
    print(f"   Processed: {processed_output}")
    
    # Calculate size reduction
    original_size = os.path.getsize(original_output)
    processed_size = os.path.getsize(processed_output)
    reduction = (1 - processed_size / original_size) * 100
    
    print(f"📊 File size comparison:")
    print(f"   Original: {original_size/1024:.1f} KB")
    print(f"   Processed: {processed_size/1024:.1f} KB")
    print(f"   Reduction: {reduction:.1f}%")

def create_sample_images():
    """Create sample images for demo if none exist"""
    samples_dir = "sample_images"
    os.makedirs(samples_dir, exist_ok=True)
    
    # Create a sample image with text and borders
    from PIL import ImageDraw, ImageFont
    
    # Sample 1: Document with borders
    img1 = Image.new('RGB', (1200, 800), color='white')
    draw = ImageDraw.Draw(img1)
    
    # Add border
    draw.rectangle([0, 0, 1199, 799], outline='gray', width=20)
    
    # Add some text (simulated document)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    draw.text((100, 100), "Sample Document", fill='black', font=font)
    draw.text((100, 200), "Mathematical Formula: x² + y² = z²", fill='black', font=font)
    draw.text((100, 300), "This image has borders that will be cropped", fill='black', font=font)
    
    sample1_path = os.path.join(samples_dir, "sample_document.png")
    img1.save(sample1_path)
    print(f"📄 Created sample: {sample1_path}")
    
    # Sample 2: Low contrast image
    img2 = Image.new('RGB', (800, 600), color='lightgray')
    draw2 = ImageDraw.Draw(img2)
    draw2.text((50, 50), "Low Contrast Text", fill='gray', font=font)
    draw2.text((50, 150), "Formula: ∫f(x)dx = F(x) + C", fill='darkgray', font=font)
    
    sample2_path = os.path.join(samples_dir, "low_contrast.png")
    img2.save(sample2_path)
    print(f"📄 Created sample: {sample2_path}")
    
    return [sample1_path, sample2_path]

def main():
    """Main demo function"""
    print("🚀 P_OCR PDF AI 2025 - Image Processing Demo")
    print("=" * 50)
    
    # Check if sample images exist, create if not
    sample_images = []
    if os.path.exists("sample_images"):
        sample_images = [
            os.path.join("sample_images", f) 
            for f in os.listdir("sample_images") 
            if f.endswith(('.png', '.jpg', '.jpeg'))
        ]
    
    if not sample_images:
        print("📸 No sample images found, creating demo samples...")
        sample_images = create_sample_images()
    
    # Process each sample
    for img_path in sample_images:
        print("\n" + "-" * 30)
        demo_image_processing(img_path)
    
    print("\n" + "=" * 50)
    print("✅ Demo complete! Check the 'demo_output' folder for results.")
    print("💡 The processed images show the improvements that will be applied")
    print("   to images extracted from PDFs before inserting into Word documents.")

if __name__ == "__main__":
    main()
