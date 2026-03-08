# LLM Text Models Reference

A reference list of text/language models available via API for Claude, Gemini, and OpenAI.
Excludes image, video, audio, TTS, and embedding models.

---

## Anthropic — Claude API

> No extra tier needed. All models available with any paid API account.

| Model | API ID | Status |
|---|---|---|
| Claude Opus 4.6 | `claude-opus-4-6` | Latest |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | Latest |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | Latest |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | Previous |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | Previous |
| Claude Opus 4 | `claude-opus-4-20250514` | Previous |

### Usage

```bash
# Anthropic API base URL
https://api.anthropic.com/v1/messages

# Required headers
x-api-key: YOUR_API_KEY
anthropic-version: 2023-06-01
Content-Type: application/json
```

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 1024,
  "messages": [{ "role": "user", "content": "Hello" }]
}
```

---

## Google — Gemini API

> Free tier available with rate limits. Blaze (paid) plan required for higher limits and some preview models.

| Model | API ID | Status |
|---|---|---|
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | Preview |
| Gemini 3 Flash | `gemini-3-flash-preview` | Preview |
| Gemini 2.5 Pro | `gemini-2.5-pro` | Stable |
| Gemini 2.5 Flash | `gemini-2.5-flash` | Stable |
| Gemini 2.5 Flash-Lite | `gemini-2.5-flash-lite` | Stable |
| Gemini Deep Research | `deep-research-pro-preview-12-2025` | Preview |
| Gemini 2.0 Flash | `gemini-2.0-flash` | Deprecated |
| Gemini 2.0 Flash-Lite | `gemini-2.0-flash-lite` | Deprecated |

### Usage

```bash
# Gemini API base URL
https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

# Required query parameter
?key=YOUR_API_KEY
```

```json
{
  "contents": [{ "role": "user", "parts": [{ "text": "Hello" }] }]
}
```

---

## OpenAI API

> All models available at Tier 1+. Rate limits scale with cumulative spend (Tier 1–5).

| Model | API ID | Notes |
|---|---|---|
| GPT-5.2 | `gpt-5.2` | Current flagship |
| GPT-5.1 | `gpt-5.1` | Previous flagship |
| GPT-5 Mini | `gpt-5-mini` | Faster/cheaper GPT-5 |
| GPT-5 Nano | `gpt-5-nano` | Most cost-efficient |
| GPT-4.1 | `gpt-4.1` | Best non-reasoning |
| GPT-4.1 mini | `gpt-4.1-mini` | Smaller, faster |
| GPT-4.1 nano | `gpt-4.1-nano` | Fastest, cheapest |
| GPT-4o | `gpt-4o` | Multimodal text |
| GPT-4o mini | `gpt-4o-mini` | Cost-efficient multimodal |
| o3 | `o3` | Reasoning |
| o3-mini | `o3-mini` | Compact reasoning |
| o3-pro | `o3-pro` | Extended reasoning compute |
| o4-mini | `o4-mini` | Fast reasoning |
| o1 | `o1` | Previous reasoning flagship |
| o1-pro | `o1-pro` | o1 + more compute |
| o3-deep-research | `o3-deep-research` | Research agent |
| o4-mini-deep-research | `o4-mini-deep-research` | Fast research agent |
| GPT-OSS 120B | `gpt-oss-120b` | Open-weight, Apache 2.0 |

### Usage

```bash
# OpenAI API base URL
https://api.openai.com/v1/chat/completions

# Required headers
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

```json
{
  "model": "gpt-4.1",
  "messages": [{ "role": "user", "content": "Hello" }]
}
```

---

## Tier Requirements Summary

| Provider | Extra Tier Needed? |
|---|---|
| Anthropic | No — all models on any paid API account |
| Google | Partial — free tier exists; Blaze plan for higher limits and some previews |
| OpenAI | Partial — all models from Tier 1+; rate limits scale with cumulative spend |

---

## Notes for Implementation

- **Anthropic:** Pin to versioned model IDs (e.g. `claude-sonnet-4-6`) in production to avoid unexpected changes from aliases.
- **Gemini:** Prefer `gemini-2.5-pro` or `gemini-2.5-flash` for stable production builds; avoid deprecated models.
- **OpenAI:** `o3-pro` and `o1-pro` are higher-cost but require no special subscription — billing only. Deep research models may have more restrictive rate limits.
- Models marked **Deprecated** (Gemini 2.0 series) should be migrated away from as soon as possible.