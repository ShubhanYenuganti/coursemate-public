"""
User and Session models for database operations.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from .db import get_db


class User:
    """User model representing a user in the database."""

    @staticmethod
    def create_or_update(
        google_id: str,
        email: str,
        email_verified: bool = False,
        name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        picture: Optional[str] = None,
        locale: Optional[str] = None,
        address: Optional[str] = None,
        google_id_token: Optional[str] = None,
        google_access_token: Optional[str] = None,
        google_refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create a new user or update existing user. Returns the user record."""
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM users WHERE google_id = %s",
                (google_id,)
            )
            existing_user = cursor.fetchone()

            if existing_user:
                cursor.execute("""
                    UPDATE users
                    SET email = %s,
                        email_verified = %s,
                        name = %s,
                        given_name = %s,
                        family_name = %s,
                        picture = %s,
                        locale = %s,
                        address = COALESCE(%s, address),
                        google_id_token = COALESCE(%s, google_id_token),
                        google_access_token = COALESCE(%s, google_access_token),
                        google_refresh_token = COALESCE(%s, google_refresh_token),
                        token_expires_at = COALESCE(%s, token_expires_at),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE google_id = %s
                    RETURNING *
                """, (
                    email, email_verified, name, given_name, family_name,
                    picture, locale, address, google_id_token,
                    google_access_token, google_refresh_token, token_expires_at,
                    google_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO users (
                        google_id, email, email_verified, name, given_name, family_name,
                        picture, locale, address, google_id_token,
                        google_access_token, google_refresh_token, token_expires_at,
                        username
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    google_id, email, email_verified, name, given_name, family_name,
                    picture, locale, address, google_id_token,
                    google_access_token, google_refresh_token, token_expires_at,
                    name  # seed username from name on first sign-in
                ))

            user = cursor.fetchone()
            cursor.close()

            return dict(user)

    @staticmethod
    def get_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Google ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE google_id = %s",
                (google_id,)
            )
            user = cursor.fetchone()
            cursor.close()
            return dict(user) if user else None

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()
            cursor.close()
            return dict(user) if user else None

    @staticmethod
    def update_address(google_id: str, address: str) -> Optional[Dict[str, Any]]:
        """Update user's address."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET address = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE google_id = %s
                RETURNING *
            """, (address, google_id))

            user = cursor.fetchone()
            cursor.close()
            return dict(user) if user else None

    @staticmethod
    def update_username(google_id: str, username: str) -> Optional[Dict[str, Any]]:
        """Update user's display username (independent from the static Google name field)."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET username = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE google_id = %s
                RETURNING *
            """, (username, google_id))
            user = cursor.fetchone()
            cursor.close()
            return dict(user) if user else None

    @staticmethod
    def delete_user(google_id: str) -> bool:
        """Delete a user record. Returns True if a row was deleted."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE google_id = %s", (google_id,))
            cursor.execute(
                "DELETE FROM users WHERE google_id = %s RETURNING id",
                (google_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            return result is not None


class Material:
    """Material model for managing uploaded course materials."""

    @staticmethod
    def create(
        course_id: int,
        name: str,
        file_url: str,
        uploaded_by: int,
        file_type: Optional[str] = None,
        visibility: str = 'private',
        source_type: str = 'upload',
    ) -> Dict[str, Any]:
        """Insert a new material record and return it."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO materials (course_id, name, file_url, uploaded_by, file_type, visibility, source_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (course_id, name, file_url, uploaded_by, file_type, visibility, source_type))
            material = cursor.fetchone()
            cursor.close()
            return dict(material)

    @staticmethod
    def get_by_id(material_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single material record by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM materials WHERE id = %s", (material_id,))
            material = cursor.fetchone()
            cursor.close()
            return dict(material) if material else None

    @staticmethod
    def get_by_course(course_id: int, user_id: int) -> list:
        """
        Return all materials for a course visible to this user:
        public materials + materials uploaded by the user.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM materials
                WHERE course_id = %s
                  AND (visibility = 'public' OR uploaded_by = %s)
                ORDER BY created_at DESC
            """, (course_id, user_id))
            materials = cursor.fetchall()
            cursor.close()
            return [dict(m) for m in materials]

    @staticmethod
    def update_visibility(material_id: int, visibility: str) -> Optional[Dict[str, Any]]:
        """Change a material's visibility. Returns updated record or None if not found."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE materials
                SET visibility = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            """, (visibility, material_id))
            material = cursor.fetchone()
            cursor.close()
            return dict(material) if material else None

    @staticmethod
    def delete(material_id: int) -> bool:
        """Delete a material record. Returns True if a row was deleted."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM materials WHERE id = %s RETURNING id", (material_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None


class Session:
    """Session model for server-side session management."""

    @staticmethod
    def create(google_id: str, ttl_hours: int = 24) -> Dict[str, Any]:
        """Create a new session. Returns session_token and expires_at."""
        token = secrets.token_hex(64)
        expires = datetime.utcnow() + timedelta(hours=ttl_hours)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_token, google_id, expires_at)
                VALUES (%s, %s, %s)
                RETURNING session_token, expires_at
            """, (token, google_id, expires))
            result = cursor.fetchone()
            cursor.close()
        return dict(result)

    @staticmethod
    def revoke(session_token: str) -> bool:
        """Revoke a specific session. Returns True if a session was revoked."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET revoked = TRUE
                WHERE session_token = %s AND revoked = FALSE
                RETURNING id
            """, (session_token,))
            result = cursor.fetchone()
            cursor.close()
        return result is not None

    @staticmethod
    def revoke_all(google_id: str) -> None:
        """Revoke all active sessions for a user (force logout everywhere)."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET revoked = TRUE
                WHERE google_id = %s AND revoked = FALSE
            """, (google_id,))
            cursor.close()
