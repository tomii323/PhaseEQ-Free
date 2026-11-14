from .adapters import adapter_by_id, available_adapters
from .canonical import canonical_from_export_inputs
from .models import CanonicalDSPChannel, CanonicalDSPPackage, CompatibilityIssue, CompatibilityReport, DSPProfile
from composite_engine.export import DSP_DELIVERY_FORMAT_VERSION as DSP_EXPORT_FORMAT_VERSION


def build_dsp_export_zip(*args, **kwargs):
    from phase_fir_designer.edition import require_pro_feature
    require_pro_feature("Multiway DSP export")
    from .package import build_dsp_export_zip as build
    return build(*args, **kwargs)


def package_filename(*args, **kwargs):
    from .package import package_filename as filename
    return filename(*args, **kwargs)

__all__ = [
    "CanonicalDSPChannel", "CanonicalDSPPackage", "CompatibilityIssue",
    "CompatibilityReport", "DSPProfile", "DSP_EXPORT_FORMAT_VERSION",
    "adapter_by_id", "available_adapters", "build_dsp_export_zip", "package_filename",
    "canonical_from_export_inputs",
]
