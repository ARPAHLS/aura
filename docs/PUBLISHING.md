# Publishing to PyPI

Releases are published automatically by [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) when:

- you **publish a GitHub Release**, or
- you push a **`v*` tag** (e.g. `v0.3.0`)

The workflow runs tests, builds sdist/wheel, then uploads to PyPI.

## One-time PyPI setup

1. Create the project on [pypi.org](https://pypi.org/) (or claim `aura-harness` if reserved).
2. **Trusted publishing (recommended):** PyPI → project → Publishing → Add GitHub Actions publisher  
   - Owner: `ARPAHLS`  
   - Repository: `aura`  
   - Workflow: `publish-pypi.yml`
3. **Or** create an API token and add `PYPI_API_TOKEN` as a GitHub repo secret; uncomment the `password` line in the workflow.

## Release checklist

1. Bump `version` in `pyproject.toml` and `aura/__init__.py`.
2. Update `CHANGELOG.md`.
3. Commit, push, tag: `git tag v0.3.0 && git push origin v0.3.0`
4. Create GitHub Release from the tag (or publish release — either triggers the workflow).
5. Confirm the [Publish to PyPI](https://github.com/ARPAHLS/aura/actions) workflow succeeded.

## README images on PyPI

Use **raw GitHub URLs** in `README.md` (not relative paths) so the PyPI project page renders logos:

`https://raw.githubusercontent.com/ARPAHLS/aura/main/docs/assets/aura_splash.png`
