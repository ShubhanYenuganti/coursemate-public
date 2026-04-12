"""
Local development server — routes /api/* requests to Vercel handler classes.
Usage: python dev_server.py
Runs on port 3001 (matches vite.config.js proxy target).
"""
import importlib
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# Load .env before importing any api modules so env vars are available
load_dotenv()

# Ensure both the project root and the api/ directory are on sys.path so that
# both relative imports (Vercel style) and bare imports (fallback) resolve.
_root = os.path.dirname(os.path.abspath(__file__))
for _p in (_root, os.path.join(_root, 'api')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Map URL path → api module
ROUTES = {
    '/api/auth':       'api.auth',
    '/api/chat':       'api.chat',
    '/api/course':     'api.course',
    '/api/flashcards': 'api.flashcards',
    '/api/material':   'api.material',
    '/api/notion':     'api.notion',
    '/api/gdrive':     'api.gdrive',
    '/api/quiz':       'api.quiz',
    '/api/reports':    'api.reports',
    '/api/sharing':    'api.sharing',
    '/api/user':       'api.user',
}


class Router(BaseHTTPRequestHandler):
    def _dispatch(self, method):
        path = self.path.split('?')[0].rstrip('/')
        module_name = ROUTES.get(path)
        if not module_name:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')
            return
        module = importlib.import_module(module_name)
        # Temporarily mix the api handler's methods into this Router instance
        # so that handler-private methods (e.g. _get_selections) are reachable.
        original_class = self.__class__
        self.__class__ = type('_Dispatch', (module.handler, Router), {})
        try:
            fn = getattr(self, f'do_{method}', None)
            if fn is None:
                self.send_response(405)
                self.end_headers()
                return
            fn()
        finally:
            self.__class__ = original_class

    def do_GET(self):     self._dispatch('GET')
    def do_POST(self):    self._dispatch('POST')
    def do_PUT(self):     self._dispatch('PUT')
    def do_PATCH(self):   self._dispatch('PATCH')
    def do_DELETE(self):  self._dispatch('DELETE')
    def do_OPTIONS(self): self._dispatch('OPTIONS')

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()} — {fmt % args}')


if __name__ == '__main__':
    port = int(os.environ.get('DEV_API_PORT', 3001))
    server = HTTPServer(('', port), Router)
    print(f'API dev server → http://localhost:{port}')
    print(f'DEV_BYPASS_AUTH = {os.environ.get("DEV_BYPASS_AUTH", "not set")}')
    server.serve_forever()
