Perfect! I understand your requirements. Let me create a comprehensive plan focused on the AWS S3 infrastructure, backend API, and visibility controls.

## Plan: AWS S3 Material Storage with Privacy Controls

This plan implements S3-backed file storage for course materials with public/private visibility controls. Any user can upload/delete materials, but private materials are only accessible/referenceable by their uploader. Uses presigned URLs to bypass Vercel's 10MB request limit.

**Key decisions:**
- **Presigned URL uploads**: Frontend uploads directly to S3 (client → S3), avoiding Vercel serverless limits
- **Privacy model**: `visibility` field ('private'/'public') controls who can reference materials, not just who uploaded them
- **S3 organization**: Flat structure with UUID filenames to prevent collisions and obscure file paths
- **Bucket policy**: Private bucket with signed URLs for access (no public reads)

**Steps**

1. **AWS S3 Bucket Setup**
   - Create S3 bucket (e.g., `oneshot-coursemate-materials`) with:
     - Block all public access enabled
     - Versioning disabled (optional: enable for recovery)
     - Server-side encryption (SSE-S3 or SSE-KMS)
   - Configure CORS to allow uploads from your frontend origin
   - Create IAM user `coursemate-s3-uploader` with programmatic access
   - Attach custom IAM policy for `PutObject`, `GetObject`, `DeleteObject` on bucket
   - Save Access Key ID and Secret Access Key for environment variables

2. **Environment Configuration**
   - Add to `.env` (backend only, NOT `VITE_` prefixed):
     - `AWS_ACCESS_KEY_ID`
     - `AWS_SECRET_ACCESS_KEY`
     - `AWS_REGION` (e.g., `us-east-1`)
     - `AWS_S3_BUCKET_NAME`
   - Add `boto3` to [requirements.txt](requirements.txt)

3. **Database Adjustments**
   - Verify [api/models.py](api/models.py) `materials` table schema has:
     - `file_url` (TEXT) - will store `s3://bucket/key` or full HTTPS URL
     - `visibility` (VARCHAR) - 'private' or 'public'
     - `uploaded_by` (INTEGER) - user ID for ownership
     - `file_type` (VARCHAR) - MIME type for validation
     - `source_type` (VARCHAR) - set to 'upload' for S3 uploads
    - If the live schema is not aligned, alter `init_db` in [api/db.py](api/db.py) to create/update the `materials` table with the required columns, constraints, and indexes (including safe migrations for existing deployments).
   - Create `Material` model class in [api/models.py](api/models.py) with methods:
     - `create()` - Insert material record
     - `get_by_id()` - Fetch single material with uploader check
     - `get_by_course()` - Fetch course materials filtered by visibility and user
     - `update_visibility()` - Change public/private status
     - `delete()` - Remove record

4. **Create Upload API Endpoint** - `api/upload_material.py`
   - Authenticate user via `authenticate_request()`
   - Accept: `{course_id, filename, file_type, visibility}`
   - Validate:
     - File type against whitelist (PDF, DOCX, TXT, JPEG, PNG, GIF, SVG, XLSX, CSV)
     - Filename sanitization
     - User has course access via `Course.verify_access()`
   - Generate UUID-based S3 key: `materials/{uuid4()}.{extension}`
   - Use `boto3.client('s3').generate_presigned_post()` with:
     - 5-minute expiration
     - 10MB size limit condition
     - Content-Type condition
   - Return: `{upload_url, fields, material_id (temp), s3_key}`
   - Store pending upload in session or return `s3_key` for confirmation

5. **Create Confirmation API Endpoint** - `api/confirm_upload.py`
   - Authenticate user
   - Accept: `{s3_key, course_id, filename, file_type, visibility}`
   - Verify S3 object exists via `head_object()`
   - Create material record via `Material.create()`:
     - `file_url`: `https://{bucket}.s3.{region}.amazonaws.com/{key}`
     - `uploaded_by`: user ID
     - `course_id`, `file_type`, `visibility`, `source_type='upload'`
   - Link to course via `Course.add_material(course_id, material_id)`
   - Return: `{material: {id, name, file_url, file_type, visibility, ...}}`

6. **Create Get Materials API Endpoint** - `api/get_materials.py`
   - Authenticate user
   - Accept: `{course_id}`
   - Fetch materials via `Material.get_by_course(course_id, user_id)`:
     - Query: `SELECT * FROM materials WHERE course_id = %s AND (visibility = 'public' OR uploaded_by = %s)`
   - For each material, generate presigned download URL (1-hour expiration):
     - `boto3.client('s3').generate_presigned_url('get_object', ...)`
   - Return: `{materials: [{id, name, file_url, download_url, file_type, visibility, ...}]}`

7. **Create Delete Material API Endpoint** - `api/delete_material.py`
   - Authenticate user
   - Accept: `{material_id, course_id}`
   - Fetch material via `Material.get_by_id(material_id)`
   - Verify user can delete (check `uploaded_by` matches user_id OR is course creator)
   - Delete from S3: `boto3.client('s3').delete_object(Bucket, Key)`
   - Remove from course: `Course.remove_material(course_id, material_id)`
   - Delete record: `Material.delete(material_id)`
   - Return: `{success: true}`

8. **Create Update Visibility API Endpoint** - `api/update_material_visibility.py`
   - Authenticate user
   - Accept: `{material_id, visibility}` ('private' or 'public')
   - Fetch material via `Material.get_by_id(material_id)`
   - Verify user is uploader (`uploaded_by` matches user_id)
   - Update: `Material.update_visibility(material_id, visibility)`
   - Return: `{material: {...}}`

9. **Create S3 Utility Module** - `api/s3_utils.py`
   - Initialize boto3 S3 client with credentials from env vars
   - Helper functions:
     - `generate_upload_presigned_url(s3_key, file_type, max_size)`
     - `generate_download_presigned_url(s3_key, expiration=3600)`
     - `verify_file_exists(s3_key)`
     - `delete_file(s3_key)`
     - `get_file_extension(filename)`
     - `validate_file_type(file_type, allowed_types)`

**Verification**

1. **S3 Bucket Test**:
   - Use AWS CLI: `aws s3 ls s3://oneshot-coursemate-materials` (should be empty)
   - Verify IAM user can access: `aws s3 cp test.txt s3://bucket/ --profile coursemate`

2. **Upload Flow Test**:
   - Call `POST /api/upload_material` → receive presigned URL
   - Upload file to presigned URL using curl/Postman
   - Call `POST /api/confirm_upload` → material record created
   - Verify in PostgreSQL: `SELECT * FROM materials WHERE source_type='upload'`
   - Check S3: Object exists at expected key

3. **Privacy Test**:
   - Upload private material as User A
   - Call `GET /api/get_materials` as User B → private material not returned
   - Call `GET /api/get_materials` as User A → private material appears

4. **Delete Test**:
   - Call `DELETE /api/delete_material` → record removed
   - Verify S3 object deleted: `aws s3 ls s3://bucket/materials/{key}` (not found)

**Decisions**
- **Chose presigned URLs over direct upload**: Avoids Vercel's 10MB request body limit
- **Chose flat S3 structure with UUIDs**: Prevents filename collisions, hides file structure from users
- **Chose private bucket with signed URLs**: More secure than public bucket, gives fine-grained access control
- **Chose two-step upload (request → confirm)**: Allows frontend to handle upload progress, backend only records successful uploads

---

Does this plan address your needs? I can refine any section before you proceed with implementation.