# Examples

Runnable demos for AURA Harness.

Runnable core AURA patterns. From the repo root:

```bash
pip install -e .
python examples/minimal_loop.py
python examples/guarded_tools.py
python examples/task_mode.py
python examples/sequencer_pipeline.py
```

Set `AURA_HOME` to isolate storage during tests or demos.

| Script | What it demonstrates | Why use it | Choose it when | Edge cases / failure modes | Customization knobs |
|---|---|---|---|---|---|
| [minimal_loop.py](minimal_loop.py) | Auto agent registration, session events, JSONL and summary export | Wrap a small loop with AURA audit output | You only need a script-mode session and export path | Misconfigured `AURA_HOME`; unwritable export directory | Agent name, emitted event names, `AURA_HOME` |
| [audit_pipeline.py](audit_pipeline.py) | Two sessions, audit report, compare, hash-chain verify, CLI follow-ups | Show the full export slice with MockSkill host | You need receipt + compare + verify without Skillware live | Missing write permissions under sessions dir | Agent ref, mock skill manifest, `AURA_HOME` |
| [guarded_tools.py](guarded_tools.py) | Rules, approval gates, allowlist, token limit | Show membrane behavior around guarded tool events | You need policy and approval examples without a sequencer | Approval denied or missing; rule violation; blocked disallowed tool | Rules, tool names, token limits, approval handling, mock vs live tool events |
| [task_mode.py](task_mode.py) | Task mode, profile purpose, goal completion | Model work that closes only after an explicit goal result | You need task lifecycle and conformance summary output | Goal never completed; missing purpose; invalid task state | Purpose, task steps, completion payload, `AURA_HOME` |
| [sequencer_pipeline.py](sequencer_pipeline.py) | Sequencer steps with mock Skillware-compatible skills and human confirm gate | Exercise an ordered pipeline with approval and host execution | You need prescribed step order rather than ad hoc events | Approval denied; missing skill; unknown step ref; rule violation | `PIPELINE` / sequencer YAML path, mock vs live host, skill names, gates, `AURA_HOME` |

| Integration demo | Shows |
|---|---|
| [05-skillware-skill-types](05-skillware-skill-types/) | Three Skillware categories (security, optimization, monitoring) |
| [06-skillware-sequencer-chain](06-skillware-sequencer-chain/) | Sequencer chain with conditional `when` steps |
| [07-observer-presets](07-observer-presets/) | Monitor + Break observer presets on ToolHost |
| [08-emit-only-loop](08-emit-only-loop/) | Loose coat — emit-only, no tool host |
| [09-operator-identity](09-operator-identity/) | Optional verified operator trailer (mock adapter) |
| [10-observer-metrics-snapshot](10-observer-metrics-snapshot/) | Tailored coat — AURA-native metrics snapshot via observers |

```bash
python examples/07-observer-presets/main.py
```

Live registry skills (examples 05–06): `$env:SKILLWARE_LIVE="1"` (PowerShell).

→ Capstone checklist: [docs/guides/reference-tool-host-capstone.md](../docs/guides/reference-tool-host-capstone.md)

**Learning order:** [onboarding.md](../docs/onboarding.md#examples-learning-path) — run examples 1→8 in sequence.

## Script excerpts

Each script uses a top module docstring, then section comments for setup, session, emit, and close / expected export. Core examples stay as flat scripts here; stack-specific demos belong under [`integrations/`](../integrations/README.md).
