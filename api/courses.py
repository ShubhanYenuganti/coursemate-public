"""
Course model for database operations.
"""
import json
from typing import Optional, Dict, Any, List
from .db import get_db


class Course:
    """Course model for managing courses in the database."""

    @staticmethod
    def create(
        title: str,
        primary_creator: int,
        description: Optional[str] = None,
        status: str = 'draft',
        visibility: str = 'private',
        cover_image_url: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new course.
        
        Args:
            title: Course title
            primary_creator: User ID of the primary creator
            description: Course description
            status: 'draft', 'published', or 'archived' (default: 'draft')
            visibility: 'private', 'shared', or 'public' (default: 'private')
            cover_image_url: URL to cover image
            tags: List of tag strings
            
        Returns:
            Dict containing the created course record
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            tags_json = json.dumps(tags or [])
            
            cursor.execute("""
                INSERT INTO courses (
                    title, description, primary_creator, status,
                    visibility, cover_image_url, tags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                title, description, primary_creator, status,
                visibility, cover_image_url, tags_json
            ))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course)

    @staticmethod
    def get_by_id(course_id: int) -> Optional[Dict[str, Any]]:
        """Get a course by its ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def get_by_creator(
        creator_id: int,
        include_co_created: bool = False,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all courses created by a user.
        
        Args:
            creator_id: User ID of the creator
            include_co_created: If True, also returns courses where user is a co-creator
            status_filter: Optional filter by status ('draft', 'published', 'archived')
            
        Returns:
            List of course records
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            if include_co_created:
                # Use JSONB containment operator to check co_creator_ids
                query = """
                    SELECT * FROM courses
                    WHERE primary_creator = %s
                       OR co_creator_ids @> %s::jsonb
                """
                params = [creator_id, json.dumps([creator_id])]
            else:
                query = "SELECT * FROM courses WHERE primary_creator = %s"
                params = [creator_id]
            
            if status_filter:
                query += " AND status = %s"
                params.append(status_filter)
            
            query += " ORDER BY updated_at DESC"
            
            cursor.execute(query, params)
            courses = cursor.fetchall()
            cursor.close()
            return [dict(course) for course in courses]

    @staticmethod
    def update(
        course_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        cover_image_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update course basic information.
        
        Args:
            course_id: ID of the course to update
            title: New title (if provided)
            description: New description (if provided)
            cover_image_url: New cover image URL (if provided)
            
        Returns:
            Updated course record or None if not found
        """
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = %s")
            params.append(title)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if cover_image_url is not None:
            updates.append("cover_image_url = %s")
            params.append(cover_image_url)
        
        if not updates:
            return Course.get_by_id(course_id)
        
        params.append(course_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE courses
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING *
            """, params)
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def delete(course_id: int) -> bool:
        """
        Delete a course.
        
        Returns:
            True if course was deleted, False if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM courses WHERE id = %s RETURNING id", (course_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None

    @staticmethod
    def update_status(course_id: int, status: str) -> Optional[Dict[str, Any]]:
        """
        Update course status.
        
        Args:
            course_id: ID of the course
            status: 'draft', 'published', or 'archived'
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET status = %s
                WHERE id = %s
                RETURNING *
            """, (status, course_id))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def update_visibility(course_id: int, visibility: str) -> Optional[Dict[str, Any]]:
        """
        Update course visibility.
        
        Args:
            course_id: ID of the course
            visibility: 'private', 'shared', or 'public'
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET visibility = %s
                WHERE id = %s
                RETURNING *
            """, (visibility, course_id))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def add_material(course_id: int, material_id: int) -> Optional[Dict[str, Any]]:
        """
        Add a material to the course's material_ids array.
        
        Args:
            course_id: ID of the course
            material_id: ID of the material to add
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET material_ids = material_ids || %s::jsonb
                WHERE id = %s
                  AND NOT material_ids @> %s::jsonb
                RETURNING *
            """, (json.dumps([material_id]), course_id, json.dumps([material_id])))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def remove_material(course_id: int, material_id: int) -> Optional[Dict[str, Any]]:
        """
        Remove a material from the course's material_ids array.
        
        Args:
            course_id: ID of the course
            material_id: ID of the material to remove
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET material_ids = material_ids - %s::text
                WHERE id = %s
                RETURNING *
            """, (str(material_id), course_id))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def add_co_creator(course_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Add a co-creator to the course.
        
        Args:
            course_id: ID of the course
            user_id: ID of the user to add as co-creator
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET co_creator_ids = co_creator_ids || %s::jsonb
                WHERE id = %s
                  AND NOT co_creator_ids @> %s::jsonb
                RETURNING *
            """, (json.dumps([user_id]), course_id, json.dumps([user_id])))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def remove_co_creator(course_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Remove a co-creator from the course.
        
        Args:
            course_id: ID of the course
            user_id: ID of the user to remove
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE courses
                SET co_creator_ids = co_creator_ids - %s::text
                WHERE id = %s
                RETURNING *
            """, (str(user_id), course_id))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def add_tags(course_id: int, tags: List[str]) -> Optional[Dict[str, Any]]:
        """
        Add tags to a course (merges with existing tags, no duplicates).
        
        Args:
            course_id: ID of the course
            tags: List of tag strings to add
            
        Returns:
            Updated course record or None if not found
        """
        with get_db() as conn:
            cursor = conn.cursor()
            # Get existing tags, merge, deduplicate
            cursor.execute("SELECT tags FROM courses WHERE id = %s", (course_id,))
            result = cursor.fetchone()
            
            if not result:
                cursor.close()
                return None
            
            existing_tags = result['tags'] or []
            merged_tags = list(set(existing_tags + tags))
            
            cursor.execute("""
                UPDATE courses
                SET tags = %s::jsonb
                WHERE id = %s
                RETURNING *
            """, (json.dumps(merged_tags), course_id))
            
            course = cursor.fetchone()
            cursor.close()
            return dict(course) if course else None

    @staticmethod
    def verify_access(course_id: int, user_id: int) -> bool:
        """
        Check if a user has access to a course (is creator or co-creator).
        
        Args:
            course_id: ID of the course
            user_id: ID of the user
            
        Returns:
            True if user has access, False otherwise
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM courses
                WHERE id = %s
                  AND (primary_creator = %s OR co_creator_ids @> %s::jsonb)
            """, (course_id, user_id, json.dumps([user_id])))
            
            result = cursor.fetchone()
            cursor.close()
            return result is not None