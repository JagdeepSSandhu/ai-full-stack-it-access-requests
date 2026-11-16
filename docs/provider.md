# Supported provider contract

The implemented configuration uses OpenAI Responses over HTTPS at
`https://api.openai.com/v1/responses`, model `gpt-4.1-2025-04-14`, temperature 0,
max_output_tokens 2500, timeout 30 seconds, store false and strict JSON Schema
in text.format. MODEL_ID, MODEL_ENDPOINT, MODEL_TEMPERATURE, MAX_OUTPUT_TOKENS
and MODEL_TIMEOUT override those settings; only production configuration reads
API_KEY. Tests inject Settings and an intercepted transport without reading it.

Contract references inspected during implementation:
[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Fixtures cover completed, refused and incomplete responses and HTTP failures.
This is offline contract verification; no live provider observation was made.
The lockfile has no external dependencies; HTTP and validation use the standard library.
