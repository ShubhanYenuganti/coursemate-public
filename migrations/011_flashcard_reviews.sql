-- 011_flashcard_reviews.sql — per-user spaced-repetition state for flashcards.
CREATE TABLE IF NOT EXISTS flashcard_reviews (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id INTEGER NOT NULL,
    card_index    INTEGER NOT NULL,
    last_rating   TEXT,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease          REAL    NOT NULL DEFAULT 2.5,
    due_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, generation_id, card_index)
);

CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_due ON flashcard_reviews (user_id, due_at);
