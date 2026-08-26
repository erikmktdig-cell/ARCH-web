# WP-W09 Implementation Evidence

## Status

- WP-W09 implementation: COMPLETE
- WP-W09 review: PENDING
- ARCH Web Engineering Pack: NOT YET CLOSED pending W09 approval
- Baseline: `6c069d87e67410d625fc0a10958597ff236afe89`
- Scope: local implementation only; no tag, push, hosted release, PyPI publication, cloud account,
  production deployment, production datastore, public internet, or production credential used.

## Contract And Port Inventory

- Exact release: `ReleaseCandidateManifest`, `ReleaseArtifact`, `ReleaseVersion`.
- Target and configuration: `TargetEnvironment`, `EnvironmentConfigContract`, `SecretReference`.
- Provider and plan: `DeploymentProviderProfile`, `DeploymentStrategy`, `DeploymentPlan`,
  `DeploymentStep`, `DeploymentProviderPort`.
- Migrations: `ProductionMigrationPlan`, `ProductionMigrationExecutionEvidence`.
- Execution: `DeploymentExecutionAuthorization`, `DeploymentAttempt`, `DeploymentReceipt`.
- Verification/recovery: `PostDeployVerificationPlan`, `PostDeployVerificationEvidence`,
  `RollbackPlan`, `RollbackExecutionEvidence`.
- Governance: `ReleaseFinding`, `ReleaseReviewPackage`, `DeploymentApprovalPackage` and five public
  command/result pairs for prepare, authorize, execute, verify, and approve.

## Candidate And Artifact Matrix

| Invariant | Evidence |
| --- | --- |
| W08 package current | Project, source-tree, Git and candidate bindings tested |
| Immutable source | Floating `HEAD`, `main`, and `latest` rejected |
| Build once/deploy exact artifact | SHA-256 recomputed before and after local promotion |
| Artifact drift | Source mutation and receipt digest mismatch blocked |
| Provenance | Required SBOM/signature refs block when absent; no compliance overclaim |

## Environment, Configuration And Secrets

| Case | Result |
| --- | --- |
| Explicit production target/provider/strategy | Required |
| Missing/unknown config | BLOCK |
| Localhost, test DB, mock endpoint, placeholder | BLOCK in production |
| Raw secret-like value | BLOCK |
| Secret reference | Accepted and persisted without value material |
| Provider not production-approved | BLOCK |
| Adapter identity drift | BLOCK before mutation |

## Deployment Plan And Provider

- Equivalent explicit input produces identical candidate, step ordering, plan and findings.
- Dry-run/planning calls no provider method and mutates no external state.
- Authorization binds exact candidate, plan, target, provider, artifact, migration, prior deployment,
  reviewers and execution ID; Critical requires independent evidence.
- The explicit `LocalDeploymentProvider` copies one exact artifact to an isolated directory, starts a
  loopback-only HTTP service, records sanitized digests, supports exact retries and verifies cleanup.
- Same execution ID with different authority rejects; wrong artifact or target/config drift rejects.

## Migration Governance

- Application target, expected schema version, ordered IDs/checksums, risk, compatibility, backup,
  irreversibility and postcondition are explicit.
- Wrong datastore, destructive migration without recovery, unauthorized irreversibility and invalid
  rollback claims block planning.
- A disposable application schema-state fixture proves exact precondition `1 -> 2`; wrong state
  blocks before deployment. No Runtime/K10 or SQL-schema migration is invoked.

## Verification, Rollback And Reconciliation

- Real local HTTP verifies reachability, application health, exact deployed digest, critical smoke,
  backend connectivity, security smoke, mock/test leakage and applicable TLS policy.
- Provider-ready evidence alone cannot call Runtime; wrong version, failed health/smoke, stale receipt
  and missing observations block.
- Exact rollback stops the exact local deployment and verifies cleanup. A second rollback reports no
  external change.
- Failure and uncertainty outcomes are modeled separately; `RECONCILIATION_REQUIRED` never advances.
- Runtime rejection/failure preserves verified external receipt evidence for governed retry and does
  not trigger a blind redeploy.

## Runtime Authority

- Final bridge uses only public `arch_runtime.Runtime.apply_transition()`.
- Transition is exclusively `RELEASE_READY -> DEPLOYED` and follows verified deployment, clean
  reconciliation, zero blockers and explicit final approval.
- Metadata binds candidate, W08 package, plan, authorization, receipt, verification, environment,
  provider and artifact fingerprints/digests.
- Exact final retry is idempotent. Runtime CAS/domain/infrastructure failures remain Runtime results
  or exceptions; the bridge performs zero provider/network/filesystem/Git/migration work.

## Property And Architecture Evidence

- Hypothesis: config canonicalization, finding ordering, semantic fingerprint mutation and production
  leakage fail-closed properties.
- Architecture guards: no provider SDK in neutral core, no IO in planning, no arbitrary shell or Git
  mutation, no private Runtime API/database, explicit provider/strategy, no raw production credential,
  and no provider operation in the Runtime bridge.
- Historical W06-W08 scope tests now audit their own package surfaces while W09 owns delivery scope.

## Defects Found And Fixed

1. Semantic execution IDs containing `:` were initially used as directories and failed on Windows.
   Deployment directories now use a filesystem-safe deterministic provider identity while receipts
   retain the exact execution ID.
2. Full target drift was initially checked only by environment ID immediately before execution.
   Execution now rechecks the complete target fingerprint.
3. Provider capability and strategy sets initially allowed empty profiles. Profiles now require both.
4. Production approval and concrete adapter identity were not initially rechecked. Both now fail
   closed before external mutation.

## Quality Gates

Final pre-commit evidence:

- Full tests: 559 PASS, 1 SKIP.
- Branch coverage: 94.27%.
- Focused W09: 76 PASS.
- Hypothesis property tests: PASS.
- Architecture tests: PASS as part of the full suite.
- Disposable deployment, migration, rollback/reconciliation and Runtime lifecycle integrations: PASS.
- Ruff check: PASS.
- Ruff format check: PASS.
- mypy strict: PASS across 174 source/test files.
- Wheel and sdist build: PASS.
- Twine wheel/sdist checks: PASS.
- Git diff check: PASS.
- Final local commit and clean-worktree evidence: recorded after commit.
