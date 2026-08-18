# Operation plugins

Field services, middleware ops, and attachments — all register here and in [spec/capability.registry.json](../../spec/capability.registry.json).

## Twelve field services

| Service | Op id (planned) |
|---|---|
| Monitor | `monitor.loop` |
| Audit | `audit.log` (always on) |
| Track | `track.progress` |
| Limit | `limit.tokens`, `limit.rate` |
| Safeguard | `safeguard.guardrail`, `safeguard.injection_scan` |
| Wake | `wake.resume` |
| Break | `break.runaway` |
| Conserve | `conserve.tokens` |
| Recover | `recover.error` |
| Remember | `remember.memory` |
| Learn | `learn.capture` |
| Attach | `attach.extension` |

## Middleware ops (Sequencer)

`middleware.firewall` · `middleware.pii_mask` · `middleware.prompt_compress`

See [docs/field-services.md](../../docs/field-services.md) · [docs/sequencer.md](../../docs/sequencer.md)
