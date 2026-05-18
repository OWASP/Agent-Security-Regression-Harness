# Releasing

This document is for project maintainers. It covers how to cut a release
of the OWASP Agent Security Regression Harness to PyPI.

## One-time setup (PyPI trusted publishing)

Before the first release, configure PyPI to trust this GitHub repository
so the release workflow can publish without a long-lived token.

1. Reserve the project name on PyPI by creating the project under
   `https://pypi.org/project/owasp-agent-security-regression-harness/`
   (or wait until the first publish creates it).
2. On PyPI, go to **Your projects → owasp-agent-security-regression-harness
   → Publishing → Add a new pending publisher**.
3. Fill in:
   - **PyPI Project Name**: `owasp-agent-security-regression-harness`
   - **Owner**: `OWASP`
   - **Repository name**: `Agent-Security-Regression-Harness`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
4. On GitHub, go to **Settings → Environments** and create an
   environment named `pypi`. Add a required reviewer (the maintainer
   who approves releases) so a release cannot publish without explicit
   approval.

After this is configured, the workflow at `.github/workflows/release.yml`
can publish to PyPI via OIDC. No tokens live in the repo.

## Per-release checklist

For every release tag (e.g. `v0.1.0`):

1. **Update the CHANGELOG.** Move entries from `[Unreleased]` into a
   versioned section like `[0.1.0]` with today's date. Leave an empty
   `[Unreleased]` block for the next cycle.
2. **Bump the version**. Update the version string in:
   - `pyproject.toml`
   - `src/agent_harness/__init__.py` (`__version__`)
   - `src/agent_harness/cli.py` (`VERSION`)
   - `README.md` (the expected `agent-harness version` output)
3. **Open a release-prep PR** with those two changes. Title it
   `release: prepare v0.X.Y`. Merge it once CI passes.
4. **Tag** the merge commit on `main`:

   ```bash
   git checkout main
   git pull
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

5. **Watch the workflow.** The release workflow runs four jobs:
   - `verify` — pytest, ruff, mypy on the tagged commit
   - `build` — `python -m build` produces sdist + wheel artifacts
   - `publish-pypi` — uploads to PyPI via trusted publishing (waits
     for environment approval if you required one)
   - `github-release` — attaches sdist + wheel to the GitHub release
     page with auto-generated release notes

6. **Verify the published artifact**:

   ```bash
   pip install --upgrade --no-cache-dir owasp-agent-security-regression-harness
   agent-harness version
   ```

## What if a release fails?

**Publish step failed before PyPI accepted the upload.** Fix the issue,
delete the tag locally and remotely, re-tag, and re-push:

```bash
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0
# fix the issue, commit, push
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

**Publish step succeeded but the artifact is broken.** PyPI does **not**
allow re-uploading the same version. Bump to the next patch version
(e.g. `v0.1.1`), update CHANGELOG, retag, and let the workflow run.

**GitHub release step failed but PyPI succeeded.** Re-run the
`github-release` job from the Actions tab. The artifacts are already
on PyPI; this step only attaches them to the GitHub release page.

## Tag format

Only tags matching `v<major>.<minor>.<patch>` and
`v<major>.<minor>.<patch>rc<N>` trigger the release workflow. Other
tags are ignored.
