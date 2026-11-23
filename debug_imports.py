import sys
print("Start imports...")
try:
    import dotenv
    print("dotenv ok")
    import fastapi
    print("fastapi ok")
    from core.parsers.pdf_parser import pdf_to_text
    print("pdf_parser ok")
    from utils.chatbot import generate_chat_response
    print("chatbot ok")
    from chat_api import router
    print("chat_api ok")
    from crew.crew_runner import run_pipeline
    print("crew_runner ok")
except Exception as e:
    print(f"Error: {e}")
print("Done")
