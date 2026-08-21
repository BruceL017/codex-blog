# Gemini-Compatible Image Providers

This is a protocol compatibility note, not a fixed model catalog. Models and
availability change; use the model configured by the operator or discover it
from the configured provider's own API when that operation is supported.

## Configuration expectations

- provider type: `gemini-compatible`;
- `base_url`: may be the official service or a user-configured compatible
  endpoint;
- model: explicit configured identifier;
- secret: environment-variable name only;
- optional request defaults: aspect ratio, output format, safety controls, and
  timeout.

Do not assume the endpoint owner from protocol compatibility. Do not silently
replace a configured model with a remembered model name. Report an unsupported
model response and try the next configured provider.

## Response handling

Accept only image bytes or documented image-data fields. Decode into the
article's `images/` directory, validate file type and size, and discard unrelated
text as untrusted provider data. Do not treat a text-only response as a generated
image.

Record provider type, base-URL host (not query strings or credentials), model,
dimensions, and prompt hash in the manifest. Never record the API key or raw
authorization headers.
