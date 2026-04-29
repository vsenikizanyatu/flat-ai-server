from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'GET':
        return "FLAT AI Bridge: Active"

    try:
        data = request.get_json()
        user_message = data.get('message', '')
        api_key = data.get('api_key', '').strip()
        model_name = data.get('model', 'gemini-1.5-flash').replace('models/', '')

        # Спроба №1: v1beta (найновіша)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": user_message}]}]}
        
        response = requests.post(url, json=payload, timeout=10)
        
        # Якщо 404, пробуємо Спроба №2: v1 (стабільна)
        if response.status_code == 404:
            url_v1 = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={api_key}"
            response = requests.post(url_v1, json=payload, timeout=10)

        result = response.json()

        if response.status_code == 200:
            reply = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"reply": reply})
        else:
            err = result.get('error', {}).get('message', 'Unknown')
            return jsonify({"reply": f"Google Error {response.status_code}: {err}"})

    except Exception as e:
        return jsonify({"reply": f"Bridge Error: {str(e)}"}), 500

app = app
