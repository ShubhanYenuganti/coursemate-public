-- Per-user last time a course shell was opened (for dashboard ordering).
CREATE TABLE IF NOT EXISTS user_course_opens (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_user_course_opens_user_opened
    ON user_course_opens (user_id, opened_at DESC);
