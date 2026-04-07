"""
AWS Lambda handler — integration_poller

Triggered two ways:
  1. EventBridge Scheduler (every 2h) — event: {} or { "source": "eventbridge" }
  2. Direct invocation from /api/notion?action=sync — event: { "user_id": N, "course_id": N }

When user_id + course_id are provided, only that user's active source points for that
course are processed. Otherwise all active source points across all users are processed.
"""
import json
import os

from db import get_db

try:
    from handlers.notion import sync_source_point as notion_sync
except ImportError:
    from integration_poller.handlers.notion import sync_source_point as notion_sync


def _get_notion_token(user_id: int):
    """Decrypt and return the Notion token for a user, or None."""
    import sys
    sys.path.insert(0, '/var/task')
    # crypto_utils lives in the api layer — replicate decrypt inline for Lambda isolation
    import base64
    import os as _os
    key_b64 = _os.environ.get('FERNET_KEY')
    if not key_b64:
        return None
    from cryptography.fernet import Fernet
    fernet = Fernet(key_b64.encode())
    with get_db() as db:
        row = db.execute(
            "SELECT encrypted_token FROM user_integrations WHERE user_id = %s AND provider = 'notion'",
            (user_id,)
        ).fetchone()
    if not row:
        return None
    return fernet.decrypt(row['encrypted_token'].encode()).decode()


def lambda_handler(event, context):
    user_id_filter = event.get('user_id')
    course_id_filter = event.get('course_id')

    with get_db() as db:
        if user_id_filter and course_id_filter:
            rows = db.execute("""
                SELECT * FROM integration_source_points
                WHERE is_active = true
                  AND user_id = %s
                  AND course_id = %s
            """, (user_id_filter, course_id_filter)).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM integration_source_points WHERE is_active = true"
            ).fetchall()

    results = []
    for sp in rows:
        sp = dict(sp)
        provider = sp.get('provider')
        try:
            if provider == 'notion':
                token = _get_notion_token(sp['user_id'])
                if not token:
                    results.append({'id': sp['id'], 'status': 'skipped', 'reason': 'no_token'})
                    continue
                notion_sync(sp, token)
                results.append({'id': sp['id'], 'status': 'ok'})
            else:
                results.append({'id': sp['id'], 'status': 'skipped', 'reason': f'unknown_provider:{provider}'})
        except Exception as exc:
            print(f"[integration_poller] source_point {sp['id']} failed: {exc}")
            results.append({'id': sp['id'], 'status': 'error', 'error': str(exc)})

    return {
        'total': len(results),
        'ok': sum(1 for r in results if r['status'] == 'ok'),
        'results': results,
    }
