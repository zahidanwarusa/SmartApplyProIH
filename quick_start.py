#!/usr/bin/env python3
"""
Gemini API Diagnostic Tool
Tests your Gemini API connection and configuration
"""

import sys
from pathlib import Path

def print_header():
    print("=" * 80)
    print("🔍 Gemini API Diagnostic Tool")
    print("=" * 80)
    print()

def check_config():
    """Check if config.py exists and has API keys"""
    print("[1] Checking config.py...")
    print("-" * 60)
    
    if not Path('config.py').exists():
        print("❌ config.py not found!")
        print("\nPlease create config.py with:")
        print("""
GEMINI_API_KEYS = [
    'your-gemini-api-key-here'
]
        """)
        return None
    
    try:
        import config
        if hasattr(config, 'GEMINI_API_KEYS'):
            keys = config.GEMINI_API_KEYS
            if not keys or len(keys) == 0:
                print("❌ No API keys configured!")
                return None
            
            if keys[0] == 'your-api-key-here' or keys[0] == 'your-gemini-api-key-here':
                print("❌ API key is placeholder - not a real key!")
                print("\nYou need to replace it with your actual Gemini API key")
                print("Get one at: https://makersuite.google.com/app/apikey")
                return None
            
            print(f"✅ Found {len(keys)} API key(s)")
            return keys
        else:
            print("❌ GEMINI_API_KEYS not found in config.py")
            return None
    except Exception as e:
        print(f"❌ Error loading config.py: {e}")
        return None

def test_gemini_import():
    """Test if google.generativeai is installed"""
    print("\n[2] Checking google.generativeai package...")
    print("-" * 60)
    
    try:
        import google.generativeai as genai
        print("✅ google.generativeai is installed")
        return True
    except ImportError:
        print("❌ google.generativeai not installed!")
        print("\nInstall it with:")
        print("  pip install google-generativeai")
        return False

def test_api_connection(api_keys):
    """Test actual API connection"""
    print("\n[3] Testing API Connection...")
    print("-" * 60)
    
    try:
        import google.generativeai as genai
        
        # Configure with first key
        genai.configure(api_key=api_keys[0])
        
        print(f"Using API key: {api_keys[0][:10]}...{api_keys[0][-5:]}")
        
        # Try to list models
        print("\nAttempting to list available models...")
        try:
            models = genai.list_models()
            model_list = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
            
            if model_list:
                print(f"✅ API connection successful!")
                print(f"\nAvailable models:")
                for model in model_list[:5]:  # Show first 5
                    print(f"  • {model}")
                return True
            else:
                print("⚠️  Connected but no suitable models found")
                return False
                
        except Exception as e:
            error_msg = str(e)
            
            if "API_KEY_INVALID" in error_msg or "invalid API key" in error_msg.lower():
                print("❌ API Key is INVALID!")
                print("\nThe key you provided is not valid.")
                print("Get a new key at: https://makersuite.google.com/app/apikey")
                
            elif "quota" in error_msg.lower() or "RESOURCE_EXHAUSTED" in error_msg:
                print("❌ API Quota Exceeded!")
                print("\nYou've used up your free quota for today.")
                print("Wait 24 hours or upgrade your plan.")
                
            elif "billing" in error_msg.lower():
                print("❌ Billing Issue!")
                print("\nYour API key may not have billing enabled.")
                print("Check: https://console.cloud.google.com/billing")
                
            else:
                print(f"❌ API Error: {error_msg}")
            
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_generation(api_keys):
    """Test a simple text generation"""
    print("\n[4] Testing Text Generation...")
    print("-" * 60)
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_keys[0])
        
        # Use Gemini 1.5 Flash (most reliable)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        print("Sending test prompt: 'Say hello in one word'")
        
        response = model.generate_content("Say hello in one word")
        
        if response and response.text:
            print(f"✅ Generation successful!")
            print(f"Response: {response.text}")
            return True
        else:
            print("⚠️  No response received")
            return False
            
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False

def test_job_parsing(api_keys):
    """Test actual job description parsing"""
    print("\n[5] Testing Job Description Parsing...")
    print("-" * 60)
    
    try:
        from gemini_service import GeminiService
        
        print("Creating GeminiService instance...")
        gemini = GeminiService()
        
        test_description = """
We are looking for a Senior Software Engineer with experience in:
- Python and JavaScript
- React and Node.js
- 5+ years of experience
- AWS cloud platforms

Responsibilities:
- Build scalable applications
- Lead technical discussions
- Mentor junior developers
        """
        
        print("Parsing test job description...")
        result = gemini.convert_job_description_to_json(
            test_description,
            "Senior Software Engineer",
            "TechCorp"
        )
        
        if result:
            print("✅ Job parsing successful!")
            print(f"\nExtracted Data:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Company: {result.get('company', 'N/A')}")
            print(f"  Skills: {', '.join(result.get('skills', [])[:5])}")
            return True
        else:
            print("❌ Job parsing failed - returned None")
            return False
            
    except ImportError:
        print("⚠️  gemini_service.py not found - skipping this test")
        return None
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_summary(results):
    """Print summary and recommendations"""
    print("\n" + "=" * 80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 80)
    
    config_ok, import_ok, connection_ok, generation_ok, parsing_ok = results
    
    if all([r for r in results if r is not None]):
        print("\n✅ ALL TESTS PASSED!")
        print("\nYour Gemini API is configured correctly and working.")
        print("The resume generator should work fine now.")
        
    else:
        print("\n❌ ISSUES FOUND\n")
        
        if not config_ok:
            print("1️⃣  FIX API KEY CONFIGURATION")
            print("   • Create or update config.py")
            print("   • Add your real Gemini API key")
            print("   • Get key: https://makersuite.google.com/app/apikey")
            print()
        
        if config_ok and not import_ok:
            print("2️⃣  INSTALL REQUIRED PACKAGE")
            print("   pip install google-generativeai")
            print()
        
        if config_ok and import_ok and not connection_ok:
            print("3️⃣  FIX API CONNECTION")
            print("   • Check if API key is valid")
            print("   • Verify you haven't exceeded quota")
            print("   • Check internet connection")
            print()
        
        if connection_ok and not generation_ok:
            print("4️⃣  GENERATION ISSUE")
            print("   • Try a different model")
            print("   • Check API quotas")
            print()
        
        if generation_ok and parsing_ok == False:
            print("5️⃣  PARSING ISSUE")
            print("   • Check gemini_service.py exists")
            print("   • Verify prompt format in gemini_service.py")
            print()
    
    print("=" * 80)
    
    if all([r for r in results if r is not None]):
        print("\n🚀 You're ready to generate resumes!")
    else:
        print("\n🔧 Fix the issues above, then run this diagnostic again")

def main():
    print_header()
    
    # Run all tests
    api_keys = check_config()
    config_ok = api_keys is not None
    
    if not config_ok:
        print_summary([False, None, None, None, None])
        return
    
    import_ok = test_gemini_import()
    
    if not import_ok:
        print_summary([True, False, None, None, None])
        return
    
    connection_ok = test_api_connection(api_keys)
    
    if not connection_ok:
        print_summary([True, True, False, None, None])
        return
    
    generation_ok = test_simple_generation(api_keys)
    parsing_ok = test_job_parsing(api_keys)
    
    print_summary([config_ok, import_ok, connection_ok, generation_ok, parsing_ok])

if __name__ == '__main__':
    main()