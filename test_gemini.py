import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join('env', '.env'))

# Configure Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
print(f"API Key loaded: {'Yes' if api_key else 'No'}")
print(f"API Key starts with: {api_key[:10]}..." if api_key else "No API key found")

genai.configure(api_key=api_key)

# Test the connection
try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Simple test prompt
    test_prompt = """
    Return a JSON object with these keys:
    {
        "status": "success",
        "message": "API connection working",
        "test_skills": ["Python", "JavaScript", "React"]
    }
    """
    
    response = model.generate_content(test_prompt)
    print("API Response:")
    print(response.text)
    print("\n✅ Gemini API connection successful!")
    
except Exception as e:
    print(f"❌ Error connecting to Gemini API: {e}")
    print("Please check your API key and internet connection.")
