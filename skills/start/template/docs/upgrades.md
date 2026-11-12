# Upgrading project copies

Plugin updates do not replace files already copied into this project.

- Record upstream paths, the actual source version/commit, and local adaptations in
  `relai/UPSTREAM.md` or an existing provenance record. Unknown provenance stays unknown;
  the currently installed plugin version does not identify older copies. For development
  checkouts, include the commit and local changes.
- Compare upstream changes with the project's copy. Apply relevant differences, preserving
  local modifications and project data; never recopy the template over an existing `relai/`.
  Test affected guarantees and record which files were upgraded, their source, and validation.
  Partial upgrades advance provenance only for those files; rollback restores files and provenance together.

Changes to frozen content follow the [project contract](../README.md#fixed-rules): pause
optimization against affected tests, record the reason, obtain fresh review, and refreeze with
that reason. Preserve previous results. Changes to measurement meaning or relevant execution
conditions, including shared graders/runners outside the frozen digest, need a comparable
baseline before improvement claims resume. A plugin version bump alone requires no refreeze.
