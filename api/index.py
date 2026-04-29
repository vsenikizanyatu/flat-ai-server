from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Цей роут обробляє і корінь (/), і /api, і будь-що інше
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    # Якщо це просто перевірка в браузері (GET)
    if request.method == 'GET':
        return "FLAT AI Bridge: Flask is Running. System Status: Online."

    # Якщо це запит з LINQPad (POST)
    try:
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Помилка: JSON не отримано"}), 400

        user_message = data.get('message')
        api_key = data.get('api_key')
        model_name = data.get('model', 'gemini-1.5-flash')

        if not api_key:
            return jsonify({"reply": "Помилка: Відсутній API ключ у запиті"}), 400

        # Запит до Google Gemini
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
        
        # Перевірка на помилки самого Google API
        if response.status_code != 200:
            try:
                error_data = response.json()
                msg = error_data.get('error', {}).get('message', 'Unknown Google Error')
                return jsonify({"reply": f"Google Error [{response.status_code}]: {msg}"})
            except:
                return jsonify({"reply": f"Google Server Error: {response.status_code}"})

        result = response.json()

        # Витягуємо текст відповіді
        if 'candidates' in result and result['candidates']:
            bot_reply = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"reply": bot_reply})
        else:
            return jsonify({"reply": "Google повернув порожню відповідь (можливо, цензура)."}), 200

    except Exception as e:
        return jsonify({"reply": f"Внутрішня помилка мосту: {str(e)}"}), 500

# Обов'язково для Vercel
app = app
