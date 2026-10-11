# Example 15 — Sequencer PII Masking Middleware

Demonstrates **Issue #58** end-to-end: sanitizing sensitive PII via sequencer step operations and boundary middleware.

## What this shows

1. **Step Op Sanitization:** An explicit pipeline step (`ref: middleware.pii_mask`) sanitizes output from upstream steps (`source_step: ingest_customer_data`).
2. **Pseudonymization Strategy:** Sensitive values (emails, credit cards, international phones) are transformed into deterministic session-scoped tokens (e.g. `<EMAIL_REF_...>`, `<PHONE_REF_...>`), preserving entity equivalence across agent reasoning.
3. **Audit Spine Hygiene:** Zero raw sensitive data is written to the audit spine.
4. **Audit Report Telemetry:** The session audit report records `scorecard.middleware = {applied: 1, pii_redactions: 3}` and surfaces the `PII_MASKED` finding.

## Run

```bash
python examples/15-sequencer-pii-mask/main.py
```
