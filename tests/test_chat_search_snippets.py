import sys, os, types

# Stub out every module that chat.py tries to import so we can reach
# _content_match_from_row without a live DB / Vercel environment.
def _make_stub(*names):
    for name in names:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

_make_stub(
    "middleware", "models", "courses", "db", "rag", "llm",
    "services", "services.query", "services.query.retrieval",
    "services.query.persistence",
    "s3_utils",
)

# Provide the attributes that chat.py references at import time.
mw = sys.modules["middleware"]
for attr in ("send_json", "send_sse_headers", "send_sse_event",
             "handle_options", "authenticate_request",
             "sanitize_string", "check_rate_limit"):
    setattr(mw, attr, None)

models_mod = sys.modules["models"]
models_mod.User = object

courses_mod = sys.modules["courses"]
courses_mod.Course = object

db_mod = sys.modules["db"]
db_mod.get_db = None

rag_mod = sys.modules["rag"]
rag_mod.retrieve_chunks = None

llm_mod = sys.modules["llm"]
for attr in ("synthesize", "synthesize_with_clarification", "suggest_chat_title"):
    setattr(llm_mod, attr, None)

retrieval_mod = sys.modules["services.query.retrieval"]
retrieval_mod._fetch_chunk_context = None

persistence_mod = sys.modules["services.query.persistence"]
for attr in ("embed_text_via_lambda", "write_chat_message_embedding",
             "embed_image_via_lambda"):
    setattr(persistence_mod, attr, None)

s3_mod = sys.modules["s3_utils"]
for attr in ("generate_put_presigned_url", "generate_download_presigned_url",
             "get_file_extension", "verify_file_exists"):
    setattr(s3_mod, attr, None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_content_match_row_includes_message_fields():
    from chat import _content_match_from_row
    row = {
        "match_type": "content",
        "id": 12,
        "title": "Midterm review",
        "last_message_at": "2026-05-30T10:00:00Z",
        "hit_count": 3,
        "message_id": 88,
        "message_index": 4,
        "snippet": "the TCP <mark>handshake</mark> uses SYN",
    }
    out = _content_match_from_row(row)
    assert out["id"] == 12
    assert out["message_id"] == 88
    assert out["message_index"] == 4
    assert "<mark>handshake</mark>" in out["snippet"]
    assert out["hit_count"] == 3
    assert out["title"] == "Midterm review"
    assert out["last_message_at"] == "2026-05-30T10:00:00Z"
