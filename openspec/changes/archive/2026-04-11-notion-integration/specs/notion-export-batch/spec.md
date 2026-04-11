## ADDED Requirements

### Requirement: Export endpoint accepts a provider-agnostic batch envelope
`POST /api/notion?action=export` SHALL accept a Shape C envelope: a top-level `exports` array where each entry specifies a `generation_id`, `generation_type`, and a `targets` array of `{ provider, target_id }` objects. A single export is represented as `exports` of length 1. This unified structure is forward-compatible with multi-provider and multi-generation batch scenarios without requiring a separate batch endpoint.

Request shape:
```json
{
  "exports": [
    {
      "generation_id": 1,
      "generation_type": "flashcards",
      "targets": [
        { "provider": "notion", "target_id": "page-abc123" }
      ]
    }
  ]
}
```

#### Scenario: Single export (standard case)
- **WHEN** `exports` contains one entry with one target
- **THEN** the server processes it and returns a 207 Multi-Status response with a single result entry
- **AND** behaviour is identical to the previous single-export API contract

#### Scenario: Batch export of multiple generations
- **WHEN** `exports` contains multiple entries (e.g. three flashcard generations to the same page)
- **THEN** each generation is exported independently in sequence
- **AND** a per-entry result is returned for each

#### Scenario: Empty exports array
- **WHEN** `exports` is an empty array or omitted
- **THEN** the endpoint returns 400 Bad Request with `{ "error": "exports array is required and must not be empty" }`

### Requirement: Export response uses 207 Multi-Status with per-entry results
The endpoint SHALL always return HTTP 207 Multi-Status. The response body SHALL include a `total`, `succeeded`, and `failed` count, plus a `results` array with one entry per (generation, provider) pair.

Response shape:
```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    {
      "generation_id": 1,
      "generation_type": "flashcards",
      "provider": "notion",
      "status": "success",
      "exported_count": 15,
      "url": "https://notion.so/..."
    },
    {
      "generation_id": 2,
      "generation_type": "quiz",
      "provider": "notion",
      "status": "success",
      "exported_count": 8,
      "url": "https://notion.so/..."
    },
    {
      "generation_id": 3,
      "generation_type": "flashcards",
      "provider": "notion",
      "status": "error",
      "error": "Generation not ready"
    }
  ]
}
```

#### Scenario: All exports succeed
- **WHEN** all entries in `exports` complete without error
- **THEN** response has `succeeded = total`, `failed = 0`
- **AND** all result entries have `status: 'success'`

#### Scenario: Partial failure
- **WHEN** some entries succeed and others fail
- **THEN** the endpoint still returns 207 (not 4xx/5xx)
- **AND** `failed` reflects the count of errored entries
- **AND** successful entries are not rolled back due to failures in other entries

#### Scenario: All exports fail
- **WHEN** every entry in `exports` errors
- **THEN** response still returns 207 with `succeeded: 0`, `failed: total`
- **AND** each result entry has `status: 'error'` with a descriptive `error` string

### Requirement: Multi-provider targets are a forward-compatibility hook (not yet implemented)
The `targets` array in each export entry is designed to support multiple providers simultaneously in the future (e.g. `[{ provider: 'notion', ... }, { provider: 'gdocs', ... }]`). In the current implementation, only `provider: 'notion'` is supported. If any target specifies an unknown provider, the result entry for that target SHALL have `status: 'error'` and `error: 'Unsupported provider'`. This allows the architecture to expand without changing the API contract.

#### Scenario: Unknown provider in targets
- **WHEN** a target entry specifies `provider: 'gdocs'` (or any provider other than 'notion')
- **THEN** that target's result entry has `status: 'error'` and `error: 'Unsupported provider: gdocs'`
- **AND** other valid targets in the same batch are unaffected
