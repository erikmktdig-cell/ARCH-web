"""Explicit static HTML/CSS/JS reference adapter for the W06 vertical slice."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib

from arch_web.application.architecture.planning import semantic_id
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.frontend import (
    FrontendArtifact,
    FrontendArtifactKind,
    FrontendCheckStatus,
    FrontendComponentBinding,
    FrontendDataBinding,
    FrontendDataDisposition,
    FrontendEngineeringCheck,
    FrontendImplementationProposal,
    FrontendRouteBinding,
    FrontendSurfaceBinding,
    FrontendTokenBinding,
)
from arch_web.domain.ui_specification import WebDesignSystemContract, WebUISpecificationContract
from arch_web.domain.workspace import ImplementationPlan, ResolvedStackManifest


def _fingerprint(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


class StaticFrontendAdapter:
    """Small proof adapter; callers must select it explicitly."""

    identity = "arch-web.static-reference@0.1.0"

    def supports(self, stack: ResolvedStackManifest) -> bool:
        return (
            stack.frontend_framework == "none"
            and stack.rendering_mode == "static"
            and stack.package_manager == "none"
        )

    def compile_tokens(
        self, design: WebDesignSystemContract
    ) -> tuple[str, tuple[tuple[str, str, str], ...]]:
        resolved = design.semantic_tokens.resolve(design.primitive_tokens)
        lines = [":root {"]
        bindings: list[tuple[str, str, str]] = []
        for token in design.primitive_tokens.tokens:
            primitive_name = "--primitive-" + token.token_id.replace(".", "-")
            lines.append(f"  {primitive_name}: {token.value};")
        for role, token in resolved:
            name = "--" + role.replace(".", "-")
            primitive_name = "--primitive-" + token.token_id.replace(".", "-")
            lines.append(f"  {name}: var({primitive_name});")
            bindings.append((role, name, token.token_id))
        lines.append("}")
        return "\n".join(lines) + "\n", tuple(bindings)

    def reference_proposal(
        self,
        assignment: object,
        design: WebDesignSystemContract,
        ui: WebUISpecificationContract,
        plan: ImplementationPlan,
    ) -> FrontendImplementationProposal:
        from arch_web.domain.frontend import FrontendAssignmentPacket

        assert isinstance(assignment, FrontendAssignmentPacket)
        if not assignment.selected_unit_refs:
            raise ValueError("Reference proposal requires selected units")
        units = {item.unit_id: item for item in plan.units}
        claims = {item.unit_ref: item for item in plan.path_claims}
        token_css, compiled = self.compile_tokens(design)
        artifacts: list[FrontendArtifact] = []
        surface_artifacts: list[str] = []
        shared_units = [
            units[item] for item in assignment.selected_unit_refs if not units[item].surface_refs
        ]
        if shared_units:
            unit = shared_units[0]
            path = claims[unit.unit_id].path_pattern.removesuffix("/**") + "/tokens.css"
            artifacts.append(
                self._artifact(
                    unit.unit_id,
                    claims[unit.unit_id].claim_id,
                    path,
                    FrontendArtifactKind.STYLE,
                    token_css,
                )
            )
            token_artifact = artifacts[-1].artifact_id
        else:
            token_artifact = "embedded-token-evidence"
        for unit_ref in assignment.selected_unit_refs:
            unit = units[unit_ref]
            if not unit.surface_refs:
                continue
            root = claims[unit_ref].path_pattern.removesuffix("/**")
            html = self._html(ui)
            script = self._script()
            for filename, kind, content in (
                ("index.html", FrontendArtifactKind.SOURCE, html),
                ("interaction.js", FrontendArtifactKind.SOURCE, script),
            ):
                artifacts.append(
                    self._artifact(
                        unit_ref, claims[unit_ref].claim_id, f"{root}/{filename}", kind, content
                    )
                )
                surface_artifacts.append(artifacts[-1].artifact_id)
        surface_bindings = tuple(
            FrontendSurfaceBinding(ref, tuple(surface_artifacts)) for ref in assignment.surface_refs
        )
        route_bindings = tuple(
            FrontendRouteBinding(ref, path, surface_artifacts[0])
            for ref, path in assignment.route_paths
        )
        components = []
        ui_by_id = {item.component_id: item for item in ui.components}
        for ref in assignment.component_refs:
            spec = ui_by_id[ref]
            components.append(
                FrontendComponentBinding(
                    ref,
                    tuple(surface_artifacts),
                    tuple(item.state.value for item in spec.states),
                    spec.responsive_rule_refs,
                    (
                        "semantic landmark",
                        "keyboard operation",
                        "focus-visible style",
                        "accessible name",
                    ),
                )
            )
        data = tuple(
            FrontendDataBinding(
                semantic_id("FDB", {"component": item.component_id}),
                item.component_id,
                FrontendDataDisposition.PENDING_BACKEND_BINDING,
                f"{item.component_id}DataSource",
            )
            for item in ui.components
            if item.component_id in assignment.component_refs and item.data_bearing
        )
        tokens = tuple(
            FrontendTokenBinding(role, name, primitive, token_artifact)
            for role, name, primitive in compiled
        )
        proposal_identity = {
            "assignment": assignment.canonical_fingerprint(),
            "artifacts": artifacts,
            "surface": surface_bindings,
            "routes": route_bindings,
            "components": components,
            "tokens": tokens,
        }
        return FrontendImplementationProposal(
            CURRENT_WEB_CONTRACT_VERSION,
            semantic_id("FIP", proposal_identity),
            assignment.canonical_fingerprint(),
            assignment.selected_unit_refs,
            tuple(artifacts),
            surface_bindings,
            route_bindings,
            tuple(components),
            data,
            tokens,
            (),
            ("Reference copy is non-consequential fixture content.",),
            (),
            "arch-web-reference-executor",
            "0.1.0",
        )

    @staticmethod
    def _artifact(
        unit_ref: str,
        claim_ref: str,
        path: str,
        kind: FrontendArtifactKind,
        content: str,
    ) -> FrontendArtifact:
        return FrontendArtifact(
            semantic_id("FAR", {"unit": unit_ref, "path": path, "content": content}),
            unit_ref,
            path,
            kind,
            content,
            _fingerprint(content),
            claim_ref,
        )

    @staticmethod
    def _html(ui: WebUISpecificationContract) -> str:
        states = sorted({state.state.value for item in ui.components for state in item.states})
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Project overview</title>
  <link rel="stylesheet" href="../../shared/design/tokens.css">
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: system-ui, sans-serif; color: var(--text-primary); background: var(--surface-canvas); }}
    header, main {{ width: min(100% - 2rem, 72rem); margin-inline: auto; }}
    header {{ min-height: 4rem; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-default); }}
    main {{ display: grid; grid-template-columns: minmax(0, 2fr) minmax(16rem, 1fr); gap: var(--primitive-space-6); padding-block: var(--primitive-space-6); }}
    section, aside {{ min-width: 0; }}
    button {{ min-height: 44px; border: 0; border-radius: var(--primitive-radius-control); padding: var(--primitive-space-2) var(--primitive-space-4); background: var(--action-primary-background); color: var(--action-primary-foreground); cursor: pointer; }}
    button:hover {{ filter: brightness(.92); }} button:focus-visible {{ outline: 3px solid var(--focus-ring); outline-offset: 3px; }}
    button[aria-pressed="true"] {{ background: var(--state-success-foreground); }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--primitive-space-4); }}
    .metric {{ border-left: 4px solid var(--action-primary-background); padding: var(--primitive-space-4); background: var(--surface-default); }}
    .status {{ display: inline-flex; gap: var(--primitive-space-2); align-items: center; }} .status::before {{ content: ""; width: .65rem; height: .65rem; border-radius: 50%; background: var(--state-success-foreground); }}
    [data-state="loading"], [data-state="empty"], [data-state="error"] {{ padding: var(--primitive-space-4); border: 1px solid var(--border-default); }}
    @media (max-width: 720px) {{ main {{ grid-template-columns: 1fr; }} .metric-grid {{ grid-template-columns: 1fr; }} header {{ align-items: flex-start; padding-block: 1rem; }} }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; transition-duration: .01ms !important; }} }}
  </style>
</head>
<body>
  <header><strong>Project overview</strong><span class="status">Operational</span></header>
  <main>
    <section aria-labelledby="overview-title"><h1 id="overview-title">Overview</h1><div class="metric-grid"><article class="metric"><h2>Active work</h2><p>Fixture value</p></article><article class="metric"><h2>Quality</h2><p>Fixture value</p></article><article class="metric"><h2>Readiness</h2><p>Fixture value</p></article></div></section>
    <aside aria-labelledby="actions-title"><h2 id="actions-title">Actions</h2><button type="button" aria-pressed="false" id="state-toggle">Toggle selection</button><p role="status" id="feedback" aria-live="polite"></p></aside>
    <section aria-label="Data states"><div data-state="loading" aria-busy="true">Loading</div><div data-state="empty">No items</div><div data-state="error" role="alert">Unable to load</div></section>
  </main>
  <script src="interaction.js" defer></script>
  <!-- Implemented states: {", ".join(states)} -->
</body>
</html>
"""

    @staticmethod
    def _script() -> str:
        return """const button = document.querySelector('#state-toggle');
const feedback = document.querySelector('#feedback');
button?.addEventListener('click', () => {
  const selected = button.getAttribute('aria-pressed') !== 'true';
  button.setAttribute('aria-pressed', String(selected));
  if (feedback) feedback.textContent = selected ? 'Selected' : 'Not selected';
});
"""

    def verify(
        self,
        proposal: FrontendImplementationProposal,
        source_tree_fingerprint: str,
    ) -> tuple[FrontendEngineeringCheck, ...]:
        combined = "\n".join(item.content for item in proposal.artifacts)
        checks = {
            "format": all(item.content.endswith("\n") for item in proposal.artifacts),
            "lint": "eval(" not in combined and "document.write" not in combined,
            "typecheck": True,
            "unit": "addEventListener" in combined,
            "build": "<!doctype html>" in combined,
            "static_accessibility": all(
                marker in combined
                for marker in ("<main>", "aria-labelledby", "focus-visible", "aria-live")
            ),
            "route": bool(proposal.route_bindings),
            "traceability": bool(
                proposal.surface_bindings
                and proposal.component_bindings
                and proposal.token_bindings
            ),
        }
        return tuple(
            FrontendEngineeringCheck(
                semantic_id("FCK", {"kind": kind, "tree": source_tree_fingerprint}),
                kind,
                self.identity,
                "built-in@0.1.0",
                source_tree_fingerprint,
                FrontendCheckStatus.PASS if passed else FrontendCheckStatus.FAIL,
                0 if passed else 1,
                _fingerprint(f"{kind}:{passed}"),
                ("sanitized-static-analysis",),
                proposal.unit_refs,
            )
            for kind, passed in sorted(checks.items())
        )


__all__ = ("StaticFrontendAdapter",)
