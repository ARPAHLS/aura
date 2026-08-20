# Getting started

## Install

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
pip install -e ".[dev]"
```

Optional Skillware integration:

```bash
pip install -e ".[dev,skillware]"
```

Requires Python 3.10+.

## Five-minute example

```python
from aura import agent, configure

configure()

ag = agent("my-bot")
with ag.session() as run:
    run.emit("turn.start", {"input": "hello"})
    run.emit("turn.end", {"output": "world", "tokens": 50})

print(run.exports)  # JSONL + summary paths
```

## Sequencer example (v0.2)

```python
from aura import agent, configure
from aura.hosts import MockSkill, SkillwareHost

configure()

spec = {
    "steps": [
        {"id": "research", "type": "skill", "ref": "research",
         "config": {"tool": "search", "args": {"query": "AURA"}}},
        {"id": "summarize", "type": "op", "ref": "compose"},
    ]
}

ag = agent("pipeline", sequencer=spec)
with ag.session() as run:
    host = SkillwareHost(run._session)
    host.register(MockSkill("research", {"search": lambda a: {"hits": 1}}))
    run.run_sequencer(host=host)

print(run.exports)
```

Logs land in `~/.aura/sessions/` unless you configure project storage.

## CLI

```bash
aura agent create my-bot --purpose "research assistant"
aura agent list
aura run my-bot path/to/script.py
aura logs aura_sess_xxxxxxxxxxxx
aura export aura_sess_xxxxxxxxxxxx
```

## Agent profile (optional YAML)

Save as `agents/my-bot.yaml` and load in your app, or use `agent("my-bot", rules=[...])`:

```yaml
name: my-bot
purpose: Research and draft outreach emails
default_mode: task
skills: [research, gmail]
sequencer:
  steps:
    - id: research
      type: skill
      ref: research
      config: { tool: search, args: { query: "..." } }
rules:
  - type: max_tokens_per_step
    limit: 10000
  - type: confirm_before
    tools: [send]
observers:
  - id: metrics
variables:
  brain: cursor-agent
ids:
  external:
    company: TEAM-42
```

## Examples

See [examples/](../examples/README.md) — including [04-sequencer-pipeline](../examples/04-sequencer-pipeline/).

## Next

- [using-aura.md](using-aura.md) — membrane, personas, observers
- [skillware-integration.md](skillware-integration.md) — Skillware host
- [concepts.md](concepts.md) — agent, session, sequencer
- [comparison.md](comparison.md) — vs orchestrators and eval harnesses
- [ROADMAP.md](ROADMAP.md) — what comes after v0.2
- [architecture.md](architecture.md) — modules and data flow
