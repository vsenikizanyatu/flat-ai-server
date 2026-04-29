import os
from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)
BRAIN_FILE = "brain_db.json"

# ОТРИМАННЯ КЛЮЧІВ (Безпечно, через змінні оточення)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
# Gemini ключ можна передавати з клієнта або теж зашити тут

def load_brain():
    if os.path.exists(BRAIN_FILE):
        try:
            with open(BRAIN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {"knowledge": []}
    return {"knowledge": []}

def save_to_brain(user_msg, ai_reply):
    if len(ai_reply) < 40: return
    brain = load_brain()
    brain["knowledge"].append({"q": user_msg, "a": ai_reply})
    if len(brain["knowledge"]) > 500: brain["knowledge"].pop(0)
    with open(BRAIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(brain, f, ensure_ascii=False, indent=4)

def ask_llama_70b(message, history):
    if not GROQ_API_KEY:
        return "Помилка: Ключ GROQ_API_KEY не знайдено в оточенні сервера."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    messages = [{"role": "system", "content": "Ти — FLAT AI. Адаптивне мислення. Точність. Без води."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": messages,
        "temperature": 0.5
    }
    
    response = requests.post(url, json=payload, timeout=20)
    return response.json()['choices'][0]['message']['content']

@app.route('/', methods=['GET', 'POST'])
def catch_all():
    if request.method == 'GET': return "FLAT AI: Bridge Online (Secure Mode)"

    try:
        data = request.get_json()
        user_message = data.get('message', '')
        provider = data.get('provider', 'gemini').lower()
        history = data.get('history', [])
        
        if provider == 'llama':
            reply = ask_llama_70b(user_message, history)
        else:
            # Для Gemini використовуємо ключ, що прийшов з C# (для гнучкості)
            client_gemini_key = data.get('api_key', '')
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={client_gemini_key}"
            payload = {"contents": [{"parts": [{"text": user_message}]}]}
            res = requests.post(url, json=payload, timeout=20).json()
            reply = res['candidates'][0]['content']['parts'][0]['text']

        save_to_brain(user_message, reply)
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Core Error: {str(e)}"}), 500
