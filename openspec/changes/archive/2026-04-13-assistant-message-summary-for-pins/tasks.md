## 1. Database

- [x] 1.1 Add migration SQL for `chat_messages.summary` (nullable TEXT)
- [x] 1.2 Add `summary` to `chat_messages` in `api/db.py` `init_db()` for new installs

## 2. LLM synthesis

- [x] 2.1 Add JSON synthesis instructions and `_parse_synthesis_json` helper with fallback
- [x] 2.2 Update `_synthesize_openai` to use `response_format` json_object and parse `reply`/`summary`
- [x] 2.3 Update `_synthesize_claude` and `_synthesize_gemini` to request JSON and parse
- [x] 2.4 Extend `synthesize()` return value to include `summary` (or tuple) for non-agentic path
- [x] 2.5 Update `run_agent_openai` final message parsing, verifier/repair on `reply`, emit text SSE from `reply`

## 3. Chat API

- [x] 3.1 Thread `summary` through all assistant `INSERT`/`RETURNING` paths in `api/chat.py`
- [x] 3.2 Add `summary` to message list SELECTs
- [x] 3.3 `_list_pins`: `ai_summary` = `COALESCE(am.summary, pm.ai_summary, '')`
- [x] 3.4 `_pin_message`: set `ai_summary` from `chat_messages.summary` for assistant id

## 4. Frontend

- [x] 4.1 Remove `derivePinSummary` and stop sending `ai_summary` on pin POST
- [x] 4.2 Use `assistantMsg.summary` for optimistic pin rows when present
