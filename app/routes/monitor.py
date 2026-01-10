import time
import requests
import psutil
import os
import joblib
import json
from flask import Blueprint, jsonify, current_app, request

monitor_bp = Blueprint('monitor', __name__, url_prefix='/api/monitor')

# Global cache to prevent reloading the 100MB file on every ping
loaded_model = None
last_loaded_file = None
model_cached_info = {}  # Cache for model metadata to avoid re-parsing

@monitor_bp.route('/health', methods=['GET'])
def system_health():
    global loaded_model, last_loaded_file, model_cached_info
    start_time = time.time()
    
    # =========================================================
    # 1. UPDATED: UNSUPERVISED MODEL HEALTH CHECK
    # =========================================================
    requested_file = request.args.get('model_file', 'devnexus.pkl')
    
    # Path resolution logic (Checks both models/ and root folder)
    model_path_primary = os.path.join(current_app.root_path, 'models', requested_file)
    model_path_root = os.path.join(current_app.root_path, requested_file)
    
    final_path = model_path_primary if os.path.exists(model_path_primary) else \
                 (model_path_root if os.path.exists(model_path_root) else None)

    custom_model_status = "missing"
    model_info = {
        "file": requested_file,
        "size": "0 MB",
        "type": "unknown",
        "components": [],
        "integrity": "not_loaded"
    }

    # =========================================================
    # 1. FIXED: DICTIONARY MODEL HEALTH CHECK
    # =========================================================
    if final_path:
        try:
            size_in_bytes = os.path.getsize(final_path)
            model_info["size"] = f"{size_in_bytes / (1024 * 1024):.2f} MB"
            
            if loaded_model is None or last_loaded_file != requested_file:
                with open(final_path, 'rb') as f:
                    loaded_model = joblib.load(f)
                last_loaded_file = requested_file

            # CHECK STRUCTURE: Is it a dictionary or a direct model?
            if isinstance(loaded_model, dict):
                # Valid if it contains the required keys for matching
                has_vectorizer = 'vectorizer' in loaded_model
                has_model = 'model' in loaded_model
                
                model_info["integrity"] = "valid (dict)"
                model_info["can_process"] = has_vectorizer and has_model
            else:
                # Fallback for old direct models
                model_info["integrity"] = "valid (object)"
                model_info["can_process"] = hasattr(loaded_model, 'predict') or hasattr(loaded_model, 'kneighbors')

            custom_model_status = "operational" if model_info["can_process"] else "degraded"

        except Exception as e:
            custom_model_status = "corrupt"
            model_info["integrity"] = f"error: {str(e)}"
            loaded_model = None
            
    # =========================================================
    # 2. OPTIMIZED: OLLAMA CHECK
    # =========================================================
    ollama_status = "outage"
    ollama_model = "unknown"
    ollama_latency = 0
    
    base_url = current_app.config.get('OLLAMA_URL') or 'http://localhost:11434'
    tags_url = f"{base_url.rstrip('/')}/api/tags"

    try:
        o_start = time.time()
        # Optimization: Reduced timeout from default (often 10s+) to 0.5s
        # For a health check, if local AI isn't instant, it's effectively down.
        o_resp = requests.get(tags_url, timeout=0.5) 
        if o_resp.status_code == 200:
            ollama_status = "operational"
            ollama_latency = round((time.time() - o_start) * 1000)
            data = o_resp.json()
            models = data.get('models', [])
            if models:
                ollama_model = models[0]['name']
    except:
        pass

    # =========================================================
    # 3. OPTIMIZED: SYSTEM METRICS
    # =========================================================
    # Optimization: Use 'inet' kind to filter quickly, or skip if overhead is high
    try:
        connections = len(psutil.net_connections(kind='inet'))
    except:
        connections = "N/A"

    # =========================================================
    # 4. OPTIMIZED: FILE DEPENDENCIES CHECK
    # =========================================================
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check Course DB
    course_db_path = os.path.join(project_root, 'data', 'course_db.json')
    course_db_status = "missing"
    course_db_latency = 0
    
    # Optimization: Use os.access (stat check) instead of open() (read check)
    if os.path.exists(course_db_path):
        t_db = time.time()
        if os.access(course_db_path, os.R_OK):
            course_db_status = "operational"
        else:
            course_db_status = "corrupt"
        course_db_latency = round((time.time() - t_db) * 1000) # Should be <1ms now

    # Check Website Context
    web_ctx_path = os.path.join(project_root, 'data', 'website_context.json')
    # Optimization: One-line check
    web_ctx_status = "operational" if os.access(web_ctx_path, os.R_OK) else "missing"

    # =========================================================
    # 5. NEW: SERVICES STATUS AGGREGATION (No Changes to Logic)
    # =========================================================
    
    # Pre-calc logic to save CPU cycles
    is_model_ok = custom_model_status == "operational"
    is_db_ok = course_db_status == "operational"
    is_ollama_ok = ollama_status == "operational"
    is_web_ok = web_ctx_status == "operational"

    services = {
        "roadmap_generator": {
            "status": "operational" if (is_model_ok and is_db_ok) else "degraded",
            "latency": f"{course_db_latency}ms", 
            "dependencies": ["DevNexus Model", "Course DB"]
        },
        "cv_ats_scorer": {
            "status": "operational" if is_ollama_ok else "outage",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI"]
        },
        "quiz_generator": {
            "status": "operational" if (is_ollama_ok and is_db_ok) else "degraded",
            "latency": f"{ollama_latency + course_db_latency}ms",
            "dependencies": ["Ollama AI", "Course DB"]
        },
        "website_chatbot": {
            "status": "operational" if (is_ollama_ok and is_web_ok) else "degraded",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI", "Website Context"]
        },
        "skill_recommender": {
            "status": "operational" if is_ollama_ok else "outage",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI"]
        },
        "project_recommender": {
            "status": "operational" if is_ollama_ok else "outage",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI"]
        },
        "career_recommender": {
            "status": "operational" if is_ollama_ok else "outage",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI"]
        },
        "skill_gap": {
            "status": "operational" if is_ollama_ok else "outage",
            "latency": f"{ollama_latency}ms",
            "dependencies": ["Ollama AI"]
        }
    }

    # =========================================================
    # 6. RETURN RESPONSE
    # =========================================================
    
    latency = round((time.time() - start_time) * 1000)
    
    return jsonify({
        "flask": {
            "name": "Flask Gateway",
            "version": "3.1.12",
            "python_version": f"{current_app.config.get('PYTHON_VERSION', 'unknown')}",
            "host": request.host,
            "status": "operational",
            "connections": connections,
            "latency": latency
        },
        "ollama": {
            "status": ollama_status,
            "model": ollama_model,
            "latency": ollama_latency
        },
        "custom_model": {
            "status": custom_model_status,
            "details": model_info,
            "integrity": model_info["integrity"],
            "size": model_info["size"],
            "latency": latency 
        },
        "dependencies": {
            "course_database": {"status": course_db_status, "latency": f"{course_db_latency}ms"},
            "website_context": {"status": web_ctx_status}
        },
        "services": services
    })