# Releasing RELAI

## One-time release app setup

Releases use a dedicated GitHub App, `relai-agent-eval-loop-release`, owned by `relai-ai`.
Give it only repository **Contents: read and write** (Metadata read is automatic), disable
webhooks, and install it on **only `agent-eval-loop`**. Do not reuse the shared organization's
release app or its private key.

In this repository, configure the `release` Actions environment:

- Allow deployments from the `main` branch only (not tags), require a maintainer's approval,
  and disable administrator bypass. Allow the initiating maintainer to approve their own run.
- Set the environment variable `RELEASE_APP_CLIENT_ID` to the dedicated app's client ID.
- Set the environment secret `RELEASE_APP_PRIVATE_KEY` to that app's PEM private key.
  Keep it out of repository and organization secrets so other jobs cannot access it without
  the environment's protection rules.

Replace the shared release app's bypass entry in the `Protect main` ruleset with the dedicated
app's **Always allow** entry. Preserve the other actors and all existing protection rules.
This exception lets the app push a tested release commit directly to `main`.

## Publish a release

Feature PRs do not bump versions. To release merged work:

1. Open **Actions → Release → Run workflow**, selecting **main**.
2. For the first release, enter the current manifest version (`0.1.0`). After that, leave
   version blank for the next patch, or enter a higher unused `X.Y.Z`.
3. Leave early access disabled for a regular release. Supply project-copy migration notes when needed.
4. After tests pass, approve the `release` environment deployment to let the publish job run.

After changing the workflow or its credential names, start a new run from current `main`.
Re-running an older failed run uses its original workflow definition and source revision.

The workflow prepares and tests a release snapshot without release credentials. On a fresh runner,
the approved publish job reconstructs a snapshot from the same source commit and version, verifies
that its Git tree matches the tested tree, then creates the app token. Commit timestamps may differ;
the published files must match exactly. It pushes the verified release commit and
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

The workflow publishes immediately with generated change notes and the supplied project-copy notes.
To add a release introduction, edit the published release on GitHub, prepend the introduction, and
retain the source commit, project-copy information, and generated changes.
