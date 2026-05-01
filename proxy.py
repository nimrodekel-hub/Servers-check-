"""
פרוקסי מקומי קטן — מפעיל פעם אחת על המחשב שלך.
הכלי (index.html) ישתמש בו אוטומטית כשהוא פעיל.

הפעלה:
  python proxy.py

ואז פתח את index.html בדפדפן כרגיל.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.error, sys, ssl, json

PORT = 7654

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # silent

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        target = self.path.lstrip('/')
        if not target.startswith('http'):
            self.send_response(400)
            self._cors()
            self.end_headers()
            return
        try:
            req = urllib.request.Request(target, headers={'Range': 'bytes=0-0'})
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            self.send_response(502)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
            return

        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': status}).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')


print(f'פרוקסי פועל על http://localhost:{PORT}  —  לעצור: Ctrl+C')
HTTPServer(('localhost', PORT), Handler).serve_forever()
