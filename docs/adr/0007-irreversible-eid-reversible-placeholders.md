# ADR 0007 — Emirates IDs masked irreversibly; other categories reversible

**Status:** accepted · 2026-09-06

**Context.** The reader of a reply needs real names to act on it. Nobody downstream needs
an Emirates ID number, and it is the highest-risk identifier in scope.

**Decision.** Names, emails and phones become numbered placeholders (`[NAME_1]`,
`[EMAIL_1]`, `[PHONE_1]`) with a mapping held in memory for the current request only and
restored in the reply. Emirates IDs become `[EID_MASKED]`; the original is never stored,
never mapped, never restored. Restoration touches only placeholders present in the
request's own mapping; anything else stays literal and flags `needs_review`. The restored
reply is re-checked for EIDs before display.

**Consequences.** A model that invents or echoes a placeholder cannot cause a leak. The
mapping's lifetime is the request; a secrets-manager-backed store with retention rules is
the documented upgrade path.
