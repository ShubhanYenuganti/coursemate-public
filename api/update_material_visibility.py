# Vercel Python Serverless Function — Update Material Visibility
# Endpoint: POST /api/update_material_visibility

import json
from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User, Material
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User, Material


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return

        material_id = data.get('material_id')
        visibility = data.get('visibility')

        if not material_id or visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "material_id and visibility ('public' or 'private') are required"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        material = Material.get_by_id(material_id)
        if not material:
            send_json(self, 404, {"error": "Material not found"})
            return

        if material['uploaded_by'] != user['id']:
            send_json(self, 403, {"error": "Only the uploader can change visibility"})
            return

        updated = Material.update_visibility(material_id, visibility)
        send_json(self, 200, {"material": updated})
