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
