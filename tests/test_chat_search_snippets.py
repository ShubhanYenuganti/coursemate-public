import sys, os, types
import pytest

# chat.py pulls in middleware/db/rag/llm/etc. at import time. We stub those so we can
# reach _content_match_from_row without a live DB / Vercel environment.
#
# IMPORTANT: the stubbing is done inside a module-scoped fixture (not at module top)
# and fully restores sys.modules afterward. Doing it at import time left an empty `llm`
# module in sys.modules that shadowed the real api/llm.py and broke collection of
# test_pageindex_agent.py (`from llm import _format_routing_index_block`).

_STUB_NAMES = [
    "middleware", "models", "courses", "db", "rag", "llm",
    "services", "services.query", "services.query.retrieval",
    "services.query.persistence", "s3_utils", "chat",
]


@pytest.fixture(scope="module", autouse=True)
def _stub_chat_deps():
    saved = {name: sys.modules.get(name) for name in _STUB_NAMES}

    def _stub(name):
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    mw = _stub("middleware")
    for attr in ("send_json", "send_sse_headers", "send_sse_event",
                 "handle_options", "authenticate_request",
                 "sanitize_string", "check_rate_limit"):
        setattr(mw, attr, None)

    _stub("models").User = object
    _stub("courses").Course = object
    _stub("db").get_db = None
    _stub("rag").retrieve_chunks = None

    llm_mod = _stub("llm")
    for attr in ("synthesize", "synthesize_with_clarification", "suggest_chat_title"):
        setattr(llm_mod, attr, None)

    _stub("services")
    _stub("services.query")
    _stub("services.query.retrieval")._fetch_chunk_context = None

    persistence_mod = _stub("services.query.persistence")
    for attr in ("embed_text_via_lambda", "write_chat_message_embedding",
                 "embed_image_via_lambda"):
        setattr(persistence_mod, attr, None)

    s3_mod = _stub("s3_utils")
    for attr in ("generate_put_presigned_url", "generate_download_presigned_url",
                 "get_file_extension", "verify_file_exists"):
        setattr(s3_mod, attr, None)

    sys.modules.pop("chat", None)  # force a fresh import against the stubs
    api_path = os.path.join(os.path.dirname(__file__), '..', 'api')
    sys.path.insert(0, api_path)
    try:
        yield
    finally:
        if api_path in sys.path:
            sys.path.remove(api_path)
        for name, orig in saved.items():
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig
        sys.modules.pop("chat", None)


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
