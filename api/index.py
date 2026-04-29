from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Читаємо дані від C#
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            user_message = data.get('message')
            api_key = data.get('api_key')

            if not api_key:
                raise ValueError("API Key is missing")

            # 2. Відправляємо запит до Google Gemini
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "contents": [{"parts": [{"text": user_message}]}]
            }

            response = requests.post(url, headers=headers, json=payload)
            result = response.json()

            # 3. Витягуємо текст відповіді
            if 'candidates' in result:
                bot_reply = result['candidates'][0]['content']['parts'][0]['text']
            else:
                bot_reply = f"Помилка від Google: {result.get('error', {}).get('message', 'Невідома помилка')}"

        except Exception as e:
            bot_reply = f"Помилка на сервері Python: {str(e)}"

        # 4. Відправляємо відповідь назад у C#
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = json.dumps({"reply": bot_reply})
        self.wfile.write(response_data.encode('utf-8'))

    # Додаємо do_GET, щоб браузер не видавав 501 при простому заході на сторінку
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Server is running. Send a POST request with message and api_key.".encode('utf-8'))
