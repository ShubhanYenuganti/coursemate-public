## 1. System Prompt Updates

- [x] 1.1 Update `_JSON_SYNTHESIS_INSTRUCTION` to instruct the model to emit `<REPLY>…</REPLY>` and `<META>{…}</META>` instead of a bare JSON object
- [x] 1.2 Update `_AGENTIC_JSON_FINAL_INSTRUCTION` with the same tag-delimited format instruction, including escaping rules (no JSON encoding in REPLY block)
- [x] 1.3 Remove backslash-doubling instruction from both prompts (no longer needed for reply body)

## 2. Parser Rewrite

- [x] 2.1 Implement tagged-format extraction: regex for `<REPLY>(.*?)</REPLY>` and `<META>(.*?)</META>` with `re.DOTALL`
- [x] 2.2 Implement brace-boundary fallback: `rfind('}')` + backward brace walk to isolate trailing JSON object; validate with `summary`/`follow_ups` key check
- [x] 2.3 Implement whole-text fallback: return full output as reply with empty metadata when both prior stages fail
- [x] 2.4 Wire all three stages into `_parse_synthesis_json` in order: tagged → brace-boundary → whole-text
- [x] 2.5 Remove `_repair_json_string_escapes` and `_extract_synthesis_obj` functions
- [x] 2.6 Remove `_VALID_JSON_ESCAPES` constant and the `\f`/`\t`/`\b` repair logic added in the previous session's hotfix

## 3. Streaming Path

- [x] 3.1 Identify where the streaming response is assembled in `api/chat.py` or `api/llm.py`
- [x] 3.2 Buffer tokens from `</REPLY>` onward; stream REPLY block tokens to client immediately
- [x] 3.3 After stream completes, parse buffered `<META>` block and attach metadata fields to the final response payload

## 4. Code Fence Strip Removal

- [x] 4.1 Remove the ` ```json ` / ` ``` ` fence-stripping regex from `_parse_synthesis_json` (no longer needed; tags are unambiguous delimiters)

## 5. Verification

- [x] 5.1 Test with a math-heavy prompt (e.g., HTTP download time analysis) and confirm `\frac`, `\times`, `\text` render correctly in the chat UI
- [x] 5.2 Test fallback: temporarily suppress tags in the prompt and confirm brace-boundary stage recovers the reply and metadata
- [x] 5.3 Test whole-text fallback: use a plain markdown response with no tags and no trailing JSON; confirm reply is shown without errors
- [x] 5.4 Test that `follow_ups`, `clarifying_question`, and `summary` are still persisted correctly after the parser change
- [x] 5.5 Confirm no `_repair_json_string_escapes` references remain in the codebase
