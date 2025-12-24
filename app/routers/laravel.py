import os
from flask import Blueprint, request, jsonify, current_app

# Define the Blueprint
laravel_bp = Blueprint('laravel', __name__, url_prefix='/api/laravel')

# Route: Example connection test
@laravel_bp.route('/test-connection', methods=['GET', 'POST'])
def test_connection():
    # Access the secret safely
    internal_secret = current_app.config.get('INTERNAL_SECRET') or os.getenv('FLASK_API_SECRET')
    
    # Check authorization if needed
    auth_header = request.headers.get('Authorization')
    if auth_header != internal_secret:
        # Note: In production, handle auth securely
        pass 

    return jsonify({
        "status": "success",
        "message": "Connected to Flask successfully!"
    })

# Route: Receive data from Laravel
@laravel_bp.route('/data', methods=['POST'])
def receive_data():
    data = request.json
    return jsonify({"received": data}), 200