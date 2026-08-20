# Publishing to PyPI

Releases are published automatically by [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) when:

- you **publish a GitHub Release**, or
- you push a **`v*` tag** (e.g. `v0.3.0`), or
- you **Run workflow** manually (Actions → Publish to PyPI → Run workflow)

The workflow runs tests, builds sdist/wheel, then uploads to PyPI.

## One-time PyPI setup

1. Create the project on [pypi.org](https://pypi.org/project/aura-harness/) (owner account must match GitHub org/user used below).
2. **Trusted publishing (recommended):** PyPI → **aura-harness** → **Publishing** → **Add a new pending publisher** → GitHub Actions  
   Enter **exactly**:

   | Field | Value |
   | :--- | :--- |
   | **PyPI Project Name** | `aura-harness` |
   | **Owner** | `ARPAHLS` |
   | **Repository name** | `aura` |
   | **Workflow name** | `publish-pypi.yml` |
   | **Environment name** | *(leave blank)* |

   Save. The publisher must exist **before** the workflow publish step runs.

3. **Or** create an API token scoped to `aura-harness` and add `PYPI_API_TOKEN` as a GitHub repo secret; uncomment the `password` line in the workflow.

### Trusted publishing troubleshooting

If publish fails with `invalid-publisher: valid token, but no corresponding publisher`, PyPI has no publisher row matching the GitHub OIDC claims. Typical fixes:

- Publisher was added **after** the failed run — configure PyPI, then **re-run** the workflow (no new release needed).
- **Owner** typo — must be `ARPAHLS`, not a personal PyPI username, unless the repo lives under a user account.
- **Workflow name** — filename only: `publish-pypi.yml` (not the full path).
- **Environment** — leave empty on PyPI unless you add a GitHub Environment and set the same name on both sides.
- **Project name** — publisher must be attached to **`aura-harness`**, the PyPI project being uploaded.

Claims from a successful v0.3.0 run (for verification):

```text
repository: ARPAHLS/aura
repository_owner: ARPAHLS
workflow_ref: ARPAHLS/aura/.github/workflows/publish-pypi.yml@refs/tags/v0.3.0
ref: refs/tags/v0.3.0
environment: MISSING
```

See [PyPI trusted publishing troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/).

## Re-run after fixing PyPI

You do **not** need a new GitHub Release if tests already passed:

1. Fix trusted publisher (or add `PYPI_API_TOKEN`) on PyPI / GitHub.
2. Actions → **Publish to PyPI** → open the failed run → **Re-run failed jobs**,  
   **or** Actions → **Publish to PyPI** → **Run workflow** (manual dispatch).

PyPI rejects uploading the **same version twice**. If `0.3.0` partially uploaded, delete the release on PyPI (if allowed) or bump to `0.3.1` before re-publishing.

## Release checklist

1. Bump `version` in `pyproject.toml` and `aura/__init__.py`.
2. Update `CHANGELOG.md` and `CITATION.cff` (`version`, `date-released`).
3. Commit, push, tag: `git tag v0.3.0 && git push origin v0.3.0`
4. Create GitHub Release from the tag (or publish release — either triggers the workflow).
5. Confirm the [Publish to PyPI](https://github.com/ARPAHLS/aura/actions/workflows/publish-pypi.yml) workflow succeeded.
6. Confirm [pypi.org/project/aura-harness](https://pypi.org/project/aura-harness/) shows the new version.

## Citation / Zenodo

Concept DOI (all versions): [10.5281/zenodo.22031863](https://doi.org/10.5281/zenodo.22031863)

Recorded in [CITATION.cff](../CITATION.cff) and `pyproject.toml` `[project.urls]`. Bump Zenodo on major releases if your archive policy requires it.

## README images on PyPI

- **GitHub (private or public):** use a **relative** path in `README.md`, e.g. `docs/assets/aura_splash.png`.
- **PyPI** (after the repo is **public**): pin a tag URL so the project page renders logos:

  `https://raw.githubusercontent.com/ARPAHLS/aura/v0.3.0/docs/assets/aura_splash.png`

  Switch back to relative on `main` for GitHub if you prefer one README for both — PyPI will not resolve relative asset paths.
