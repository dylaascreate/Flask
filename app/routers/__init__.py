from app.services.ollama import query_ollama

@laravel_bp.route('/ask-llm', methods=['POST'])
def ask_llm():
    prompt = request.json.get('prompt')
    answer = query_ollama(prompt)
    return jsonify({"answer": answer})