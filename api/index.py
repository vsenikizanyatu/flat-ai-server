import os
from flask import Flask, request, jsonify
import requests
from vercel_kv import KV  # Імпортуємо інструмент пам'яті

app = Flask(__name__)
kv = KV()  # Ініціалізуємо пам'ять

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'GET': 
        return "FLAT AI Bridge: Active. Storage: Connected."

    try:
        data = request.get_json()
        if not data: return jsonify({"reply": "No JSON"}), 400

        user_msg = data.get('message', '')
        provider = data.get('provider', 'gemini').lower()
        api_key = data.get('api_key', '').strip()

        # Виклик нейронки (Gemini або Llama)
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

        # --- ЛОГІКА НАВЧАННЯ (ЗАПИС У БАЗУ) ---
        # Створюємо запис знання
        knowledge_entry = {
            "prompt": user_msg,
            "reply": reply,
            "provider": provider
        }
        
        # Додаємо в список 'flat_ai_brain' (зберігаємо останні 100 діалогів)
        import json
        kv.lpush('flat_ai_brain', json.dumps(knowledge_entry))
        kv.ltrim('flat_ai_brain', 0, 99) 
        # --------------------------------------

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"System Error: {str(e)}"}), 500
