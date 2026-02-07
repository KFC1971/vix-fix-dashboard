import google.generativeai as genai
import os

# Use the key user provided in previous turns or ask for it.
# I will use the one hardcoded in the dashboard as default # Test script to list Gemini models

# Load API Key from environment or input
api_key = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

genai.configure(api_key=api_key)

print("Listing available models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
