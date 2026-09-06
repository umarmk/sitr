# ADR 0004 — Model behind a Protocol; OpenRouter via stdlib urllib

**Status:** accepted · 2026-09-06

**Context.** A real model must be optional, sit behind a simple interface, and read its
credentials from the environment. Offline mode is the default and the full product.

**Decision.** A `Model` Protocol with one method. `RuleBasedModel` implements offline
mode. `OpenRouterModel` posts to `https://openrouter.ai/api/v1/chat/completions` with
stdlib `urllib`, reads `OPENROUTER_API_KEY` from the environment, requests JSON mode
(`response_format: json_object`), and uses the configured timeout. Unreachable or erroring
gateway → `model_unavailable`; an answer that is not a JSON object → `model_output_invalid`.
Error strings are static so they can appear in results and audit records. Model name,
temperature, timeout and system prompt come from configuration, never code. Tested against
an in-process fake HTTP server; CI never calls a live service.

**Consequences.** Zero client dependencies. OpenRouter is an OpenAI-compatible gateway,
so the same code reaches many providers by changing `policy.yaml`. Rejected: the
`openai` SDK (a dependency tree for one POST).
