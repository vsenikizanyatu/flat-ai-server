from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'GET': return "FLAT AI Bridge: Active"

    try:
        data = request.get_json()
        if not data: return jsonify({"reply": "No JSON received"}), 400

        user_msg = data.get('message', '')
        provider = data.get('provider', 'gemini').lower()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({"reply": "Помилка: Ключ не введено в програмі C#!"})

        if provider == 'llama':
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.1-70b-versatile",
                "messages": [{"role": "user", "content": user_msg}]
            }
            response = requests.post(url, json=payload, timeout=20)
            
            # Перевірка на успішність запиту
            if response.status_code != 200:
                return jsonify({"reply": f"Groq Error {response.status_code}: {response.text}"})
            
            return jsonify({"reply": response.json()['choices'][0]['message']['content']})

        else: # Gemini
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": user_msg}]}]}
            response = requests.post(url, json=payload, timeout=20)
            
            if response.status_code != 200:
                return jsonify({"reply": f"Gemini Error {response.status_code}: {response.text}"})
            
            res_json = response.json()
            # Перевірка наявності відповіді в структурі Google
            if 'candidates' in res_json:
                reply = res_json['candidates'][0]['content']['parts'][0]['text']
                return jsonify({"reply": reply})
            else:
                return jsonify({"reply": f"Gemini Error: {res_json}"})

    except Exception as e:
        return jsonify({"reply": f"Python Error: {str(e)}"}), 500
