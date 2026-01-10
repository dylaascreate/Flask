import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Flask's Session Key (Required by Flask)
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default-session-key')
    
    # 2. Your API Password (For Laravel -> Flask connection)
    INTERNAL_API_KEY = os.getenv('FLASK_API_SECRET')  # The key you used before
    
    # 3. Ollama Settings
    OLLAMA_URL = os.getenv('OLLAMA_URL')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL')
    
    # Format: postgresql://username:password@localhost:5432/database_name
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # vital for performance when connecting to external DBs
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    PYTHON_VERSION = os.getenv('PYTHON_VERSION', '3.12.3')