-- 010_pending_invites.sql - invites for users who have not signed up yet.
CREATE TABLE IF NOT EXISTS pending_invites (
    id            SERIAL PRIMARY KEY,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    email         TEXT    NOT NULL,
    invited_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (course_id, email)
);

CREATE INDEX IF NOT EXISTS idx_pending_invites_email ON pending_invites (email);
