# Home Assistant environment boundary

Use the fork owner's designated isolated Ubuntu WSL development environment.
Record the instance identity, Home Assistant version, endpoint, configuration
root and approved access method. Verify the target before each deployment.
Use dedicated configuration, credentials, loopback ports, storage and logs.
Production and the upstream maintainer's Home Assistant instances are outside
this workflow. Provision dependencies in an isolated user-space environment.

# F1 Sensor source parity

Inspect the checkout and isolated instance's custom_components/f1_sensor
directory before deployment. Preserve unrelated work and synchronize every
intended addition, edit, rename and deletion from the reviewed Git commit.
Require an identical complete file inventory and byte-for-byte comparison
against the reviewed commit, excluding only runtime cache artifacts such as
`__pycache__`, `*.pyc` and `.DS_Store`. Record the SHA and comparison result.

# Local dev CI preflight

Run `npm run setup:ci` to create the isolated Python, Node, npm, browser and
workflow-validator environment. Versions and dependency inputs are recorded;
preflight refreshes stale setup rather than trusting an existing directory.
Before considering a code change ready for commit, run
`npm run verify:changed`. It uses the same check commands and selection policy
as GitHub, including the global runtime coverage gate for integration changes. Fix every
failure before reporting readiness. `--print-plan` and a no-change result are
not successful verification.

Run `npm run verify:dev` for a complete development snapshot. Before proposing
a substantial promotion, run `npm run verify:release -- --target beta` or
`npm run verify:release -- --target main` for its actual destination. These full
profiles include the security gate. Evidence in `test-results/verification.json`
is valid only for the recorded source fingerprint, tools and dependencies;
changes during a run invalidate the result. Never describe local success as
GitHub success, a published release, or a Home Assistant runtime activation.

Weblate target-language text and the number of supported languages are not
fixed test contracts. Test catalog structure, placeholders, delivered assets,
locale selection and per-key fallback against independent fixtures or current
catalogs. Target-language-only changes use the translations lane; changes to
English sources, localization code or tooling retain broader verification.
Obsolete target keys that Weblate has not removed yet are cleanup warnings;
invalid catalogs and placeholder errors for active keys remain blocking.

CI separates product verification, documentation delivery and release security
readiness. Route checks by actual impact, including promotions; a metadata-only
workflow edit does not justify every product test. Keep behavioral regressions,
HACS/hassfest and package integrity blocking when applicable. Per-file coverage
percentages, broad pixel diffs and timing benchmarks are review evidence, not
universal merge requirements. Do not replace product behavior with source-code
spelling assertions or require a repaired dependency/retired exception to remain.

Run blocking browser tests without assertion retries. Rendering auto-wait is
expected; a workflow's first attempt is not proof of a test's first-attempt pass.
Report all selected local failures in one verification attempt. Missing trusted
remote evidence is not a successful check, and a failed dependency-health or
publication job must not be described as a product regression.

Publication changes must preserve the normal `dev → beta → main` rollout.
Beta documentation must work on its first promotion without requiring the new
publisher on `main`. Test that transition explicitly. Keep Pages failures out
of product verification and never publish unverified companion-branch content.

HACS and hassfest remain GitHub-only verification gates. Local verification is
the agent's pre-commit quality gate; passing it does not replace the required
remote checks after the user pushes with GitHub Desktop. A failed selected job
cannot be excused as a skipped check or replaced by unrelated green evidence.

If the isolated target is unavailable or parity cannot be established, report
the limitation and keep it as a merge gate. Restart or reload Home Assistant,
confirm the config entry loads from the verified tree and record runtime
results separately from CI. For timing changes, verify authenticated analysis
snapshot delivery, timestamped TimingData, Live Delay release, replay seek and
reset, source-generation isolation and runtime logs. Record synthetic coverage
and real race-feed evidence separately. Missing required runtime evidence
blocks merge.

One-time owner exception approved November 5, 2026: the isolated Circle of Doom
Phase 3 foundation in PRs #11�16 at heads 737472ed, 38ced917, 844c5a65,
a0d9039a, 1732bb3c and 897c84e5 may merge without new HA runtime evidence.
This covers only the reviewed pure helpers and unused synthetic preview, with
an empty pit-loss fallback catalog and no production consumers. It does not
claim runtime tests passed, waive CI/security/package gates, authorize deployment,
or extend to future adapters, live/replay integration or prediction enablement.
Changed scope requires renewed review. See
`docs/research/CIRCLE_OF_DOOM_NEXT_STEPS.md` for evidence limits and approval.

# Release notes and commit policy

F1 Sensor uses Conventional Commits and semantic-release. Preserve individual
Conventional Commits when promoting `dev` to `beta` and `beta` to `main` with a
merge commit; never squash or rebase a promotion.

Write commit summaries in English as plain text, without Markdown, issue
numbers, PR numbers, or implementation details. Use `feat:` for a new
user-facing capability and `fix:` for a correction. Prefer a scope when it
clarifies the affected user area: `integration`, `card`, `blueprint`, or
`translations`.

Commit bodies are published in release notes. Omit the body when the summary is
self-explanatory. Otherwise use at most two concise user-facing sentences. If a
commit fully resolves an issue, end the body with `Fixes #<number>`; retain this
reference because it drives issue handling and lets users reach the context.

Use `chore(translations):`, `chore(i18n):`, `chore(accessibility):`,
`chore(a11y):`, or `chore(compatibility):` for user-visible improvements that
do not change semantic-release versioning. Internal chores, refactors, tests,
CI, build work, branch synchronization, release tooling, and formatting must
not appear in user-facing release notes.

Use `feat(blueprint):` for a new or materially expanded blueprint. For a
breaking change, write `feat(scope)!:` or `fix(scope)!:` and include a final
`BREAKING CHANGE:` footer explaining what users must change.

The generated release keeps the download shield, beta notice, sponsorship
message, and sponsor buttons. Add a short manual editorial summary only when a
release has a main story, a beta-testing focus, or an external contributor to
thank; remove or leave the HTML prompt comment otherwise.
