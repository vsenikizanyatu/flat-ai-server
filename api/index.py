from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'GET':
        return "FLAT AI Bridge: Online"

    try:
        data = request.get_json()
        if not data: return jsonify({"reply": "No JSON"}), 400

        user_message = data.get('message', '')
        api_key = data.get('api_key', '').strip()
        # Примусово ставимо flash, якщо щось пішло не так
        model_name = data.get('model', 'gemini-1.5-flash').strip()

        # Чистимо назву моделі від можливих "models/" щоб не дублювати
        model_name = model_name.replace('models/', '')
        
        # Спробуємо прямий шлях v1beta/models/назва
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        payload = {
            "contents": [{"parts": [{"text": user_message}]}]
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        result = response.json()

        if response.status_code == 200:
            bot_reply = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"reply": bot_reply})
        else:
            # Якщо знову 404 — виведемо повний URL в лог (для тебе)
            msg = result.get('error', {}).get('message', 'Unknown Error')
            return jsonify({"reply": f"Google Error {response.status_code}: {msg}"})

    except Exception as e:
        return jsonify({"reply": f"Bridge Error: {str(e)}"}), 500

app = app
