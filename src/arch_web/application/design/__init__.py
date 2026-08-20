"""Public governed W04 design workflow."""

from arch_web.application.design.errors import (
    UIDesignApprovalError,
    UIDesignPreparationError,
    UIDesignWorkflowError,
)
from arch_web.application.design.models import (
    ApproveUISpecificationCommand,
    ApproveUISpecificationResult,
    PrepareUISpecificationCommand,
    PrepareUISpecificationResult,
)
from arch_web.application.design.profiles import (
    get_reference_profile,
    recommend_reference_profile,
    reference_design_profiles,
)
from arch_web.application.design.review import (
    analyze_ui_design,
    build_design_coverage,
    prepare_ui_specification,
)

__all__ = (
    "ApproveUISpecificationCommand",
    "ApproveUISpecificationResult",
    "PrepareUISpecificationCommand",
    "PrepareUISpecificationResult",
    "UIDesignApprovalError",
    "UIDesignPreparationError",
    "UIDesignWorkflowError",
    "analyze_ui_design",
    "build_design_coverage",
    "get_reference_profile",
    "prepare_ui_specification",
    "recommend_reference_profile",
    "reference_design_profiles",
)
