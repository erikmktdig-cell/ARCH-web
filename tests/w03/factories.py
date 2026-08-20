"""W03 test factories built from approved W02 evidence."""

from __future__ import annotations

from arch_web import (
    PrepareArchitectureCommand,
    PrepareRequirementsCommand,
    WebLifecycleStatus,
    WebRoute,
    prepare_requirements,
)
from w02.factories import PROJECT_ID, intake


def architecture_command(
    route: WebRoute = WebRoute.QUICK, **changes: object
) -> PrepareArchitectureCommand:
    prepared = prepare_requirements(PrepareRequirementsCommand(intake(route)))
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.REQUIREMENTS_APPROVED,
        "requirements_contract": prepared.requirements_contract,
        "requirements_review": prepared.review_package,
        "approved_requirements_fingerprint": (
            prepared.requirements_contract.canonical_fingerprint()
        ),
        "approved_requirements_review_fingerprint": (
            prepared.review_package.canonical_fingerprint()
        ),
        "route": route,
        "assumptions": (),
    }
    values.update(changes)
    return PrepareArchitectureCommand(**values)  # type: ignore[arg-type]
