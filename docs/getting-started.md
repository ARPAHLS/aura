# Getting started

## Install

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
pip install -e ".[dev]"
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
purpose: Research tire companies and draft outreach emails
default_mode: task
rules:
  - type: max_tokens_per_step
    limit: 10000
  - type: confirm_before
    tools: [gmail.send]
variables:
  skills: skillware
  brain: cursor-agent
ids:
  external:
    company: TEAM-42
```

## Examples

See [examples/](../examples/README.md) for three runnable demos.

## Next

- [concepts.md](concepts.md) — agent, session, event, rule
- [comparison.md](comparison.md) — vs orchestrators and eval harnesses
- [ROADMAP.md](ROADMAP.md) — what comes after v0.1
- [architecture.md](architecture.md) — attach → audit trail → export
