from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'GET': return "FLAT AI Bridge: Active"

    try:
        data = request.get_json()
        user_msg = data.get('message', '')
        provider = data.get('provider', 'gemini').lower()
        api_key = data.get('api_key', '') # Отримуємо ключ прямо з програми C#

        if not api_key:
            return jsonify({"reply": "Помилка: Ключ не введено в програмі!"})

        if provider == 'llama':
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": "llama-3.1-70b-versatile",
                "messages": [{"role": "user", "content": user_msg}]
            }
            res = requests.post(url, json=payload, timeout=20).json()
            reply = res['choices'][0]['message']['content']
        else:
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": user_msg}]}]}
            res = requests.post(url, json=payload, timeout=20).json()
            reply = res['candidates'][0]['content']['parts'][0]['text']

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Помилка: {str(e)}"}), 500
