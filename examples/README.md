# Examples

Runnable demos for AURA Harness v0.1.

| Example | Shows |
|---|---|
| [01-minimal-loop](01-minimal-loop/) | Auto agent ID, emit events, JSONL export |
| [02-guarded-tools](02-guarded-tools/) | Rules, approval gates, token limit |
| [03-task-mode](03-task-mode/) | Task mode, goal completion |

```bash
pip install -e ..
cd examples/01-minimal-loop && python main.py
```

Set `AURA_HOME` to isolate storage during tests.
