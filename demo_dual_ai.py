#!/usr/bin/env python3
"""
Demo script for Dual AI Models in P_OCR PDF AI 2025 v2.0
Shows how OCR Model and Image Analysis Model work together
"""

import os
import json
from PIL import Image, ImageDraw, ImageFont

def create_demo_scenario():
    """Create demo files to showcase dual AI functionality"""
    print("🎬 Creating Demo Scenario for Dual AI Models")
    print("=" * 50)
    
    # Create demo directory
    demo_dir = "dual_ai_demo"
    os.makedirs(demo_dir, exist_ok=True)
    
    # Create sample images with different content types
    demo_images = []
    
    # 1. Mathematical Formula Image
    print("📐 Creating mathematical formula image...")
    math_img = Image.new('RGB', (600, 200), color='white')
    draw = ImageDraw.Draw(math_img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((50, 50), "Pythagorean Theorem:", fill='black', font=font)
    draw.text((50, 100), "a² + b² = c²", fill='blue', font=font)
    
    math_path = os.path.join(demo_dir, "math_formula.png")
    math_img.save(math_path)
    demo_images.append(("math_formula.png", "formula", "Mathematical formula"))
    
    # 2. Business Chart Image
    print("📊 Creating business chart image...")
    chart_img = Image.new('RGB', (500, 300), color='white')
    draw2 = ImageDraw.Draw(chart_img)
    
    # Simple bar chart simulation
    draw2.text((50, 20), "Sales Revenue Q1-Q4", fill='black', font=font)
    draw2.rectangle([100, 100, 150, 200], fill='blue')  # Q1
    draw2.rectangle([170, 80, 220, 200], fill='green')   # Q2
    draw2.rectangle([240, 120, 290, 200], fill='red')    # Q3
    draw2.rectangle([310, 60, 360, 200], fill='orange')  # Q4
    
    draw2.text((110, 210), "Q1", fill='black')
    draw2.text((180, 210), "Q2", fill='black')
    draw2.text((250, 210), "Q3", fill='black')
    draw2.text((320, 210), "Q4", fill='black')
    
    chart_path = os.path.join(demo_dir, "business_chart.png")
    chart_img.save(chart_path)
    demo_images.append(("business_chart.png", "chart", "Business sales chart"))
    
    # 3. Technical Diagram
    print("🔧 Creating technical diagram...")
    diagram_img = Image.new('RGB', (400, 350), color='white')
    draw3 = ImageDraw.Draw(diagram_img)
    
    # Simple system diagram
    draw3.text((50, 20), "System Architecture", fill='black', font=font)
    draw3.rectangle([50, 60, 150, 100], outline='black', width=2)
    draw3.text((70, 75), "Frontend", fill='black')
    
    draw3.rectangle([200, 60, 300, 100], outline='black', width=2)
    draw3.text((220, 75), "Backend", fill='black')
    
    draw3.rectangle([125, 150, 225, 190], outline='black', width=2)
    draw3.text((145, 165), "Database", fill='black')
    
    # Arrows
    draw3.line([150, 80, 200, 80], fill='black', width=2)  # Frontend -> Backend
    draw3.line([250, 100, 175, 150], fill='black', width=2)  # Backend -> Database
    
    diagram_path = os.path.join(demo_dir, "tech_diagram.png")
    diagram_img.save(diagram_path)
    demo_images.append(("tech_diagram.png", "diagram", "Technical system diagram"))
    
    # 4. Table/Data Image
    print("📋 Creating data table image...")
    table_img = Image.new('RGB', (450, 250), color='white')
    draw4 = ImageDraw.Draw(table_img)
    
    draw4.text((50, 20), "Employee Performance Data", fill='black', font=font)
    
    # Table headers
    draw4.text((50, 60), "Name", fill='black', font=font)
    draw4.text((150, 60), "Department", fill='black', font=font)
    draw4.text((280, 60), "Score", fill='black', font=font)
    
    # Table data
    employees = [
        ("John Doe", "Engineering", "95"),
        ("Jane Smith", "Marketing", "88"),
        ("Bob Johnson", "Sales", "92")
    ]
    
    for i, (name, dept, score) in enumerate(employees):
        y = 90 + i * 30
        draw4.text((50, y), name, fill='black')
        draw4.text((150, y), dept, fill='black')
        draw4.text((280, y), score, fill='black')
    
    table_path = os.path.join(demo_dir, "data_table.png")
    table_img.save(table_path)
    demo_images.append(("data_table.png", "table", "Employee performance data"))
    
    print(f"✅ Created {len(demo_images)} demo images in '{demo_dir}/'")
    return demo_dir, demo_images

def simulate_dual_ai_analysis(demo_images):
    """Simulate how dual AI models would analyze the images"""
    print("\n🤖 Simulating Dual AI Analysis")
    print("=" * 50)
    
    # Simulate OCR Model results
    ocr_results = {
        "math_formula.png": "Pythagorean Theorem: a² + b² = c²",
        "business_chart.png": "Sales Revenue Q1-Q4 with quarterly performance bars",
        "tech_diagram.png": "System Architecture: Frontend connects to Backend, Backend connects to Database",
        "data_table.png": "Employee Performance Data: John Doe Engineering 95, Jane Smith Marketing 88, Bob Johnson Sales 92"
    }
    
    # Simulate Image Analysis Model results
    image_analyses = {
        "math_formula.png": {
            "description": "Biểu diễn định lý Pythagoras với công thức toán học a² + b² = c²",
            "category": "formula",
            "placement_hint": "Nên chèn sau đoạn văn bản giải thích về định lý Pythagoras hoặc hình học",
            "related_keywords": ["pythagorean", "theorem", "mathematics", "geometry", "formula"],
            "content_type": "mathematical"
        },
        "business_chart.png": {
            "description": "Biểu đồ cột thể hiện doanh thu bán hàng theo quý từ Q1 đến Q4",
            "category": "chart", 
            "placement_hint": "Nên chèn trong phần phân tích kinh doanh hoặc báo cáo tài chính",
            "related_keywords": ["sales", "revenue", "quarterly", "business", "performance"],
            "content_type": "business"
        },
        "tech_diagram.png": {
            "description": "Sơ đồ kiến trúc hệ thống với Frontend, Backend và Database",
            "category": "diagram",
            "placement_hint": "Nên chèn trong phần mô tả kiến trúc kỹ thuật hoặc thiết kế hệ thống",
            "related_keywords": ["system", "architecture", "frontend", "backend", "database"],
            "content_type": "scientific"
        },
        "data_table.png": {
            "description": "Bảng dữ liệu hiệu suất nhân viên với tên, phòng ban và điểm số",
            "category": "table",
            "placement_hint": "Nên chèn trong phần báo cáo nhân sự hoặc đánh giá hiệu suất",
            "related_keywords": ["employee", "performance", "data", "evaluation", "HR"],
            "content_type": "business"
        }
    }
    
    print("📝 OCR Model Results (Text Extraction):")
    for filename, text in ocr_results.items():
        print(f"   {filename}: {text}")
    
    print("\n🖼️ Image Analysis Model Results:")
    for filename, analysis in image_analyses.items():
        print(f"   📄 {filename}:")
        print(f"      Category: {analysis['category']}")
        print(f"      Description: {analysis['description']}")
        print(f"      Placement Hint: {analysis['placement_hint']}")
        print(f"      Keywords: {', '.join(analysis['related_keywords'])}")
        print()
    
    return ocr_results, image_analyses

def simulate_smart_positioning(ocr_results, image_analyses):
    """Simulate smart positioning logic"""
    print("🎯 Simulating Smart Positioning Logic")
    print("=" * 50)
    
    # Sample document text
    sample_text = """
    Trong tài liệu này, chúng ta sẽ tìm hiểu về các khái niệm toán học cơ bản.
    
    Định lý Pythagoras là một trong những định lý quan trọng nhất trong hình học.
    Định lý này áp dụng cho tam giác vuông và mô tả mối quan hệ giữa các cạnh.
    
    Chuyển sang phần kinh doanh, chúng ta cần phân tích doanh thu theo quý.
    Báo cáo sales revenue cho thấy xu hướng tăng trưởng trong năm qua.
    Quarterly performance là chỉ số quan trọng để đánh giá hiệu quả kinh doanh.
    
    Về mặt kỹ thuật, system architecture của chúng ta bao gồm nhiều thành phần.
    Frontend và backend cần kết nối chặt chẽ với database để đảm bảo hiệu suất.
    
    Cuối cùng, employee performance data cho thấy mức độ hiệu quả của đội ngũ.
    Việc evaluation định kỳ giúp cải thiện HR policies và quy trình làm việc.
    """
    
    paragraphs = [p.strip() for p in sample_text.split('\n') if p.strip()]
    
    print("📝 Document Paragraphs:")
    for i, para in enumerate(paragraphs, 1):
        print(f"   {i}. {para}")
    
    print("\n🤖 Smart Positioning Analysis:")
    
    positioning_results = []
    
    for filename, analysis in image_analyses.items():
        print(f"\n🖼️ {filename} ({analysis['category']}):")
        
        keywords = analysis['related_keywords']
        best_position = None
        best_score = 0
        
        for i, para in enumerate(paragraphs):
            para_lower = para.lower()
            score = sum(1 for keyword in keywords if keyword.lower() in para_lower)
            
            # Category-specific bonus scoring
            if analysis['category'] == 'formula' and ('định lý' in para_lower or 'toán học' in para_lower):
                score += 2
            elif analysis['category'] == 'chart' and ('doanh thu' in para_lower or 'kinh doanh' in para_lower):
                score += 2
            elif analysis['category'] == 'diagram' and ('hệ thống' in para_lower or 'kỹ thuật' in para_lower):
                score += 2
            elif analysis['category'] == 'table' and ('nhân viên' in para_lower or 'hiệu suất' in para_lower):
                score += 2
            
            if score > best_score:
                best_score = score
                best_position = i + 1
            
            if score > 0:
                print(f"      Paragraph {i+1}: Score {score} - {para[:50]}...")
        
        if best_position:
            print(f"   ✅ Best Position: After paragraph {best_position} (Score: {best_score})")
            positioning_results.append((filename, best_position, best_score))
        else:
            print(f"   ⚠️ No optimal position found - will place at end")
            positioning_results.append((filename, len(paragraphs) + 1, 0))
    
    return positioning_results

def generate_demo_report(demo_dir, positioning_results):
    """Generate a demo report showing the results"""
    print("\n📄 Generating Demo Report")
    print("=" * 50)
    
    report_path = os.path.join(demo_dir, "dual_ai_demo_report.md")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# P_OCR PDF AI 2025 v2.0 - Dual AI Demo Report\n\n")
        f.write("## 🎯 Demo Overview\n\n")
        f.write("This demo showcases how dual AI models work together:\n")
        f.write("- **OCR Model**: Extracts text content from images\n")
        f.write("- **Image Analysis Model**: Analyzes image content and determines optimal positioning\n\n")
        
        f.write("## 🤖 AI Models Configuration\n\n")
        f.write("| Purpose | Model | Responsibility |\n")
        f.write("|---------|-------|----------------|\n")
        f.write("| Text Extraction | Gemini 2.0 Flash | OCR from images and PDFs |\n")
        f.write("| Image Analysis | Mistral Small | Content analysis and positioning |\n\n")
        
        f.write("## 📊 Smart Positioning Results\n\n")
        for filename, position, score in positioning_results:
            f.write(f"### {filename}\n")
            f.write(f"- **Optimal Position**: After paragraph {position}\n")
            f.write(f"- **Confidence Score**: {score}\n")
            f.write(f"- **Reasoning**: AI detected content relevance based on keywords and context\n\n")
        
        f.write("## ✨ Benefits of Dual AI Approach\n\n")
        f.write("1. **Specialized Performance**: Each model optimized for specific tasks\n")
        f.write("2. **Better Accuracy**: OCR and analysis happen independently\n")
        f.write("3. **Smart Positioning**: Content-aware image placement\n")
        f.write("4. **Flexible Configuration**: Can use different model combinations\n")
        f.write("5. **Redundancy**: If one model fails, the other can still work\n\n")
        
        f.write("## 🎉 Conclusion\n\n")
        f.write("The dual AI approach in P_OCR PDF AI 2025 v2.0 provides:\n")
        f.write("- Superior text extraction accuracy\n")
        f.write("- Intelligent image content analysis\n") 
        f.write("- Context-aware document generation\n")
        f.write("- Professional Word output with smart positioning\n")
    
    print(f"✅ Demo report saved to: {report_path}")

def main():
    """Main demo function"""
    print("🚀 P_OCR PDF AI 2025 v2.0 - Dual AI Models Demo")
    print("=" * 60)
    
    # Create demo scenario
    demo_dir, demo_images = create_demo_scenario()
    
    # Simulate dual AI analysis
    ocr_results, image_analyses = simulate_dual_ai_analysis(demo_images)
    
    # Simulate smart positioning
    positioning_results = simulate_smart_positioning(ocr_results, image_analyses)
    
    # Generate report
    generate_demo_report(demo_dir, positioning_results)
    
    print("\n" + "=" * 60)
    print("🎉 Dual AI Demo Complete!")
    print(f"📁 Demo files created in: {demo_dir}/")
    print("💡 This demonstrates how P_OCR v2.0 uses dual AI models for:")
    print("   - Specialized OCR processing")
    print("   - Intelligent image analysis")
    print("   - Smart content positioning")
    print("   - Professional document generation")
    print("\n🚀 Try the real app: streamlit run app.py")

if __name__ == "__main__":
    main()
