# sitr — Specification (v0.1)

sitr is a privacy boundary between employee messages and AI models. Personal data is
removed before any model sees the text and restored only for the human who reads the
reply. A small reference assistant for an employee-services desk exists to show the
boundary doing real work; the boundary is the product.

## 1. Scope

**In scope (v0.1)**

- Detection categories: Emirates ID numbers, UAE mobile numbers, email addresses,
  personal names (Latin script, English text).
- Treatment: names, emails and phones become reversible placeholders restored in the
  reply. Emirates IDs are masked irreversibly, never restored, never leave the boundary.
- Destination policy as configuration (`policy.yaml`). Anything undeclared is refused.
- Outgoing re-check before any text leaves; refusal on any hit.
- One audit record per request; never contains message text or the placeholder mapping.
- Reference assistant: classifies a request as `salary_certificate`, `noc_letter`,
  `leave` or `it_access`, lists missing items, drafts a reply for a person to review.
- Two modes: `offline` (rule-based, default, no network) and `ai` (OpenRouter, optional).
- Interfaces: a CLI and a minimal local web UI over the same `process()` function.

**Out of scope (stated, not silent)**

- Hosted multi-user deployment (access codes, rate limits, spend caps).
- Arabic-script names, Arabic-Indic digits, any other PII category (passport numbers,
  IBANs, postal addresses, dates of birth).
- Recorded/replay mode, secrets-manager-backed placeholder store, measured detection
  quality set, chat front end, per-business-unit policy packs.
- Sending anything on anyone's behalf. sitr drafts only.

## 2. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Detect Emirates IDs, UAE mobiles, emails and personal names in English text. |
| FR-2 | Replace names/emails/phones with numbered placeholders (`[NAME_1]`, `[EMAIL_1]`, `[PHONE_1]`); keep the mapping in memory for the current request only. |
| FR-3 | Replace Emirates IDs with `[EID_MASKED]`; never store the original. |
| FR-4 | Load destinations from `policy.yaml` (name, provider, region, approved, model). Refuse any destination that is undeclared or `approved: false`. |
| FR-5 | Re-run all detectors on the outgoing text; refuse the request if anything is found. |
| FR-6 | Classify the request into one of four types, list missing items per type, and draft a reply. In `ai` mode the model does this on the masked text only. |
| FR-7 | Validate model output: JSON with `request_type` in the closed set, `missing_items`, `draft_reply`. Anything else is handed to a person. |
| FR-8 | Restore only placeholders present in this request's mapping. Unknown placeholders stay literal and the result is flagged `needs_review`. |
| FR-9 | Re-check the restored reply for Emirates IDs before display. |
| FR-10 | Emit one audit record per request: id, timestamp, mode, destination (provider/region/approved), category counts, request type, decision, refusal reason, needs-review flag (an unknown placeholder was left literal in the reply). |
| FR-11 | Every result shows which destination handled it, in which region, and whether it is approved. |
| FR-12 | Offer example requests as templates; always allow free text. |
| FR-13 | The `ai` mode is offered only when the machine can run it (key present); otherwise it is shown disabled with the reason. |

## 3. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Runs from a clean checkout with `uv sync` and one run command. No accounts, keys, paid services or separate model downloads. The name model ships as a pinned dependency. |
| NFR-2 | No secrets committed. The only secret (`OPENROUTER_API_KEY`) is read from the environment on the server side and never appears in responses, logs, errors or the UI. |
| NFR-3 | Privacy invariants are tested: no personal data in logs or audit records, outgoing re-check refuses on a hit, Emirates IDs are never restored. |
| NFR-4 | Honest refusal: empty, oversized (> 4,000 chars), non-English, unrecognisable or suspicious input is handed to a person with a stated reason. sitr never crashes and never guesses. |
| NFR-5 | Web UI binds to `127.0.0.1` by default. Same-origin only. The placeholder mapping never leaves the server process. |
| NFR-6 | Handover: another engineer can run, test and maintain it from the README alone. Tests and CI are part of the product. |
| NFR-7 | Offline request completes in under one second on a laptop after the name model is loaded once (at `serve` startup; on first use for `run`). |
| NFR-8 | Nothing in the code, UI or docs claims regulatory compliance. |
| NFR-9 | All sample data is synthetic. |

## 4. Refusal conditions

Each is handed to a person with the reason stated and recorded in the audit record.

`empty` · `too_long` · `non_english` · `suspected_manipulation` · `unrecognised_request` ·
`destination_not_approved` · `outgoing_recheck_failed` · `model_unavailable` ·
`model_output_invalid`

## 5. Acceptance tests (non-negotiable)

| ID | Test |
|----|------|
| T-1 | Offline end-to-end: synthetic request with all four PII categories → classified, drafted, names restored, EID masked. |
| T-2 | No PII in logs: capture all logging output for T-1 and assert none of the synthetic values appear. Same assertion on the audit record. |
| T-3 | Outgoing re-check: inject a *masking* fault (monkeypatch `Masker.apply` to leave phone spans in place) so a phone survives masking → request refused with `outgoing_recheck_failed`, nothing sent. The re-check shares `detect()` with masking, so it guards against masking faults, not detector blind spots (see §7). |
| T-4 | One test per refusal condition in §4. |
| T-5 | Mask → restore round-trip is lossless for names, emails, phones. |
| T-6 | Emirates ID is absent from masked text, restored reply, mapping and audit record. |
| T-7 | Policy: undeclared destination refused; `approved: false` refused; approved passes. |
| T-8 | AI mode against an in-process fake server: request body contains placeholders and no synthetic PII; invalid JSON or unknown `request_type` → handed to a person. |

## 6. Cut order if time runs out

1. Manipulation heuristic
2. Name detection
3. Missing-items check

Never cut: offline flow, T-2, T-3, honest refusal, README.

## 7. Known limitations

- Name detection uses a small statistical model (`en_core_web_sm`). It misses lowercase
  or uncommon names and can flag non-names; recall is uneven on compound names. When one
  name in a message is missed and another caught, the draft greets the wrong person.
  Precision is stated, not measured.
- Phone detection covers UAE mobile spellings (`+971 5x`, `00971 5x`, `971 5x`, `+971 (0)5x`,
  `05x`); landlines and foreign numbers are not detected.
- Emirates ID detection is format-based (`784-YYYY-NNNNNNN-N`, separators optional); no
  checksum validation.
- Manipulation detection is a keyword heuristic, not a classifier.
- English text only; the language check is a script heuristic, not language identification.
- The outgoing re-check reuses the same detectors as masking. It catches masking faults
  (a replacement bug, a skipped span, a name spaCy only recognises on a second pass), not
  a format the detectors do not know. Unknown formats are the limitations above; the
  re-check cannot compensate for them.
