from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            # Явно декодуємо вхідні байти в utf-8, щоб уникнути пошкодження ключа
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            data = json.loads(post_data)
            user_message = data.get('message')
            api_key = data.get('api_key')
            model_name = data.get('model', 'gemini-1.5-flash')

            if not api_key:
                self._send_json({"reply": "ПОМИЛКА: API ключ не знайдено в запиті!"}, 400)
                return

            # Формуємо запит до Google
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": f"Ти - Вчитель для FLAT AI. Надавай технічні знання максимально точно та коротко. Запит: {user_message}"}]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 800
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            try:
                result = response.json()
            except:
                result = {}

            if response.status_code == 200:
                if 'candidates' in result and result['candidates']:
                    bot_reply = result['candidates'][0]['content']['parts'][0]['text']
                else:
                    bot_reply = "Google повернув порожню відповідь (можливо, фільтр безпеки)."
                self._send_json({"reply": bot_reply}, 200)
            else:
                # Витягуємо детальну помилку від Google (наприклад, чому саме Unauthorized)
                err_detail = result.get('error', {}).get('message', 'Невідома помилка API')
                self._send_json({"reply": f"Помилка Google [{response.status_code}]: {err_detail}"}, 200)

        except Exception as e:
            self._send_json({"reply": f"Внутрішня помилка мосту: {str(e)}"}, 500)

    def _send_json(self, data, status_code):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("FLAT AI Server: Online. Waiting for POST...".encode('utf-8'))
