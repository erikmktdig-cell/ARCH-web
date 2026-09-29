# ARCH Web

`arch-web` defines immutable, framework-neutral contracts for governed web projects.

## Installation

ARCH Web 0.2.x supports Python 3.12 and 3.13. Until publication on a package index,
install the verified GitHub Release wheels together:

```console
python -m pip install arch_kernel-0.2.0-py3-none-any.whl arch_runtime-0.2.0-py3-none-any.whl arch_web-0.2.0-py3-none-any.whl
```

The supported release chain is `arch-web 0.2.x` -> `arch-runtime 0.2.x` ->
`arch-kernel 0.2.x`. Package metadata requires `arch-runtime>=0.2.0,<0.3.0`;
development and CI pin the exact released 0.2.0 dependency wheels and their hashes in the lock.
Web contract payload versions remain unchanged; distribution version is a separate concept.
Minor `0.2.x` releases may add compatible contracts and fixes. Breaking public-contract changes require
a new minor line while the project remains below 1.0.

The dependency direction is intentionally one-way:

```text
arch-web -> arch-runtime v0.2.x -> arch-kernel v0.2.x
```

## Runtime lifecycle authority

The Web lifecycle is the closed, namespaced Runtime workflow
`arch_web.project_lifecycle`; it is not Kernel `PhaseStatus` and does not use the
phase-oriented `PROJECT_LIFECYCLE` domain. After creating the Runtime project, callers must
explicitly invoke `initialize_web_lifecycle(...)`, which initializes only `DRAFT` and binds the
canonical workflow identity, version, and definition fingerprint.

Every W02-W09 approval bridge reads the authoritative `WorkflowStateRecord` from Runtime before
requesting an adjacent transition. Caller status fields are assertions only. Aggregate and target
workflow CAS evidence are both bound to the request, including exact idempotent retries. Runtime
metadata crosses the boundary as `dict[str, str]`; structured evidence is encoded as deterministic
canonical JSON text and absent optional values are omitted.

WP-W01 includes project, stack, requirement, surface, route, information architecture,
design, evidence, and integrity-aware reference contracts. It provides pure canonical JSON
encoding, decoding, validation, and SHA-256 fingerprints. It does not implement workflows,
generation, filesystem mutation, persistence, framework adapters, previews, or deployment.

`none` and `unspecified` stack choices are represented by distinct `ArchitectureChoice`
values. Dates are accepted only when supplied by callers and must be timezone-aware.

## Requirements workflow

W02 adds a pure preparation flow followed by an explicit Runtime approval boundary:

```python
prepared = prepare_requirements(PrepareRequirementsCommand(intake))

# Human review happens here. Completeness is not approval.
if prepared.review_package.readiness is RequirementsReadiness.READY_FOR_REVIEW:
    approved = approve_requirements(runtime, approval_command)
```

The route recommendation is advisory and never changes the selected ARCH route. Approval
requires explicit evidence and a successful public `Runtime.apply_transition()` result.
This workflow generates no web code, routes, repositories, previews, or deployments.

## Information architecture workflow

W03 transforms approved requirements into a deterministic information-architecture proposal:

```python
architecture = prepare_architecture(PrepareArchitectureCommand(...))

# Review readiness is not approval.
if architecture.review_package.readiness is ArchitectureReadiness.READY_FOR_REVIEW:
    approved = approve_architecture(runtime, approval_command)
```

Surfaces represent meaningful interaction contexts and do not necessarily have URLs.
Navigation is modeled independently from route nesting. Routes use the framework-neutral
brace grammar (`/products/{product_id}`) and do not encode React, Next.js, Vite, or filesystem
conventions. Every approved requirement receives an explicit architecture disposition,
including deferred W04 and W06/W07 evidence.

Architecture approval requires exact requirement, IA, navigation, and review fingerprints,
explicit evidence, and a successful public `Runtime.apply_transition()` result. W03 produces
no visual design or frontend code.

## Design system and UI specification

W04 converts exact approved requirements, information architecture, and explicit design intent
into deterministic, framework-neutral design-system and UI contracts. Primitive values remain
separate from semantic token roles, and UI components reference semantic roles with explicit
applicable states. Responsive policy describes behavior across ranges, including preservation
of required actions, rather than treating breakpoints as the specification.

Reference profiles are immutable accessible baselines. A recommendation is advisory and a
profile becomes governed input only through explicit adoption. Design-time checks cover color
contrast intent, labels, focus, keyboard behavior, target sizing, error semantics, data states,
and purposeful motion with reduced-motion behavior; they do not claim rendered WCAG conformance.
Visual references remain evidence, never authority.

`READY_FOR_REVIEW` is not approval. The `ARCHITECTURE_APPROVED` to `UI_APPROVED` transition binds
the exact requirements, architecture, intent/profile, design system, UI specification, coverage,
review, and approval-evidence fingerprints through public `Runtime.apply_transition()`. W04 does
not generate frontend code, CSS, framework configuration, previews, or deployments.

## Workspace and repository execution

W05 treats the local workspace and Git repository as an execution substrate; ARCH Runtime remains
the authority. Exact approved UI contracts produce a deterministic stack manifest, implementation
plan, path ownership claims, changeset, dry-run, execution receipt, and review evidence.
`WORKSPACE_PREPARED` therefore does not imply `IMPLEMENTATION_READY`.

Dry-run performs no mutation and reports preconditions, collisions, destructive operations, Git
actions, and policy violations. Apply rechecks the exact baseline under an exclusive workspace
lock, confines every managed path to the approved root, preserves unrelated files, and records
either verified success, exact no-op, rollback, or reconciliation-required evidence. Reusing an
execution identity with a different changeset fails closed.

Local Git support is deliberately narrow: inspect, initialize, explicitly stage managed paths, and
create a local commit. There is no push, pull, reset, clean, remote creation, tag, or release API.
Stack resolution has no hidden `latest`; probes use adapter-owned argv with `shell=False`, bounded
output, timeout, and redaction. Secret-bearing files and content are rejected, while non-secret
`.env.example` templates are permitted.

Only a successful public Runtime transition from `UI_APPROVED` to `IMPLEMENTATION_READY`, bound to
the exact post-state receipt and explicit approval evidence, authorizes the next phase. W05 creates
no final UI, backend behavior, preview, deployment, or W06 product implementation.

## Frontend engineering

W06 turns exact `IMPLEMENTATION_READY` evidence into a bounded frontend assignment. Before the
first source mutation, the public Runtime API must authorize the
`IMPLEMENTATION_READY -> IMPLEMENTING` transition. The Runtime bridge never writes files, and an
executor's output remains an untrusted proposal until scope, path, traceability, design, data,
dependency, and browser-side security checks pass.

Validated proposal bytes are converted into an exact W05 `WorkspaceChangeSet`; W05 remains the
only filesystem and Git execution substrate. Framework behavior belongs to an explicitly selected
stack adapter, with no hidden fallback. W06 includes a small static reference adapter only for the
governance vertical slice.

Completion evidence binds routes, surfaces, components, applicable states, semantic tokens,
responsive rules, accessibility intent, pending W07 data boundaries, engineering checks, source
tree evidence, and reconciliation status. Engineering checks do not claim rendered accessibility,
visual, browser, preview, release, or deployment quality. W06 leaves lifecycle state at
`IMPLEMENTING`; W08 owns rendered QA and later testing semantics.

## Backend and data integration

W07 consumes the exact W06 completion package and closes every pending backend binding as
implemented, not applicable, deferred with authority, or blocked. Approved interface, data,
ownership, retention, authentication, server authorization, persistence, migration, integration,
and public failure contracts are immutable inputs; executor output remains an untrusted proposal
until W07 validation succeeds. Validated bytes flow through the existing W05 dry-run and safe-apply
engine, so W07 does not introduce another filesystem or Git mutation path.

ARCH Runtime persistence and generated-application persistence are separate systems. Application
code cannot reuse the Runtime database path, connection, repositories, Unit of Work, tables, SQL
migrations, or K10 contract migrations. The bundled Python/SQLite implementation is an explicitly
selected offline reference adapter for governance evidence, not a production default or hidden
stack fallback.

Backend completion binds the exact pre/post tree, W06 evidence, binding matrix, contracts,
migrations, engineering checks, findings, and reconciliation state. A truly static project with no
backend units and no pending bindings receives deterministic `NOT_APPLICABLE` evidence. W07 keeps
the lifecycle at `IMPLEMENTING`; it does not claim W08 testing/QA or W09 release readiness.

## Testing, preview, and design QA

W08 freezes an exact `QACandidateBaseline` from the approved W05-W07 evidence, source-tree
fingerprint, Git HEAD, build artifacts, Runtime version/fingerprint, route, and explicitly adopted
QA profile. Public Runtime authorization moves that exact candidate from `IMPLEMENTING` to
`TESTING`; preparation alone never implies that QA passed.

The reference vertical slice starts an isolated loopback preview, drives a locally provisioned
Chromium browser through CDP, records actual interaction/focus/responsive/console/network evidence,
and executes the generated backend against a disposable application SQLite database. The adapter
tests server validation, owner-scoped authorization, persistence, and Runtime-database separation,
then removes the application database. It requires no public internet or production data.

Without an externally approved screenshot baseline and threshold, visual QA remains structural and
contract-bound; it never claims pixel equivalence. Automated accessibility evidence likewise does
not claim WCAG certification. Browser unavailability, unstable attempts, stale evidence, missing
material coverage, failed cleanup, and blocking findings cannot silently become PASS.

Only exact, current, clean evidence plus explicit external approval may request
`TESTING -> RELEASE_READY` through public `Runtime.apply_transition()`. W08 has no `DEPLOYED`
transition, deployment adapter, push, tag, release, or product-source remediation path.

## Deployment and release

W09 freezes an exact `RELEASE_READY` candidate and binds the W08 package, tested source tree and
Git commit, immutable artifact digests, target environment, non-secret configuration, secret
references, provider profile, migration disposition, rollout strategy, and recovery plan. The
preferred invariant is build once and deploy the exact artifact that W08 tested; floating branches,
`latest`, stale evidence, config drift, raw secrets, test-system leakage, unsafe migrations, and
unapproved production providers fail closed.

Planning is deterministic and performs no provider mutation. Execution requires a separate
`DeploymentExecutionAuthorization` bound to the exact candidate, plan, environment, adapter,
artifact, migration plan, prior deployment, reviewer evidence, and idempotency identity. Provider
success produces a receipt, not project authority. Application-level health, exact artifact,
frontend/backend smoke, security behavior, mock leakage, and applicable TLS checks must pass, and
reconciliation must be clean before final approval.

Application migrations remain separate from ARCH Runtime/K10 and SQL schema migrations. Recovery
explicitly distinguishes rollback from roll-forward-only cases; uncertain external state becomes
`RECONCILIATION_REQUIRED` and never `DEPLOYED`. Only the public Runtime bridge can request
`RELEASE_READY -> DEPLOYED`, and that bridge performs no network, filesystem, Git, provider, or
migration work. The bundled loopback provider is an explicit disposable reference adapter, never a
production default. Implementing W09 does not tag, push, publish, release, or deploy `arch-web`.

## Release evidence

The v0.1.0 closeout verifies the full test suite, branch coverage, source boundaries, wheel and
sdist contents, isolated Python 3.12/3.13 installs, dependency advisories, hosted CI, and repository
governance. Exact commit, artifact hashes, CI runs, and residual limitations are recorded in
`docs/WEB_V0_1_0_RELEASE_REPORT.md` and the generated release manifest attached to the GitHub
Release.

This first governed release provides a library and reference adapters. It does not claim general
production readiness for generated applications, WCAG certification, cloud-provider coverage, or
full-system acceptance; those require separate evidence.
