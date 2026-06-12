from api.flashcards import due_summary_sql


def test_due_summary_sql_filters_by_user_and_now():
    sql = due_summary_sql()
    low = sql.lower()
    assert 'flashcard_reviews' in low
    assert 'due_at <= now()' in low
    assert 'user_id = %s' in low
