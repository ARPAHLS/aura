# Exporters

Normalize AuraEvent stream to downstream formats. See [docs/outputs.md](../../docs/outputs.md).

| Exporter (planned) | Format |
|---|---|
| `json` | AuraEvent stream + session summary |
| `otel` | OpenTelemetry GenAI semantic conventions + ARPA extensions |
| `csv` | Tabular session summary |
| `webhook` | HTTP POST on session end / violation |
| `legacy` | Legacy Protocol signed stream (Path A) |

Export profiles set in manifest `spectrum.output`.
