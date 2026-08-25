"""Explicit local W08 QA adapters."""

from arch_web.adapters.qa.audits import (
    StructuralAccessibilityAdapter,
    StructuralRuntimeObservationAdapter,
    StructuralVisualAdapter,
)
from arch_web.adapters.qa.chromium import LocalChromiumAdapter
from arch_web.adapters.qa.integration import LocalBackendIntegrationAdapter
from arch_web.adapters.qa.local_preview import LocalPreviewAdapter, LocalPreviewSession

__all__ = (
    "LocalBackendIntegrationAdapter",
    "LocalChromiumAdapter",
    "LocalPreviewAdapter",
    "LocalPreviewSession",
    "StructuralAccessibilityAdapter",
    "StructuralRuntimeObservationAdapter",
    "StructuralVisualAdapter",
)
