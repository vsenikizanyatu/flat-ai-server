from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)
BRAIN_FILE = "brain_db.json"

# Завантаження або створення "мозку"
def load_brain():
    if os.path.exists(BRAIN_FILE):
        with open(BRAIN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"knowledge": []}

def save_to_brain(user_msg, ai_reply):
    brain = load_brain()
    # Зберігаємо тільки якщо відповідь достатньо змістовна (щоб не смітити)
    if len(ai_reply) > 50:
        brain["knowledge"].append({"q": user_msg, "a": ai_reply})
        with open(BRAIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(brain, f, ensure_ascii=False, indent=4)

# Простий пошук по базі знань (імітація векторної бази)
def search_brain(query):
    brain = load_brain()
    relevant_knowledge = ""
    query_words = set(query.lower().split())
    for item in brain["knowledge"]:
        item_words = set(item["q"].lower().split())
        # Якщо є спільні слова (більше 2)
        if len(query_words.intersection(item_words)) > 2:
            relevant_knowledge += f"З минулого досвіду: {item['a']}\n"
    return relevant_knowledge

def ask_gemini(message, history, api_key, context_injection):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # Формуємо історію для Gemini
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    # Додаємо поточне повідомлення з вкрапленням пам'яті
    full_message = f"{context_injection}\nПитання: {message}" if context_injection else message
    contents.append({"role": "user", "parts": [{"text": full_message}]})

    payload = {"contents": contents}
    response = requests.post(url, json=payload, timeout=20)
    result = response.json()
    if response.status_code == 200 and 'candidates' in result:
        return result['candidates'][0]['content']['parts'][0]['text']
    return f"Gemini Error: {result.get('error', {}).get('message', 'Unknown')}"

def ask_chatgpt(message, history, api_key, context_injection):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    messages = []
    if context_injection:
        messages.append({"role": "system", "content": f"Твої попередні знання з бази:\n{context_injection}"})
        
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": message})

    payload = {"model": "gpt-3.5-turbo", "messages": messages}
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    result = response.json()
    if response.status_code == 200:
        return result['choices'][0]['message']['content']
    return f"ChatGPT Error: {result.get('error', {}).get('message', 'Unknown')}"

@app.route('/', methods=['GET', 'POST'])
def catch_all():
    if request.method == 'GET':
        return "FLAT AI Hub: Smart Server Active"

    try:
        data = request.get_json()
        user_message = data.get('message', '')
        api_key = data.get('api_key', '').strip()
        provider = data.get('provider', 'gemini').lower()
        history = data.get('history', []) # Отримуємо історію від C#

        # Шукаємо в базі
        context = search_brain(user_message)

        if provider == 'openai':
            reply = ask_chatgpt(user_message, history, api_key, context)
        else:
            reply = ask_gemini(user_message, history, api_key, context)

        # Зберігаємо новий досвід в "мозок"
        if "Error" not in reply:
            save_to_brain(user_message, reply)

        return jsonify({"reply": reply, "provider": provider})

    except Exception as e:
        return jsonify({"reply": f"Server Critical Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(port=5000)
