# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **systems@arpacorp.net** with:

- Description of the issue
- Steps to reproduce
- Impact assessment (if known)
- Affected version

We aim to acknowledge within 72 hours and provide a timeline for a fix when applicable.

## Scope

In scope:

- AURA Harness core (session, spine, registry, constraints, CLI)
- Example code shipped in this repository

Out of scope:

- Third-party models, tools, or adapters you attach to AURA
- User agent code running under the harness

## Audit logs

Session exports may contain sensitive data from your agent runs. Store `.aura/sessions/` and export files with appropriate access controls. AURA does not encrypt logs by default in v0.1.
