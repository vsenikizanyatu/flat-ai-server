from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'GET':
        return "FLAT AI Bridge: Flask is Running. Waiting for POST..."

    try:
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Помилка: JSON не отримано"}), 400

        user_message = data.get('message', '')
        api_key = data.get('api_key', '')
        model_name = data.get('model', 'gemini-1.5-flash').strip()

        if not api_key:
            return jsonify({"reply": "Помилка: Відсутній API ключ"}), 400

        # --- КРИТИЧНЕ ВИПРАВЛЕННЯ ШЛЯХУ МОДЕЛІ ---
        # Google хоче: v1beta/models/gemini-1.5-flash
        if not model_name.startswith('models/'):
            model_path = f"models/{model_name}"
        else:
            model_path = model_name

        url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={api_key}"
        # ----------------------------------------

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
                return jsonify({"reply": bot_reply})
            else:
                return jsonify({"reply": "Google: Порожня відповідь (фільтр безпеки)."}), 200
        else:
            # Витягуємо текст помилки від Google
            err_msg = result.get('error', {}).get('message', 'Unknown Error')
            return jsonify({"reply": f"Google Error [{response.status_code}]: {err_msg}"})

    except Exception as e:
        return jsonify({"reply": f"Внутрішня помилка мосту: {str(e)}"}), 500

app = app
