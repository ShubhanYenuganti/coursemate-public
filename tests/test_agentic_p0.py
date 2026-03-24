import os
import sys
import types
import unittest
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_DIR = os.path.join(ROOT, "api")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

# Avoid importing compiled cryptography during unit tests.
fake_crypto_utils = types.ModuleType("crypto_utils")
fake_crypto_utils.decrypt_api_key = lambda value: value
sys.modules.setdefault("crypto_utils", fake_crypto_utils)

import llm  # noqa: E402
import tools  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _query, _params):
        return None

    def fetchall(self):
        return self._rows

    def close(self):
        return None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


class AgenticP0Tests(unittest.TestCase):
    def test_execute_search_materials_returns_normalized_payload(self):
        mocked_chunks = [
            {
                "id": "a-uuid",
                "chunk_text": "First chunk",
                "chunk_type": "text",
                "page_number": 1,
                "similarity": 0.9,
                "material_id": 2,
            },
            {
                "id": "b-uuid",
                "chunk_text": "Second chunk",
                "chunk_type": "visual",
                "page_number": 2,
                "similarity": 0.8,
                "material_id": 2,
            },
        ]
        with patch("tools.retrieve_chunks", return_value=mocked_chunks):
            result = tools.execute_search_materials(
                conn=object(), query="what is recursion", material_ids=[2], top_k=8
            )
        self.assertEqual(result["chunk_ids"], ["a-uuid", "b-uuid"])
        self.assertIn("Search results for query", result["text"])
        self.assertEqual(result["meta"]["result_count"], 2)

    def test_pull_grounding_context_hydrates_and_dedupes_chunk_ids(self):
        rows = [
            {
                "id": 1,
                "role": "assistant",
                "content": "prior answer",
                "retrieved_chunk_ids": ["x-1", "x-2", "x-1"],
                "message_index": 4,
                "dist": 0.01,
            }
        ]
        fake_conn = _FakeConn(rows)
        hydrated = [
            {"id": "x-1", "chunk_text": "Chunk 1", "chunk_type": "text", "material_id": 1, "page_number": 1},
            {"id": "x-2", "chunk_text": "Chunk 2", "chunk_type": "text", "material_id": 1, "page_number": 2},
        ]
        with patch("tools.embed_text_via_lambda", return_value=[0.1, 0.2]), patch(
            "tools._fetch_chunk_context", return_value=hydrated
        ):
            result = tools.pull_grounding_context(fake_conn, chat_id=7, query_text="follow up")
        self.assertEqual(result["chunk_ids"], ["x-1", "x-2"])
        self.assertIn("Prior grounded chunks", result["text"])
        self.assertEqual(len(result["chunks"]), 2)

    def test_run_agent_openai_tool_call_then_final_answer(self):
        first_payload = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search_materials",
                                    "arguments": "{\"query\": \"recursion\", \"top_k\": 4}",
                                },
                            }
                        ],
                    },
                }
            ]
        }
        second_payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Final grounded answer"},
                }
            ]
        }
        with patch("llm.requests.post", side_effect=[_FakeResponse(first_payload), _FakeResponse(second_payload)]), patch(
            "llm.execute_search_materials",
            return_value={"text": "tool evidence", "chunk_ids": ["tool-1"], "meta": {"latency_ms": 12, "result_count": 1}},
        ), patch("llm.pull_grounding_context", return_value={"text": "", "chunk_ids": [], "messages": [], "chunks": []}):
            text, refs, trace = llm.run_agent_openai(
                conn=object(),
                user_message="Explain recursion",
                model="gpt-4o-mini",
                api_key="k",
                chunks=[{"id": "seed-1", "chunk_type": "text", "similarity": 0.9, "chunk_text": "seed"}],
                chat_id=9,
                context_material_ids=[1],
            )
        self.assertEqual(text, "Final grounded answer")
        self.assertEqual(refs, ["seed-1", "tool-1"])
        self.assertTrue(any(t.get("tool") == "search_materials" for t in trace))

    def test_run_agent_openai_respects_iteration_cap(self):
        payload = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search_materials", "arguments": "{\"query\": \"x\"}"},
                            }
                        ],
                    },
                }
            ]
        }
        with patch("llm.requests.post", side_effect=[_FakeResponse(payload)] * 3), patch(
            "llm.execute_search_materials",
            return_value={"text": "tool evidence", "chunk_ids": ["tool-1"], "meta": {"latency_ms": 10, "result_count": 1}},
        ), patch("llm.pull_grounding_context", return_value={"text": "", "chunk_ids": [], "messages": [], "chunks": []}), patch.dict(
            os.environ, {"AGENTIC_MAX_ITERATIONS": "3"}, clear=False
        ):
            text, refs, trace = llm.run_agent_openai(
                conn=object(),
                user_message="x",
                model="gpt-4o-mini",
                api_key="k",
                chunks=[],
                chat_id=None,
                context_material_ids=[1],
            )
        self.assertIn("ran out of tool-call iterations", text.lower())
        self.assertEqual(refs, ["tool-1"])
        self.assertGreaterEqual(len(trace), 3)


if __name__ == "__main__":
    unittest.main()
