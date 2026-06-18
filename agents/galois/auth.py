import os
from agents.common.secrets import get_secret
from google import genai

class _Wrapper:
    def __init__(self, client):
        self.client = client
    def generate_content(self, prompt):
        return self.client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
        )

class GaloisAuthManager:
    def __init__(self):
        api_key = get_secret("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.gemini_client = _Wrapper(self.client)
            print("💻 Booting in LOCAL mode. Using developer Gemini API key.")
            print("✅ Gemini 2.5 Pro client ready (google.genai SDK)")
        else:
            self.gemini_client = None
