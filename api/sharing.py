# Vercel Python Serverless Function — Course Sharing
# GET  /api/sharing?course_id=X  → list collaborators
# POST /api/sharing               → invite by email (auto-accept)
# DELETE /api/sharing             → remove collaborator

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .courses import Course
    from .models import User, PendingInvite
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from courses import Course
    from models import User, PendingInvite


def _serialize_member(m: dict) -> dict:
    return {
        "id": m["id"],
        "name": m["name"],
        "email": m["email"],
        "picture": m.get("picture"),
        "role": m["role"],
        "joined_at": m["joined_at"].isoformat() if m.get("joined_at") else None,
        "invited_by_name": m.get("invited_by_name"),
    }


def invite_member(google_id: str, course_id: int, email: str):
    email = (email or "").lower().strip()
    inviter = User.get_by_google_id(google_id)
    if not inviter:
        return 404, {"error": "User not found"}

    course = Course.get_by_id(course_id)
    if not course:
        return 404, {"error": "Course not found"}

    if course["primary_creator"] != inviter["id"]:
        return 403, {"error": "Only the course owner can invite collaborators"}

    invitee = User.get_by_email(email)
    if invitee is None:
        PendingInvite.create(course_id, email, inviter["id"])
        return 200, {
            "members": [_serialize_member(m) for m in Course.get_members(course_id)],
            "pending": PendingInvite.list_for_course(course_id),
            "status": "pending",
        }

    if invitee["id"] == inviter["id"]:
        return 400, {"error": "You cannot invite yourself"}

    if not Course.add_member(course_id, invitee["id"], inviter["id"]):
        return 409, {"error": "User is already a collaborator on this course"}

    return 200, {
        "members": [_serialize_member(m) for m in Course.get_members(course_id)],
        "pending": PendingInvite.list_for_course(course_id),
        "status": "added",
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        qs = parse_qs(urlparse(self.path).query)
        course_id_raw = qs.get("course_id", [None])[0]
        if not course_id_raw or not course_id_raw.isdigit():
            send_json(self, 400, {"error": "course_id is required"})
            return
        course_id = int(course_id_raw)

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user["id"]):
            send_json(self, 403, {"error": "Access denied"})
            return

        members = Course.get_members(course_id)
        send_json(self, 200, {
            "members": [_serialize_member(m) for m in members],
            "pending": PendingInvite.list_for_course(course_id),
        })

    # ----------------------------------------------------------------- POST --
    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return

        course_id = data.get("course_id")
        email = sanitize_string(data.get("email", ""), max_length=320).lower().strip()

        if not isinstance(course_id, int) or not email:
            send_json(self, 400, {"error": "course_id and email are required"})
            return

        status, payload = invite_member(google_id, course_id, email)
        send_json(self, status, payload)

    # --------------------------------------------------------------- DELETE --
    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return

        course_id = data.get("course_id")
        user_id = data.get("user_id")
        email = sanitize_string(data.get("email", ""), max_length=320).lower().strip()

        if not isinstance(course_id, int) or (not isinstance(user_id, int) and not email):
            send_json(self, 400, {"error": "course_id and user_id or email are required"})
            return

        requester = User.get_by_google_id(google_id)
        if not requester:
            send_json(self, 404, {"error": "User not found"})
            return

        course = Course.get_by_id(course_id)
        if not course:
            send_json(self, 404, {"error": "Course not found"})
            return

        if course["primary_creator"] != requester["id"]:
            send_json(self, 403, {"error": "Only the course owner can remove collaborators"})
            return

        if email:
            PendingInvite.revoke(course_id, email)
        else:
            Course.remove_member(course_id, user_id)
        members = Course.get_members(course_id)
        send_json(self, 200, {
            "members": [_serialize_member(m) for m in members],
            "pending": PendingInvite.list_for_course(course_id),
        })
