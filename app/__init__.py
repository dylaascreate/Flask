import os
from flask import Flask
from dotenv import load_dotenv

# Load env vars usually happens here or in app.py
load_dotenv()

def create_app():
    app = Flask(__name__)

    # Configuration from .env
    app.config['SECRET_KEY'] = os.getenv('FLASK_API_SECRET', 'dev-secret')

    # Register Blueprints (Routers)
    from app.routers.laravel import laravel_bp
    app.register_blueprint(laravel_bp)

    # You can register more blueprints here later
    # from app.routers.ollama import ollama_bp
    # app.register_blueprint(ollama_bp)

    return app