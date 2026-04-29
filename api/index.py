import os
from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# ОТРИМАННЯ КЛЮЧІВ (Безпечно)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 

def ask_llama_70b(message, history):
    if not GROQ_API_KEY:
        return "Помилка: Ключ GROQ_API_KEY не знайдено в Environment Variables сервера."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}", 
        "Content-Type": "application/json"
    }
    
    # Формуємо історію для Llama
    messages = [{"role": "system", "content": "Ти — FLAT AI. Адаптивне мислення. Точність. Без води."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": messages,
        "temperature": 0.5
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        # Якщо статус не 200, повертаємо текст помилки від Groq
        if response.status_code != 200:
            return f"Groq Error {response.status_code}: {response.text}"
            
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"Request Error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def catch_all():
    if request.method == 'GET': 
        return "FLAT AI: Bridge Online (Secure Mode). Status: " + ("Key Found" if GROQ_API_KEY else "Key Missing")

    try:
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Error: No JSON data received"}), 400
            
        user_message = data.get('message', '')
        provider = data.get('provider', 'gemini').lower()
        history = data.get('history', [])
        
        if provider == 'llama':
            reply = ask_llama_70b(user_message, history)
        else:
            client_gemini_key = data.get('api_key', '')
            if not client_gemini_key:
                return jsonify({"reply": "Помилка: Gemini ключ не введений в C# програмі."})
                
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={client_gemini_key}"
            payload = {"contents": [{"parts": [{"text": user_message}]}]}
            
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code != 200:
                return jsonify({"reply": f"Gemini API Error: {res.text}"})
                
            res_data = res.json()
            reply = res_data['candidates'][0]['content']['parts'][0]['text']

        # Тимчасово прибрали save_to_brain для Vercel (потрібна зовнішня БД)
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Server Core Error: {str(e)}"}), 500

# Для локального тесту
if __name__ == '__main__':
    app.run(debug=True)
