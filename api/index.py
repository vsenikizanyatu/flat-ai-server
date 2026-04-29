from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    # GET запит для перевірки в браузері
    if request.method == 'GET':
        return "FLAT AI Bridge: Online (v1 Stable Mode)"

    # POST запит від твоєї програми
    try:
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Error: No JSON data received"}), 400

        user_message = data.get('message', '')
        api_key = data.get('api_key', '').strip()
        
        # Використовуємо СТАБІЛЬНУ версію v1
        # Це посилання працює майже у всіх
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": user_message}]
            }]
        }

        response = requests.post(url, json=payload, timeout=15)
        result = response.json()

        if response.status_code == 200:
            # Витягуємо текст відповіді
            if 'candidates' in result and result['candidates']:
                bot_reply = result['candidates'][0]['content']['parts'][0]['text']
                return jsonify({"reply": bot_reply})
            else:
                return jsonify({"reply": "Google returned empty response (safety filter?)"})
        else:
            # Детальна помилка для дебагу
            error_msg = result.get('error', {}).get('message', 'Unknown Error')
            return jsonify({"reply": f"Google Error {response.status_code}: {error_msg}"})

    except Exception as e:
        return jsonify({"reply": f"Bridge Error: {str(e)}"}), 500

app = app
