# Supported provider contract

The implemented configuration uses OpenAI Responses over HTTPS at
`https://api.openai.com/v1/responses`, model `gpt-4.1-2025-04-14`, temperature 0,
max_output_tokens 2500, timeout 30 seconds, store false and strict JSON Schema
in text.format. MODEL_ID, MODEL_TEMPERATURE, MAX_OUTPUT_TOKENS and MODEL_TIMEOUT
override their respective settings. MODEL_ENDPOINT must match the approved
HTTPS URL exactly. The transport disables redirects and environment proxies.
Only production configuration reads API_KEY, which is used in the authorization
header. Tests use a dummy key and an intercepted transport.

The adapter sends a fixed extraction prompt and a minimized projection. It
replaces dates, request IDs and words outside the access-request vocabulary with
placeholders scoped to one message. The adapter validates the returned
placeholders and restores exact evidence spans locally. The dedicated review
store holds the source and the restored facts. The hosted service still
receives access-related terms and structure, so approve that scope and the
provider retention settings before authorizing real input.

Contract references inspected during implementation:
[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Fixtures cover completed, refused and incomplete responses and HTTP failures.
This is offline contract verification; no live provider observation was made.
The lockfile has no external dependencies; HTTP and validation use the standard library.
