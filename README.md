# ARCH Web

`arch-web` defines immutable, framework-neutral contracts for governed web projects.

The dependency direction is intentionally one-way:

```text
arch-web -> arch-runtime v0.1.x -> arch-kernel v0.1.x
```

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
