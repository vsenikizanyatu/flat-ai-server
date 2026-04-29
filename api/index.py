from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            user_message = data.get("message", "")
            api_key = data.get("api_key", "")

            # Запит до "Вчителя" (Gemini)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": user_message}]}]}
            
            response = requests.post(url, json=payload)
            gemini_data = response.json()

            if response.status_code == 200:
                text_reply = gemini_data['candidates'][0]['content']['parts'][0]['text']
                self._send_response({"reply": text_reply, "source": "Gemini API"})
            else:
                self._send_response({"error": "Gemini Error"}, 500)

        except Exception as e:
            self._send_response({"error": str(e)}, 500)

    def _send_response(self, response_dict, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_dict).encode('utf-8'))
