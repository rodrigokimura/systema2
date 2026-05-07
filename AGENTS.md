# Agent Guidelines for systema2

This document codifies the preferred development workflow for anyone (human or agent) working on this repository.

## Branch-first development — always

**Never commit to `master` directly.** Every change, no matter how small,
must be developed on a feature branch and merged through a GitHub Pull Request.

### Branch naming

Use the same prefix as conventional commits (`feat/`, `fix/`, `chore/`,
`refactor/`, `test/`, `docs/`):

```
feat/add-drag-pan
cfix/handle-null-label
chore/bump-version-0.5.0
```

### Creating a branch

```bash
# Always branch from an up-to-date master
git fetch origin && git checkout origin/master
git checkout -b feat/<kebab-case-description>
```

### Workflow per feature

1. **Make changes** — code, tests, docs.
2. **Run tests** — full suite must pass before pushing:
   ```bash
   uv run pytest -q -m "not e2e"   # fast feedback (~75 s)
   uv run pytest -q -m e2e          # full e2e (~6 m)
   ```
3. **Commit** with a Conventional Commit message (enforced by the
   pre-commit hook in `.pre-commit-config.yaml`):
   ```bash
   git add -A
   git commit -m "feat(whiteboard): describe the change"
   ```
4. **Push** the branch:
   ```bash
   git push -u origin feat/name
   ```
5. **Open a PR** via `gh` CLI (include a clear title/description):
   ```bash
   gh pr create \
     --title "feat(whiteboard): short title" \
     --body "Longer description of the change." \
     --base master
   ```
6. **Merge** with squash and delete the branch:
   ```bash
   gh pr merge --squash --delete-branch
   ```

If the PR needs tweaks, push additional commits to the same branch
and let CI re-run. Only merge once all checks are green.

## What counts as a change

Use a branch + PR for **any** of the following:

- New features or sub-features
- Bug fixes
- Refactorings (even "safe" ones)
- Test additions or changes
- Dependency updates (`uv add`, `uv lock` refresh)
- Version bumps (before tagging)
- Documentation updates beyond trivial README typos
- Configuration changes (`.github/workflows`, `pyproject.toml`, etc.)

The only exception is an emergency hot-fix explicitly requested by the
repo owner with the instruction "push directly to master".

## Version tags and releases

Tagging is done **after** the version-bump PR is merged to `master`.

```bash
# On an up-to-date master
git pull origin master
git tag v0.X.Y
git push origin v0.X.Y
```

The `release.yml` GitHub Actions workflow is triggered by the tag push,
builds sdist + wheel, and publishes to PyPI via Trusted Publishing.

## Tooling conventions

- `uv` for all Python and dependency management.
- `gh` CLI for all GitHub operations (PR creation, merging, release notes).
- Conventional Commits for all commits (validated locally by the
  pre-commit hook).
- Squash-merge all PRs with `--delete-branch` to keep the branch list clean.
