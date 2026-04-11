"""Shared utilities for integration poller handlers."""

from datetime import datetime, timezone


def _needs_ingest(api_time_str: str, db_time) -> bool:
    """Return True if the external file needs to be re-ingested.

    Returns True when:
      - db_time is absent/falsy (file never successfully ingested)
      - either timestamp cannot be parsed (safe default: re-ingest)
      - api_time > db_time (file has been modified since last ingest)

    Returns False only when api_time <= db_time.
    """
    if not db_time:
        return True
    try:
        api_dt = datetime.fromisoformat(str(api_time_str).replace("Z", "+00:00"))
        if api_dt.tzinfo is None:
            api_dt = api_dt.replace(tzinfo=timezone.utc)

        db_dt = datetime.fromisoformat(str(db_time).replace("Z", "+00:00"))
        if db_dt.tzinfo is None:
            db_dt = db_dt.replace(tzinfo=timezone.utc)

        return api_dt > db_dt
    except Exception:
        return True
