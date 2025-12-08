"""
Script to inspect GeminiService methods
"""

from gemini_service import GeminiService

print("Inspecting GeminiService class...")
print("=" * 60)

# Create instance
gemini = GeminiService()

# Get all public methods
methods = [m for m in dir(gemini) if not m.startswith('_') and callable(getattr(gemini, m))]

print("\nAvailable methods:")
print("-" * 60)
for method in methods:
    print(f"  - {method}")

print("\n" + "=" * 60)

# Try to find the right method to use
print("\nLooking for content generation method...")

if hasattr(gemini, 'generate_content'):
    print("✅ Found: generate_content()")
elif hasattr(gemini, 'generate_text'):
    print("✅ Found: generate_text()")
elif hasattr(gemini, 'generate_response'):
    print("✅ Found: generate_response()")
elif hasattr(gemini, 'optimize_resume_section'):
    print("✅ Found: optimize_resume_section()")
elif hasattr(gemini, 'generate'):
    print("✅ Found: generate()")
else:
    print("❌ Could not find a standard generation method")
    print("Available methods are listed above. Please check which one to use.")