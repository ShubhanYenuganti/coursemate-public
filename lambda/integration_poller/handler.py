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

import time

try:
    from handlers.notion import sync_source_point as notion_sync
    from handlers.gdrive import sync_source_point as gdrive_sync
except ImportError:
    from integration_poller.handlers.notion import sync_source_point as notion_sync
    from integration_poller.handlers.gdrive import sync_source_point as gdrive_sync


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


def _get_gdrive_token(user_id: int):
    """
    Decrypt the stored Drive token JSON, refresh the access token if near expiry,
    and return a valid access token string. Returns None if no token is stored.
    """
    import base64
    import os as _os
    key_b64 = _os.environ.get('FERNET_KEY')
    if not key_b64:
        return None
    from cryptography.fernet import Fernet
    fernet = Fernet(key_b64.encode())
    with get_db() as db:
        row = db.execute(
            "SELECT encrypted_token FROM user_integrations WHERE user_id = %s AND provider = 'gdrive'",
            (user_id,)
        ).fetchone()
    if not row:
        return None

    payload = json.loads(fernet.decrypt(row['encrypted_token'].encode()).decode())
    access_token = payload.get('access_token')
    refresh_token = payload.get('refresh_token')
    expires_at = payload.get('expires_at', 0)
    import time as _time
    print(f'[integration_poller] gdrive token debug user_id={user_id} '
          f'keys={list(payload.keys())} '
          f'has_access_token={bool(access_token)} '
          f'has_refresh_token={bool(refresh_token)} '
          f'expires_at={expires_at} '
          f'now={_time.time():.0f} '
          f'near_expiry={_time.time() >= expires_at - 300}')

    # Refresh if within 5 minutes of expiry
    if time.time() >= expires_at - 300:
        gdrive_client_id = _os.environ.get('GOOGLE_CLIENT_ID', '').strip()
        gdrive_client_secret = _os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
        if gdrive_client_id and gdrive_client_secret and refresh_token:
            import requests as _req
            resp = _req.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': gdrive_client_id,
                    'client_secret': gdrive_client_secret,
                },
                timeout=15,
            )
            if resp.ok:
                token_data = resp.json()
                access_token = token_data['access_token']
                new_expires_in = token_data.get('expires_in', 3600)
                payload['access_token'] = access_token
                payload['expires_at'] = time.time() + new_expires_in
                new_encrypted = fernet.encrypt(json.dumps(payload).encode()).decode()
                with get_db() as db:
                    db.execute(
                        "UPDATE user_integrations SET encrypted_token = %s WHERE user_id = %s AND provider = 'gdrive'",
                        (new_encrypted, user_id)
                    )
            else:
                print(f'[integration_poller] gdrive token refresh failed user_id={user_id}: {resp.text}')
                return None
        else:
            print(f'[integration_poller] gdrive token near expiry but no credentials to refresh user_id={user_id} — skipping')
            return None

    return access_token


def lambda_handler(event, context):
    user_id_filter = event.get('user_id')
    course_id_filter = event.get('course_id')
    source_point_id_filter = event.get('source_point_id')
    force_full_sync = bool(event.get('force_full_sync', False))
    external_ids = event.get('external_ids') or None
    print(
        f'[integration_poller] lambda_handler start '
        f'user_id_filter={user_id_filter} course_id_filter={course_id_filter} '
        f'source_point_id_filter={source_point_id_filter} force_full_sync={force_full_sync}'
    )

    with get_db() as db:
        if source_point_id_filter:
            rows = db.execute("""
                SELECT * FROM integration_source_points
                WHERE is_active = true
                  AND id = %s
            """, (source_point_id_filter,)).fetchall()
        elif user_id_filter and course_id_filter:
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
    print(f'[integration_poller] source_points selected count={len(rows)}')

    results = []
    for sp in rows:
        sp = dict(sp)
        provider = sp.get('provider')
        print(
            f'[integration_poller] processing source_point_id={sp.get("id")} '
            f'provider={provider} user_id={sp.get("user_id")} course_id={sp.get("course_id")}'
        )
        try:
            if provider == 'notion':
                token = _get_notion_token(sp['user_id'])
                if not token:
                    print(f'[integration_poller] source_point_id={sp["id"]} skipped: no notion token')
                    results.append({'id': sp['id'], 'status': 'skipped', 'reason': 'no_token'})
                    continue
                print(f'[integration_poller] source_point_id={sp["id"]} notion token resolved')
                notion_sync(sp, token, force_full_sync=force_full_sync, external_ids=external_ids)
                print(f'[integration_poller] source_point_id={sp["id"]} notion sync completed')
                results.append({'id': sp['id'], 'status': 'ok'})
            elif provider == 'gdrive':
                token = _get_gdrive_token(sp['user_id'])
                if not token:
                    print(f'[integration_poller] source_point_id={sp["id"]} skipped: no gdrive token')
                    results.append({'id': sp['id'], 'status': 'skipped', 'reason': 'no_token'})
                    continue
                print(f'[integration_poller] source_point_id={sp["id"]} gdrive token resolved')
                gdrive_sync(sp, token, force_full_sync=force_full_sync, external_ids=external_ids)
                print(f'[integration_poller] source_point_id={sp["id"]} gdrive sync completed')
                results.append({'id': sp['id'], 'status': 'ok'})
            else:
                print(f'[integration_poller] source_point_id={sp["id"]} skipped: unknown provider {provider}')
                results.append({'id': sp['id'], 'status': 'skipped', 'reason': f'unknown_provider:{provider}'})
        except Exception as exc:
            print(f"[integration_poller] source_point {sp['id']} failed: {exc}")
            results.append({'id': sp['id'], 'status': 'error', 'error': str(exc)})

    print(
        f'[integration_poller] lambda_handler complete total={len(results)} '
        f'ok={sum(1 for r in results if r["status"] == "ok")}'
    )
    return {
        'total': len(results),
        'ok': sum(1 for r in results if r['status'] == 'ok'),
        'results': results,
    }
