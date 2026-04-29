from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Отримуємо дані від твого додатка на C#
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            user_message = data.get("message", "")
            api_key = data.get("api_key", "")

            if not api_key:
                self._send_response({"error": "Відсутній API ключ!"}, 400)
                return

            # --- ТУТ БУДЕ ЛОГІКА ВЛАСНОЇ ПАМ'ЯТІ ---
            # На майбутнє: тут ми спочатку перевірятимемо базу даних.
            # Якщо FLAT AI вже знає відповідь, він не буде турбувати Gemini.

            # 2. Запит до "Вчителя" (Gemini API)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": user_message}]}]
            }
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, json=payload, headers=headers)
            gemini_data = response.json()

            # 3. Обробка відповіді
            if response.status_code == 200:
                text_reply = gemini_data['candidates'][0]['content']['parts'][0]['text']
                
                # Повертаємо відповідь назад у додаток на C#
                self._send_response({
                    "reply": text_reply, 
                    "source": "Gemini API (Training Mode)"
                })
            else:
                self._send_response({"error": "Помилка при запиті до Gemini"}, 500)

        except Exception as e:
            self._send_response({"error": str(e)}, 500)

    # Функція для правильної відправки відповіді серверу
    def _send_response(self, response_dict, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        # Дозволяємо підключення з будь-якого місця (C#, браузер)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_dict).encode('utf-8'))
