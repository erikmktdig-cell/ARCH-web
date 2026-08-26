# ARCH Web v0.1.0 Release Report

## Approved Baseline

- W09 baseline: `286b7d7b92140159911e1bf5bea3554fcdbb5c15`.
- W00-W09 are approved and closed.
- Package version: `0.1.0` with no development or local suffix.
- Release hardening changes no files under `src/arch_web`.

## Release Hardening

- Added least-privilege CI with immutable action SHAs.
- Added Ubuntu and Windows matrices for Python 3.12 and 3.13.
- Added focused architecture, property, and release suites.
- Added fail-closed source and distribution inspection.
- Added deterministic manifests and byte-reproducibility checks.
- Added connected `pip-audit`, Dependabot, and a private-reporting policy.
- Removed tests from the sdist and retained `arch_web/py.typed` in both artifacts.
- Added installed-distribution smoke coverage for Web contracts and Runtime persistence.

## Local Quality Evidence

- Full suite: 570 PASS, 1 SKIP.
- Branch coverage: 94.27%.
- Architecture suite: 37 PASS.
- Property suite: 19 PASS.
- Release suite: 11 PASS.
- Ruff check and format: PASS.
- mypy strict: PASS across source, tests, and release scripts.
- `python -m build`, Twine, artifact inspection, and reproducibility: PASS.
- `git diff --check`: required again on the final release commit.

## Dependency Compatibility

- Declared dependency: `arch-runtime>=0.1.0,<0.2.0`.
- Runtime `v0.1.0` peeled commit: `363db8fba0513379ce869a79516c6c8b98226719`.
- Kernel `v0.1.0` peeled commit: `5589ec22230ce7979e365e614e9dfb167e7573b0`.
- Installed versions: Web 0.1.0, Runtime 0.1.0, Kernel 0.1.0.
- Runtime and Kernel do not import `arch_web`.

## Clean Install Evidence

- Windows / Python 3.12 / wheel: PASS.
- Windows / Python 3.13 / wheel: PASS.
- Windows / Python 3.12 / sdist build and install: PASS.
- Installed canonical round trip and Runtime create/persist/reload: PASS.
- Checkout package origins and `sys.path` leakage: rejected by the smoke.
- Ubuntu / Python 3.12 and 3.13: pending hosted CI on the final commit.

## Security And Supply Chain

- Runtime and Kernel resolve from released Git tags, not neighboring checkouts.
- Connected indexed-dependency audit: PASS, no known vulnerabilities found.
- Git dependencies are verified by version, requested tag, and peeled commit during install.
- Tracked source and distribution secret/path/database leakage scans: PASS on the candidate.
- Private Vulnerability Reporting: pending remote repository governance.

## Artifact Evidence

The deterministic candidate build produced:

- `arch_web-0.1.0-py3-none-any.whl`:
  `sha256:542c7b83a09bbcd3ef771a8a1eb47a1dfb74e4396de2078dbf9811ef20ffca25`.
- `arch_web-0.1.0.tar.gz`:
  `sha256:0213d504fa7b6ad31bc3f634a89b0a648738f100bef1e151ccafe7d14a5a8860`.

Both artifacts reproduced byte for byte. These are candidate hashes until rebuilt from the exact
final release commit. The external manifest records final commit, hashes, CI, governance, tag, and
release state without a circular tracked-file dependency.

## Remote Closure

The authenticated GitHub identity is `erikmktdig-cell`; at closeout start the target repository
`erikmktdig-cell/ARCH-web` returned 404. The remaining release blockers are:

- create the repository under the exact owner and push the candidate;
- pass hosted CI on the exact final commit;
- protect `main` with required checks, PRs, current branches, resolved conversations, linear
  history, no force pushes/deletion, and no unrestricted administrator bypass;
- enable Private Vulnerability Reporting;
- create annotated `v0.1.0` peeled to the final commit;
- create the GitHub Release with exact final artifacts and manifest.

No tag or release may be created while any item is pending. Full-system acceptance, dogfooding,
v0.2 work, and intelligence features remain outside this closeout.
