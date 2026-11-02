import json, os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Allow', 'POST, OPTIONS')
        self.end_headers()

    def do_POST(self):
        if self.path not in ('/api/chat', '/'):
            return self.respond(404, {'error': 'Not found'})
        try:
            length = min(int(self.headers.get('content-length', '0')), 50000)
            body = json.loads(self.rfile.read(length) or b'{}')
            message = str(body.get('message', '')).strip()[:4000]
            context = body.get('context', {})
            if not message:
                return self.respond(400, {'error': 'message is required'})
            base = os.environ.get('OLLAMA_BASE_URL', '').rstrip('/')
            model = os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')
            if not base:
                return self.respond(503, {'error': 'Ollama is not configured'})
            prompt = ('أنت WALLET OS، مساعد مالي شخصي. أجب بالعربية بوضوح، لا تخترع أرقامًا، واستخدم سياق البيانات فقط عند التحليل. لا تقدم وعودًا أو نصائح استثمارية جازمة.\nسياق مالي بصيغة JSON: ' + json.dumps(context, ensure_ascii=False) + '\nسؤال المستخدم: ' + message)
            payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False}).encode()
            req = urllib.request.Request(base + '/api/generate', data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read())
            return self.respond(200, {'reply': result.get('response', '').strip()})
        except urllib.error.HTTPError as e:
            return self.respond(502, {'error': 'Ollama upstream error', 'status': e.code})
        except Exception:
            return self.respond(500, {'error': 'Assistant service unavailable'})

    def respond(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)
