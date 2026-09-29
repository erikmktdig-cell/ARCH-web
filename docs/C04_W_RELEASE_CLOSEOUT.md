# C04-W Release Closeout

## Scope

Release approved C03 (`cfa4e9a20780cc00354400f32170fe5fa0aa60c1`) without redesigning
Web domain behavior. The distribution becomes 0.2.0; existing Web payload contract versions
remain 0.1.0. Runtime dependency metadata is exactly `arch-runtime>=0.2.0,<0.3.0`.
Kernel and Runtime repositories are not modified.

## Released Dependencies

Development/CI resolve public wheels, not Git source or editable upstream checkouts:

- Kernel 0.2.0, commit `4aa6a3acddd1b0ef761fb4dd0cfff720706ff5df`, wheel SHA-256
  `3c581c37c4890ac50ff8c1722aca7cc4e29fed85a37656d6f08e22ffb8847b5c`.
- Runtime 0.2.0, commit `61624e7e9b5e5169892ff3051cad0e0ede642226`, wheel SHA-256
  `6f0271bb1dca67dfd8aaf6b4b5a6a43bd3b2e8e2ab110b01e99aa48c719a42f2`.

The uv override binds the transitive Kernel wheel for development/CI; it does not add a
direct Kernel dependency to Web distribution metadata. The lock records both wheel hashes.
Isolated verification downloads and checks each approved digest before installation.

## Installed Lifecycle Evidence

`scripts/clean_install.py` creates a fresh environment outside all repositories, installs
the two verified release wheels and the candidate Web wheel/sdist, removes import overrides,
and invokes Python in isolated mode. It copies fixture support but never package source.
`installed_smoke.py` verifies all three distribution versions and site-packages origins.

The approved C03 real-SQLite scenario is reused directly rather than replaced with a weaker
synthetic transition loop. It explicitly initializes Web workflow authority and exercises
every W02-W09 bridge, including local provider execution, verification and final approval.
After every edge it asserts aggregate/workflow versions and replay fingerprints. Final
expectations: DEPLOYED, aggregate version 10, workflow version 9 and 10 events. Retry,
conflict, stale workflow evidence and string-only metadata assertions remain active.

This is release compatibility evidence with deterministic fixtures, not a new Track A
acceptance run, real customer deployment, or universal browser/design-QA claim.

## Blocking Gates

All existing 13 protected-main check names are preserved. Full suites run on Windows and
Ubuntu with Python 3.12/3.13; installed wheel scenarios run on all four combinations and
sdist installation runs separately. CI also checks actual branch coverage independently
of the combined coverage.py metric. No coverage exclusions or new skips are introduced.

Archive validation checks package identity, the exact portable dependency range, typed
package data, secrets, generated state, unsafe archive paths and source dependency leakage.
Manifest generation requires a clean checkout at the declared final commit and explicit
gate evidence, rather than defaulting unexecuted checks to PASS.

Connected security checks cover hash-pinned requirements and every registry version in the
lock, including other-platform packages. Repeated wheel/sdist builds use fixed timestamps.
Final artifacts must be rebuilt and reverified after the exact final main commit is known.

## Governance and Stop

Main requires 13 successful checks, one independent approving review, approval of the most
recent push, admin enforcement, linear history and resolved conversations. Force pushes and
deletions are forbidden. Do not bypass these requirements to complete publication.

Preserve v0.1.0: tag object `d081af853591ef684131f7aed5233b75804f7067`, peeled commit
`7e882576adb48f302b95200375749915592542c4`.

Only create annotated v0.2.0 after final-main CI, artifact identity, installed compatibility,
security and governance are verified. Publish wheel, sdist and manifest, then independently
download and reconcile hashes. C05, Track A/B and broader product scope remain blocked.

Final measured gates and release status are recorded in the external report/manifest and
Notion; this methodology document does not predeclare them as passing.

## Local Candidate Evidence (2026-09-29 UTC)

- Full clean run: 713 passed, one pre-existing Windows skip (symlink creation unavailable).
- Actual branch coverage: 1987/2198 = 90.40%; combined coverage: 95.76%.
- Architecture: 39 passed; property: 19 passed; release: 141 passed.
- Ruff, formatting, strict mypy (197 files), lock freshness and diff checks passed.
- Wheel/sdist inspection, Twine, and two byte-identical repeated builds passed.
- Fresh Windows Python 3.12 wheel and sdist installations both completed the eight-edge
  lifecycle with released upstream wheels and locked transitive dependencies.
- Connected audit of all 66 locked registry versions found no known vulnerabilities.

The initial diagnostic branch-only result was 85.94%, despite historical combined coverage
of 93.95%. The independent branch gate exposed the metric ambiguity. Added regression tests
cover approval preconditions, individual domain-record round trips, optional release
evidence, invalid references, duplicate identities, required human authority and canonical
JSON rejection. No production behavior, coverage exclusions or skip policy was changed.
The sole production-file change after C03 is the distribution version constant.

These results are candidate evidence, not final-main release evidence. Remote matrix,
independent latest-push review, protected merge, exact-final-main CI, final artifact manifest,
tag and publication remain separate mandatory gates. No v0.2.0 release is asserted here.
