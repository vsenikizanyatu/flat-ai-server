from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            user_message = data.get('message')
            api_key = data.get('api_key')

            # Налаштування Gemini через URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            # Додаємо "Системну інструкцію" прямо в запит
            payload = {
                "contents": [
                    {
                        "role": "user", 
                        "parts": [{"text": f"Ти - Вчитель для FLAT AI. Надавай технічні знання коротко. Запит: {user_message}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 500
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()

            if response.status_code == 200:
                bot_reply = result['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 401:
                bot_reply = "ПОМИЛКА: Ключ недійсний (Unauthorized). Перевір його в AI Studio."
            else:
                bot_reply = f"Помилка Google API: {result.get('error', {}).get('message', 'Невідома помилка')}"

        except Exception as e:
            bot_reply = f"Помилка сервера: {str(e)}"

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"reply": bot_reply}).encode('utf-8'))
