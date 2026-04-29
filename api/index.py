from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Розпаковуємо дані від C# (LINQPad)
            data = json.loads(post_data)
            user_message = data.get('message')
            api_key = data.get('api_key')
            # Отримуємо назву моделі (flash або pro)
            model_name = data.get('model', 'gemini-1.5-flash')

            # Формуємо URL з урахуванням обраної моделі
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            
            # Структура запиту згідно з документацією Gemini
            payload = {
                "contents": [
                    {
                        "role": "user", 
                        "parts": [{"text": f"Ти - Вчитель для FLAT AI. Надавай технічні знання максимально точно та коротко. Запит: {user_message}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 800  # Трішки збільшив ліміт для складних пояснень
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, headers=headers, json=payload)
            
            # Перевіряємо, чи повернув Google JSON
            try:
                result = response.json()
            except:
                result = {}

            if response.status_code == 200:
                # Успішна відповідь
                if 'candidates' in result and result['candidates']:
                    bot_reply = result['candidates'][0]['content']['parts'][0]['text']
                else:
                    bot_reply = "Google повернув порожню відповідь. Можливо, спрацював фільтр вмісту."
            elif response.status_code == 401:
                bot_reply = "ПОМИЛКА: Ключ Unauthorized. Перевір його в AI Studio."
            elif response.status_code == 429:
                bot_reply = "ПОМИЛКА: Забагато запитів (Too Many Requests). Збільш затримку в LINQPad."
            else:
                error_msg = result.get('error', {}).get('message', 'Невідома помилка')
                bot_reply = f"Помилка Google API ({response.status_code}): {error_msg}"

        except Exception as e:
            bot_reply = f"Внутрішня помилка сервера Vercel: {str(e)}"

        # Повертаємо результат назад у C# додаток
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_payload = json.dumps({"reply": bot_reply})
        self.wfile.write(response_payload.encode('utf-8'))

    # Додаємо обробку GET, щоб можна було перевірити статус у браузері
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("FLAT AI Server: Running. Waiting for POST requests...".encode('utf-8'))
