from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

def ask_gemini(message, api_key):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": message}]}]}
    response = requests.post(url, json=payload, timeout=15)
    result = response.json()
    if response.status_code == 200 and 'candidates' in result:
        return result['candidates'][0]['content']['parts'][0]['text']
    return f"Gemini Error: {result.get('error', {}).get('message', 'Unknown')}"

def ask_chatgpt(message, api_key):
    # Використовуємо стандартний OpenAI API формат
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-3.5-turbo", # або gpt-4o-mini
        "messages": [{"role": "user", "content": message}]
    }
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    result = response.json()
    if response.status_code == 200:
        return result['choices'][0]['message']['content']
    return f"ChatGPT Error: {result.get('error', {}).get('message', 'Unknown')}"

@app.route('/', methods=['GET', 'POST'])
def catch_all():
    if request.method == 'GET':
        return "FLAT AI Hub: Multi-Model Bridge Active"

    try:
        data = request.get_json()
        user_message = data.get('message', '')
        api_key = data.get('api_key', '').strip()
        provider = data.get('provider', 'gemini').lower() # Новий параметр

        if provider == 'openai':
            reply = ask_chatgpt(user_message, api_key)
        else:
            reply = ask_gemini(user_message, api_key)

        return jsonify({"reply": reply, "provider": provider})

    except Exception as e:
        return jsonify({"reply": f"Bridge Critical Error: {str(e)}"}), 500
