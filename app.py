import os  # <--- Put it here
from flask import Flask, request, jsonify

app = Flask(__name__)

# Now you can use it to get the secret from the environment
INTERNAL_SECRET = os.getenv('FLASK_API_SECRET', 'default_secret_if_none_found')

@app.route('/predict', methods=['POST'])
def predict():
    # 1. Security Check (Only allow requests with the secret)
    client_secret = request.headers.get('X-Internal-Secret')
    
    if client_secret != INTERNAL_SECRET:
        return jsonify({"error": "Unauthorized access"}), 403

    # 2. Process Data
    data = request.json.get('input_data')
    
    # ... AI Logic ...
    result = f"Processed '{data}' on Port 5001"

    return jsonify({"result": result, "status": "success"})
