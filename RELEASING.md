# Releasing RELAI

Feature PRs do not bump versions. To release merged work:

1. Open **Actions → Release → Run workflow**, selecting **main**.
2. For the first release, enter the current manifest version (`0.1.0`). After that, leave
   version blank for the next patch, or enter a higher unused `X.Y.Z`.
3. Leave early access disabled for a regular release. Supply project-copy migration notes when needed.

The workflow bumps metadata when needed, tests the release snapshot, then pushes the tested commit and
`vX.Y.Z` tag atomically to `main` and publishes a GitHub release.
There is no release PR. [GitHub Releases](https://github.com/relai-ai/agent-eval-loop/releases)
contains generated change notes plus the supplied migration notes. For loading/installation
changes, verify a clean install and an upgrade in the affected hosts before releasing.

If preparation or tests fail, nothing is pushed. If `main` advances during testing, the push
fails without creating a tag; trigger a fresh run against current `main`.
If the push succeeds but GitHub release creation fails, finish that existing tag's release
with its source commit and migration notes, rather than bumping again. After checking the tag:

```sh
gh release create v0.1.0 --verify-tag --generate-notes --notes-file migration-notes.md
```

Substitute the actual version; add `--prerelease` only for an early-access release. Correct published
defects with a higher version containing a fix or revert; never move published tags. See the [README](README.md#updating)
for user updates and the [project-copy policy](skills/start/template/docs/upgrades.md) for migrations.
