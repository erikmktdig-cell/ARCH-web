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
