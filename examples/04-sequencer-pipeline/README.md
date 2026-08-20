# Example 04 — Sequencer + Skillware host

Prescriptive pipeline: **research → draft → human confirm → notify**.

Uses `MockSkill` so the example runs without installing Skillware. Swap in real Skillware skills via `SkillwareHost.from_skillware()` when `pip install "aura-harness[skillware]"` is available.

```bash
python examples/04-sequencer-pipeline/main.py
```

See [skillware-integration.md](../docs/skillware-integration.md) and [sequencer.md](../docs/sequencer.md).
