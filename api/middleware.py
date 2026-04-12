"""
Centralized security middleware: CORS, rate limiting, CSRF, authentication, input validation.
"""
import os
import json
import time
import hmac
import hashlib
from collections import defaultdict


# --- CORS ---

def get_cors_headers():
    """Return CORS headers using the configured allowed origin."""
    origin = os.environ.get('ALLOWED_ORIGIN', 'http://localhost:5173')
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-CSRF-Token",
        "Access-Control-Allow-Credentials": "true",
    }


def send_json(handler, status_code, body, extra_headers=None):
    """Send a JSON response with CORS headers."""
    payload = json.dumps(body, default=str).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    for key, value in get_cors_headers().items():
        handler.send_header(key, value)
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(payload)


def send_sse_headers(handler):
    """Send HTTP headers for a Server-Sent Events response."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    for key, value in get_cors_headers().items():
        handler.send_header(key, value)
    handler.end_headers()


def send_sse_event(handler, data: dict):
    """Write a single SSE data frame and flush."""
    payload = "data: " + json.dumps(data, default=str) + "\n\n"
    handler.wfile.write(payload.encode("utf-8"))
    handler.wfile.flush()


def handle_options(handler):
    """Handle CORS preflight requests."""
    handler.send_response(204)
    for key, value in get_cors_headers().items():
        handler.send_header(key, value)
    handler.end_headers()


# --- Rate Limiting ---

_rate_store = defaultdict(list)


def check_rate_limit(handler, max_rpm=None):
    """
    In-memory per-IP rate limiting.
    Returns True if the request is within limits, False otherwise.
    Resets on cold start (acceptable for serverless).
    """
    if max_rpm is None:
        max_rpm = int(os.environ.get('RATE_LIMIT_RPM', '30'))
    client_ip = handler.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not client_ip:
        client_ip = handler.client_address[0] if handler.client_address else 'unknown'
    now = time.time()
    window = 60
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < window]
    if len(_rate_store[client_ip]) >= max_rpm:
        return False
    _rate_store[client_ip].append(now)
    return True


# --- CSRF ---

def generate_csrf_token(session_token):
    """Generate an HMAC-based CSRF token tied to a session."""
    secret = os.environ.get('SESSION_SECRET', '')
    return hmac.new(secret.encode(), session_token.encode(), hashlib.sha256).hexdigest()


def verify_csrf_token(handler, session_token):
    """Verify the X-CSRF-Token header matches the expected CSRF token."""
    provided = handler.headers.get('X-CSRF-Token', '')
    expected = generate_csrf_token(session_token)
    return hmac.compare_digest(provided, expected)


def _parse_cookie(cookie_header, name):
    """Extract a named value from a Cookie header string."""
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith(name + '='):
            return part[len(name) + 1:].strip()
    return None


def set_session_cookie(token, clear=False):
    """Build a Set-Cookie header value for the session cookie.

    Uses VERCEL_ENV to determine cookie attributes:
    - production/preview: Secure; SameSite=Strict
    - development/local: SameSite=Lax (no Secure, works over HTTP)
    """
    is_https = os.environ.get('VERCEL_ENV') in ('production', 'preview')
    max_age = 0 if clear else 86400
    value = '' if clear else token
    attrs = [f"cm_session={value}", "HttpOnly", f"Max-Age={max_age}", "Path=/"]
    if is_https:
        attrs += ["Secure", "SameSite=Strict"]
    else:
        attrs.append("SameSite=Lax")
    return "; ".join(attrs)


# --- Session Authentication ---

def authenticate_request(handler):
    """
    Extract and validate session token from HttpOnly cookie.
    Returns (google_id, session_token) tuple, or (None, None) if invalid.
    """
    # Local dev bypass: skip cookie/DB checks entirely
    if os.environ.get('DEV_BYPASS_AUTH') == 'true':
        google_id = os.environ.get('DEV_USER_GOOGLE_ID')
        session_token = os.environ.get('DEV_SESSION_TOKEN', 'dev-bypass-session')
        return google_id, session_token

    # Primary: HttpOnly cookie
    session_token = _parse_cookie(handler.headers.get('Cookie', ''), 'cm_session')
    if not session_token:
        return None, None
    from .db import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT google_id FROM sessions
            WHERE session_token = %s
              AND revoked = FALSE
              AND expires_at > CURRENT_TIMESTAMP
        """, (session_token,))
        row = cursor.fetchone()
        cursor.close()
    if row:
        return row['google_id'], session_token
    return None, None


# --- Input Validation ---

def sanitize_string(value, max_length=500):
    """Sanitize a string input: strip, truncate, remove control characters."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    value = ''.join(c for c in value if c.isprintable() or c in ('\n', '\t'))
    return value
