# Releasing RELAI

Feature PRs do not bump versions. To release merged work:

1. Open **Actions → Release → Run workflow**, selecting **main**.
2. Leave version blank for the next patch, or enter a higher unused `X.Y.Z`.
3. Keep early access enabled for the pilot. Supply project-copy migration notes when needed.

The workflow bumps metadata, tests the selected revision, then pushes the tested commit and
`vX.Y.Z` tag atomically to `main` and publishes a GitHub release.
There is no release PR. [GitHub Releases](https://github.com/relai-ai/agent-eval-loop/releases)
contains generated change notes plus the supplied migration notes. For loading/installation
changes, verify a clean install and an upgrade in the affected hosts before releasing.

If preparation or tests fail, nothing is pushed. If `main` advances during testing, the push
fails without creating a tag; trigger a fresh run against current `main`.
If the push succeeds but GitHub release creation fails, finish that existing tag's release
with its source commit and migration notes, rather than bumping again. After checking the tag:

```sh
gh release create v0.1.1 --verify-tag --generate-notes --prerelease --notes-file migration-notes.md
```

Substitute the actual version and early-access choice. Correct published defects with a higher
version containing a fix or revert; never move published tags. See the [README](README.md#updating)
for user updates and the [project-copy policy](skills/start/template/docs/upgrades.md) for migrations.
