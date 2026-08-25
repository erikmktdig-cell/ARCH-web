# W08 Implementation Evidence

## Baseline and scope

- Baseline: `6514a764b75ba70ee479f63735af06f6108555a0`
- Package: WP-W08 Testing, Preview and Design QA
- Dependencies: public `arch-runtime` v0.1.x and `arch-kernel` v0.1.x APIs
- Excluded: deployment, `DEPLOYED`, W09, product-source remediation, tag, push, and release

## Governed lifecycle

- `IMPLEMENTING -> TESTING` freezes and authorizes the exact QA candidate.
- `TESTING -> RELEASE_READY` requires current evidence, complete material coverage, zero blocking
  findings, clean reconciliation, verified preview cleanup, and explicit external approval.
- Runtime bridges perform no browser, process, filesystem, screenshot, network, or persistence work.

## Candidate and contracts

The candidate binds requirements, architecture, design system, UI specification, W05 plan, W06
completion, W07 completion, source tree, Git HEAD, build artifacts, Runtime optimistic preconditions,
route, and adopted QA profile. W08 records immutable scenarios, attempts, environment evidence,
typed category evidence, findings, coverage, review, and release-readiness packages through the
canonical W01 codec.

## Reference vertical slice

1. Prepare exact W06 and W07 completion evidence.
2. Freeze candidate, scope, profile, and preview plan.
3. Authorize `TESTING` through public Runtime.
4. Start an isolated loopback preview and verify readiness.
5. Launch local Chromium with explicit argv, `shell=False`, bounded CDP timeouts, and an ephemeral
   profile.
6. Navigate the real route, activate the governed interaction, and observe outcome, focus,
   landmark, overflow, console, rejection, external request, and screenshot-digest evidence at
   desktop and mobile viewports.
7. Execute the generated backend and schema against a disposable application DB; verify persistence,
   validation, owner authorization, cross-user denial, and Runtime DB separation.
8. Aggregate accessibility, responsive, structural design, security, integration, performance,
   coverage, findings, and cleanup evidence.
9. Build release-readiness evidence for independent approval and request `RELEASE_READY` through
   public Runtime.

## Evidence policy

- Synthetic identities and fixture data only; no production credentials or customer data.
- Screenshots are retained as SHA-256 digests in contract evidence, not uploaded.
- No approved visual baseline means structural W04 validation, never a pixel-match claim.
- Automated accessibility checks do not claim legal compliance or WCAG certification.
- Retries are bounded and recorded. Inconsistent attempts remain `FLAKY` and block critical paths.
- Missing browser tooling is `INCONCLUSIVE`, never PASS.
- W08 reports defects and does not mutate product source to remediate them.

## Defects found and fixed

- Browser engine/version normalization originally sorted each sequence independently; pairs now
  remain aligned under canonical ordering.
- Multi-viewport scenario references originally duplicated evidence keys; aggregation now performs
  deterministic deduplication.
- Review evidence sorting used a non-public reference attribute; it now uses `contract_id`.
- Chromium discovery depended on a launcher log line and page-target shutdown; it now discovers the
  loopback browser target, attaches a flattened page session, and closes through the root CDP target.
- Integration evidence originally inherited browser status without executing the applicable backend;
  a disposable real backend adapter now provides independent evidence.

## Remaining limitations

- The approved profile exercises the locally provisioned Chromium engine; additional engines require
  explicit profile adoption and adapters.
- Without an approved screenshot baseline, visual evidence is structural only.
- Performance is advisory because no approved numeric release budget exists for the reference slice.
- Rendered checks establish deterministic behavioral evidence, not full manual accessibility review.

## Review state

- WP-W08 implementation: complete
- WP-W08 review: pending
- WP-W09: blocked pending W08 approval
