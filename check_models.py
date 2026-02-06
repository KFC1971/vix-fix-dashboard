import google.generativeai as genai
import os

# Use the key user provided in previous turns or ask for it. 
# I will use the one hardcoded in the dashboard as default if available there.
# "AIzaSyCoxeAZMO-ZoHeFw-WE8-tJ93CyJoHOmTs"
api_key = "AIzaSyCoxeAZMO-ZoHeFw-WE8-tJ93CyJoHOmTs"

genai.configure(api_key=api_key)

print("Listing available models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
