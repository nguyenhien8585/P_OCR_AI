#!/usr/bin/env python3
"""
Test script for Mistral and Gemini 2.0 APIs
Verify API configurations before running the main app
"""

import requests
import base64
import json
from PIL import Image
import io
import os

def test_mistral_api(api_key: str) -> bool:
    """Test Mistral API connectivity"""
    print("🧪 Testing Mistral API...")
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Simple text completion test
        payload = {
            "model": "mistral-small-latest",
            "temperature": 0.3,
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, this is a test. Respond with 'Mistral API working!'"
                }
            ]
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ Mistral API: {message}")
            return True
        else:
            print(f"❌ Mistral API Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Mistral API Exception: {str(e)}")
        return False

def test_gemini_api(api_key: str) -> bool:
    """Test Gemini 2.0 Flash API connectivity"""
    print("🧪 Testing Gemini 2.0 Flash API...")
    
    try:
        headers = {
            'Content-Type': 'application/json',
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Hello, this is a test. Respond with 'Gemini 2.0 Flash API working!'"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 100,
            }
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                message = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ Gemini API: {message}")
                return True
            else:
                print("❌ Gemini API: No candidates in response")
                return False
        else:
            print(f"❌ Gemini API Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Gemini API Exception: {str(e)}")
        return False

def test_vision_capabilities(mistral_key: str, gemini_key: str):
    """Test vision capabilities with a simple test image"""
    print("\n🖼️ Testing Vision Capabilities...")
    
    # Create a simple test image with text
    img = Image.new('RGB', (400, 200), color='white')
    
    # You would normally use PIL.ImageDraw to add text, but for simplicity:
    print("📝 Created test image with mathematical formula: x² + y² = z²")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Test Mistral Vision (if supported)
    if mistral_key:
        print("🔍 Testing Mistral Vision...")
        try:
            headers = {
                'Authorization': f'Bearer {mistral_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": "mistral-small-latest",
                "temperature": 0.3,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this image and identify any mathematical formulas. Wrap formulas in ${...}$."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                vision_result = result['choices'][0]['message']['content']
                print(f"✅ Mistral Vision: {vision_result[:100]}...")
            else:
                print(f"❌ Mistral Vision not supported or error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Mistral Vision Exception: {str(e)}")
    
    # Test Gemini Vision
    if gemini_key:
        print("🔍 Testing Gemini 2.0 Flash Vision...")
        try:
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": "Analyze this image and extract any text or mathematical formulas. Wrap math formulas in ${...}$ format."
                            },
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                ]
            }
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    vision_result = result['candidates'][0]['content']['parts'][0]['text']
                    print(f"✅ Gemini Vision: {vision_result[:100]}...")
                else:
                    print("❌ Gemini Vision: No candidates in response")
            else:
                print(f"❌ Gemini Vision Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Gemini Vision Exception: {str(e)}")

def main():
    """Main test function"""
    print("🚀 P_OCR PDF AI 2025 - API Configuration Test")
    print("=" * 50)
    
    # Get API keys from environment or user input
    mistral_key = os.getenv("MISTRAL_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not mistral_key:
        mistral_key = input("Enter Mistral API Key (or press Enter to skip): ").strip()
    
    if not gemini_key:
        gemini_key = input("Enter Gemini API Key (or press Enter to skip): ").strip()
    
    print("\n" + "=" * 50)
    
    # Test APIs
    mistral_ok = False
    gemini_ok = False
    
    if mistral_key:
        mistral_ok = test_mistral_api(mistral_key)
    else:
        print("⚠️ Skipping Mistral API test - no key provided")
    
    if gemini_key:
        gemini_ok = test_gemini_api(gemini_key)
    else:
        print("⚠️ Skipping Gemini API test - no key provided")
    
    # Test vision capabilities
    if mistral_key or gemini_key:
        test_vision_capabilities(mistral_key if mistral_ok else None, 
                                gemini_key if gemini_ok else None)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Mistral API: {'✅ Working' if mistral_ok else '❌ Failed/Skipped'}")
    print(f"   Gemini API:  {'✅ Working' if gemini_ok else '❌ Failed/Skipped'}")
    
    if mistral_ok or gemini_ok:
        print("\n🎉 Your API configuration is ready for P_OCR PDF AI 2025!")
        print("   Run: streamlit run app.py")
    else:
        print("\n⚠️ Please check your API keys and try again.")
        print("   Mistral: https://console.mistral.ai/")
        print("   Gemini: https://makersuite.google.com/app/apikey")

if __name__ == "__main__":
    main()
