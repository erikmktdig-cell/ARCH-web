# Changelog

## Unreleased

## 0.1.0 - 2026-08-26

### Added

- WP-W01 immutable web project contracts and closed enums.
- Canonical JSON codec, exact contract version checks, and SHA-256 integrity verification.
- Pure cross-reference validation for requirements and information architecture.
- WP-W02 immutable Product Brief, intake, findings, route recommendation, and review contracts.
- Deterministic requirements derivation, normalization, gap/conflict analysis, and readiness.
- Explicit requirements approval bridge through the public ARCH Runtime API.
- WP-W03 deterministic surface, route, navigation, journey, and requirement-coverage planning.
- Framework-neutral route normalization using the canonical brace parameter grammar.
- Architecture findings, route-aware readiness, canonical review evidence, and codec support.
- Explicit architecture approval through the public ARCH Runtime API with exact fingerprints.
- WP-W04 immutable design intent, reference profiles, primitive and semantic token layers,
  typography, layout, responsive, motion, component, surface, coverage, finding, and review
  contracts.
- Deterministic design-time contrast, token resolution, component-state, form, modal-focus,
  responsive-action, requirement-provenance, and route-aware readiness validation.
- Explicit UI approval through the public ARCH Runtime API with exact governed fingerprints.
- WP-W05 immutable workspace target/baseline, resolved stack, implementation plan, path claim,
  changeset, execution policy/receipt, repository evidence, finding, and review contracts.
- Confined local filesystem execution with mutation-free dry-run, exact preconditions, exclusive
  locking, external idempotency, rollback, and reconciliation evidence.
- Narrow local Git and allowlisted toolchain adapters with explicit staging, offline defaults,
  bounded/redacted diagnostics, and secret-artifact rejection.
- Explicit implementation-readiness approval through public ARCH Runtime using exact W05 evidence.
- WP-W06 immutable frontend authorization, assignment, proposal, artifact, traceability,
  dependency, engineering-check, finding, completion, and review contracts.
- Public Runtime authorization for `IMPLEMENTATION_READY` to `IMPLEMENTING` with zero workspace
  mutation in the bridge.
- Deterministic proposal validation and conversion to the W05 workspace execution layer, including
  exact post-bootstrap baseline binding, path claims, drift/security checks, and reconciliation.
- Explicit static reference adapter for semantic-token compilation and the governed frontend
  vertical slice; unsupported stacks fail closed without a hidden default.
- WP-W07 immutable backend assignment, interface, application-data, ownership/lifecycle,
  authentication, authorization, persistence, migration, integration, failure, check, finding,
  completion, and review contracts with canonical round-trip codecs.
- Deterministic frontend/backend binding closure and proposal validation before conversion to the
  existing W05 dry-run and safe-apply engine; W07 leaves Runtime state at `IMPLEMENTING`.
- Explicit offline Python/SQLite reference adapter, disposable application-database migration
  harness, owner-scoped server authorization, parameterized repository operations, transactional
  rollback evidence, and local idempotent integration double.
- Architecture guards that confine `sqlite3` to the bounded backend adapter and prohibit Runtime
  persistence reuse, public-network test dependencies, W08 QA, and W09 delivery scope.
- WP-W08 immutable candidate, QA profile, scope, scenario, result, evidence, finding, coverage,
  review, and release-readiness contracts with canonical round-trip codecs.
- Public Runtime transitions from `IMPLEMENTING` to `TESTING` and from `TESTING` to
  `RELEASE_READY`, bound to exact candidate and independently approved QA evidence.
- Isolated loopback preview, raw-CDP local Chromium execution, disposable generated-backend
  integration, responsive/accessibility/design observation, bounded flakiness, and fail-closed
  release-readiness aggregation without public internet or product-source remediation.
- WP-W09 immutable release candidate, artifact, environment/config/secret, provider, deployment,
  production-migration, verification, rollback, reconciliation, finding, review, and final approval
  contracts with deterministic canonical evidence.
- Explicit execution authorization, exact provider/artifact binding, idempotent bounded deployment,
  application-level post-deploy verification, and public Runtime `RELEASE_READY` to `DEPLOYED`
  approval without treating provider success as authority.
- Disposable loopback deployment and application-schema fixture proving exact artifact promotion,
  real HTTP health/smoke checks, migration preconditions, rollback, reconciliation, and cleanup
  without cloud credentials, public internet, tags, push, publication, or production mutation.

### Fixed

- Application migration evidence now executes each approved SQL step inside the controlled SQLite
  transaction instead of relying on `executescript`, preserving rollback on a failing step.
- Earlier W05/W06 architecture tests now distinguish the authorized W07 backend adapter from still
  forbidden browser, deployment, framework, and remote-delivery dependencies.
- Browser support policies now normalize engine/version pairs together, preventing version drift
  when caller order differs.
- Multi-viewport evidence and review references now deduplicate and sort by their public contract
  identities, preserving canonical QA aggregation.
- Disposable deployment paths derive filesystem-safe provider identities instead of using semantic
  execution IDs directly, preserving Windows portability without changing governed evidence.

### Release hardening

- Added immutable-SHA GitHub Actions for supported Python versions on Ubuntu and Windows,
  isolated installed-distribution checks, artifact inspection, and connected dependency audit.
- Added deterministic release manifests, source and distribution leakage checks, and
  byte-reproducibility verification for wheel and sdist builds.
- Added a private vulnerability reporting policy and monthly Dependabot checks.
- Excluded the test suite and disposable local state from published distributions while retaining
  typed package metadata and reviewable public sources.
