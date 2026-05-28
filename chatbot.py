import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai  

# This finds the exact folder where chatbot.py lives and looks for the .env file there
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)
# The new SDK automatically looks for the GEMINI_API_KEY environment variable
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash") # standard default for general chat

if not API_KEY:
    raise EnvironmentError("Set GEMINI_API_KEY in your environment or .env file.")

def chat_loop():
    # Initialize the new standard client
    client = genai.Client()
    
    # Create a chat session to automatically manage history
    chat = client.chats.create(model=MODEL_NAME)

    print(f"Google Gemini ({MODEL_NAME}) chatbot ready. Type 'exit' or 'quit' to stop.")
    
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        try:
            # Send message using the updated SDK client pattern
            response = chat.send_message(user_input)
            print(f"Gemini: {response.text}\n")
        except Exception as e:
            print(f"API Error: {e}")

if __name__ == "__main__":
    chat_loop()