from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

@app.route('/api', methods=['POST'])
def handle_post():
    try:
        # Flask сам забирає JSON і декодує його
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Помилка: Порожній JSON"}), 400

        user_message = data.get('message')
        api_key = data.get('api_key')
        model_name = data.get('model', 'gemini-1.5-flash')

        if not api_key:
            return jsonify({"reply": "Помилка: Відсутній API Key"}), 401

        # Формуємо запит до Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": f"Ти - Вчитель для FLAT AI. Надавай технічні знання максимально точно та коротко. Запит: {user_message}"}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        result = response.json()

        if response.status_code == 200:
            if 'candidates' in result and result['candidates']:
                bot_reply = result['candidates'][0]['content']['parts'][0]['text']
            else:
                bot_reply = "Google повернув порожню відповідь (фільтр безпеки)."
            return jsonify({"reply": bot_reply})
        else:
            err_msg = result.get('error', {}).get('message', 'API Error')
            return jsonify({"reply": f"Помилка Google [{response.status_code}]: {err_msg}"})

    except Exception as e:
        return jsonify({"reply": f"Внутрішня помилка мосту: {str(e)}"}), 500

@app.route('/api', methods=['GET'])
def handle_get():
    return "FLAT AI Bridge: Flask is Running"

# Важливо для Vercel
app = app
