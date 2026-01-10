from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
import os
import json

# Initialize the db object globally
db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # =========================================================
    # 1. LOAD GLOBAL COURSE DATABASE
    # =========================================================
    app.json_db_path = os.path.join(app.root_path, 'data', 'course_db.json')
    app.course_db = []

    if os.path.exists(app.json_db_path):
        try:
            with open(app.json_db_path, 'r', encoding='utf-8') as f:
                app.course_db = json.load(f)
            print(f" [GLOBAL] Course Database loaded: {len(app.course_db)} items.")
        except Exception as e:
            print(f" [ERROR] Course DB load failed: {e}")

    # =========================================================
    # 2. LOAD GLOBAL WEBSITE CONTEXT
    # =========================================================
    app.website_data_path = os.path.join(app.root_path, 'data', 'website_context.json')
    app.website_context = []

    if os.path.exists(app.website_data_path):
        try:
            with open(app.website_data_path, 'r', encoding='utf-8') as f:
                app.website_context = json.load(f)
            print(f" [GLOBAL] Website Context loaded: {len(app.website_context)} pages.")
        except Exception as e:
            print(f" [ERROR] Website Context load failed: {e}")

    # =========================================================
    # 3. SETUP EXTENSIONS & BLUEPRINTS
    # =========================================================
    
    # Bind the db to the app
    db.init_app(app)
    
    # Import blueprints inside function to avoid circular imports
    from app.routes.laravel import laravel_bp
    app.register_blueprint(laravel_bp, url_prefix='/api/laravel')

    from app.routes.ollama import ollama_bp
    app.register_blueprint(ollama_bp, url_prefix='/api/ollama')
    
    from app.routes.monitor import monitor_bp
    app.register_blueprint(monitor_bp,  url_prefix='/api/monitor')

    return app