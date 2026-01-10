import requests
from config import Config

# Update the definition to accept 'json_mode' (defaulting to False)
def query_ollama(prompt, model=None, json_mode=False):
    # 1. Get URL from Config
    base_url = Config.OLLAMA_URL
    
    # Handle slash consistency
    if base_url.endswith('/'):
        api_url = f"{base_url}api/generate"
    else:
        api_url = f"{base_url}/api/generate"

    # 2. Use Config model if none provided
    target_model = model if model else Config.OLLAMA_MODEL

    payload = {
        "model": target_model,
        "prompt": prompt,
        "stream": False
    }

    # 3. Add JSON enforcement if requested
    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.exceptions.RequestException as e:
        print(f"Ollama Service Error: {e}")
        return None