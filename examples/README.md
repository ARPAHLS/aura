# Examples

Runnable demos for AURA Harness. Every example is a numbered folder with `main.py` and `README.md`.

From repo root after `pip install -e .`:

```bash
python examples/01-minimal-loop/main.py
python examples/12-escalation-playbooks/main.py
```

Set `AURA_HOME` to isolate storage during tests or demos.

## Learning path (01 → 12)

Run in order — [onboarding.md](../docs/onboarding.md#examples-learning-path):

| # | Folder | Teaches |
|---|---|---|
| **01** | [01-minimal-loop](01-minimal-loop/) | Audit posture — emit + export |
| **02** | [02-guarded-tools](02-guarded-tools/) | Rules, approval gates, allow/deny |
| **03** | [03-task-mode](03-task-mode/) | Task mode + `complete_goal()` |
| **04** | [04-sequencer-pipeline](04-sequencer-pipeline/) | Prescriptive pipeline + mock host |
| **05** | [05-skillware-skill-types](05-skillware-skill-types/) | ToolHost + three skill categories |
| **06** | [06-skillware-sequencer-chain](06-skillware-sequencer-chain/) | Declarative chain + conditional `when` |
| **07** | [07-observer-presets](07-observer-presets/) | Monitor + Break + Limit; `spectrum.services[]` |
| **08** | [08-emit-only-loop](08-emit-only-loop/) | Loose coat — no tool host |
| **09** | [09-audit-pipeline](09-audit-pipeline/) | Export slice — report, compare, OTel, verify |
| **10** | [10-observer-metrics-snapshot](10-observer-metrics-snapshot/) | Tailored coat — observer metrics snapshot |
| **11** | [11-scheduled-agent-slo](11-scheduled-agent-slo/) | Goal drift + schedule SLO |
| **12** | [12-escalation-playbooks](12-escalation-playbooks/) | Escalation playbooks — triggers + actions ([#47](https://github.com/ARPAHLS/aura/issues/47)) |

## Supplementary

| # | Folder | Teaches |
|---|---|---|
| **13** | [13-operator-identity](13-operator-identity/) | Verified operator trailer (mock adapter) |

Live registry skills (examples **05–06**): `$env:SKILLWARE_LIVE="1"` (PowerShell).

→ Capstone checklist: [docs/guides/reference-tool-host-capstone.md](../docs/guides/reference-tool-host-capstone.md)

Stack-specific bodies (Ollama, OpenAI, Anthropic) live under [`integrations/`](../integrations/README.md).
