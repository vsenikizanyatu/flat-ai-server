from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Робимо так, щоб і /api, і корінь / працювали
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    if request.method == 'GET':
        return "FLAT AI Bridge: Flask is Running. Send POST to /api"

    if path == 'api':
        try:
            data = request.get_json()
            if not data: return jsonify({"reply": "No JSON"}), 400
            
            user_message = data.get('message')
            api_key = data.get('api_key')
            model_name = data.get('model', 'gemini-1.5-flash')

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": user_message}]}]
            }
            
            response = requests.post(url, json=payload, timeout=15)
            result = response.json()

            if response.status_code == 200:
                bot_reply = result['candidates'][0]['content']['parts'][0]['text']
                return jsonify({"reply": bot_reply})
            else:
                return jsonify({"reply": f"Google Error: {response.status_code}"}), 200
        except Exception as e:
            return jsonify({"reply": f"Bridge Error: {str(e)}"}), 500
    
    return jsonify({"reply": "Not Found"}), 404

app = app
