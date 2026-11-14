from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import io
import json
import re
import zipfile

import numpy as np
from fir_output_window import COSINE_TAPER_ALPHA
from scipy.io import wavfile
from ..fir_artifact import FinalFIRArtifact
from fir_design_common import project_centered_fir, compose_fir_stages_full
from fir_design_common.output_tap_policy import (
    FinalOutputTapResult,
    FixedWindowMode,
    apply_final_output_tap_policy,
)

from ..core import CompositeResult, MultichannelCompositeResult
from ..iir_crossover import IIRCrossoverConfig
from ..phase_alignment import AllPassSection


DSP_RESUME_FORMAT = "phaseeq-multiway-dsp-package"
DSP_RESUME_FORMAT_VERSION = 3
DSP_RESUME_MIN_SUPPORTED_VERSION = 1
DSP_DELIVERY_FORMAT = "phaseeq-multiway-dsp-export"
DSP_DELIVERY_FORMAT_VERSION = 4


def _workspace_json_default(value: object) -> object:
    """Serialize normalized Studio state without retaining live UI objects."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(orient="records")
        except TypeError:
            return value.to_dict()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


@dataclass(frozen=True)
class CompositeExport:
    files: dict[str, bytes]


@dataclass(frozen=True)
class DSPChannelExportInput:
    channel_id: str
    name: str
    way: str
    group: str
    sample_rate_hz: int
    tap_count: int | None
    fir_stages: tuple[tuple[str, np.ndarray], ...]
    phaseeq_iir: tuple[dict[str, object], ...] = ()
    phaseeq_iir_sos: tuple[tuple[float, ...], ...] = ()
    baffle_iir_parameters: dict[str, object] | None = None
    baffle_iir_sos: tuple[tuple[float, ...], ...] = ()
    iir_crossover: IIRCrossoverConfig = IIRCrossoverConfig()
    gain_db: float = 0.0
    polarity: int = 1
    dsp_additional_delay_samples: float = 0.0
    channel_relative_delay_samples: float = 0.0
    working_session_zip: bytes | None = None
    auto_alignment_delay_samples: float = 0.0
    auto_alignment_allpass: tuple[AllPassSection, ...] = ()
    timing_provenance: dict[str, object] | None = None
    cosine_taper_enabled: bool = False
    kaiser_band_split_active: bool = False
    pre_alignment_tap_count: int | None = None
    final_fir_override: np.ndarray | None = None
    adaptive_crop_metadata: dict[str, object] | None = None
    cosine_taper_protected_center_taps: int | None = None
    final_window_applied: bool = False
    basic_fir_taps: int = 1
    output_reference_delay_samples: float = 0.0
    fixed_window_mode: FixedWindowMode = "protected"


def compose_channel_fir(channel: DSPChannelExportInput) -> np.ndarray:
    """Return authoritative coefficients; output never reframes an artifact."""
    if channel.final_fir_override is not None:
        if np.iscomplexobj(channel.final_fir_override):
            raise ValueError("final FIR coefficients must be real")
        fir = np.asarray(channel.final_fir_override, dtype=float).copy()
        if (fir.ndim != 1 or fir.size != channel.tap_count
                or not np.isfinite(fir).all()):
            raise ValueError("final FIR does not match its output frame")
        return fir
    return prepare_channel_fir(channel).coefficients


def prepare_channel_fir(channel: DSPChannelExportInput, *, adaptive: bool = False) -> FinalOutputTapResult:
    """Compose unchanged stages and finalize with the common policy."""
    if channel.final_fir_override is not None or channel.final_window_applied:
        raise ValueError("a finalized channel must not regenerate its FIR")
    natural = compose_fir_stages_full(values for _, values in channel.fir_stages)
    return apply_final_output_tap_policy(
        natural, int(channel.pre_alignment_tap_count or channel.tap_count or natural.size),
        adaptive=adaptive, minimum_taps=channel.basic_fir_taps,
        output_window_enabled=channel.cosine_taper_enabled,
        fixed_window_mode=channel.fixed_window_mode,
    )


def finalized_channel(channel: DSPChannelExportInput, *, adaptive: bool = False) -> DSPChannelExportInput:
    """Capture one final coefficient set with its compensated time origin."""
    if not channel.fir_stages or channel.final_fir_override is not None:
        return channel
    result = prepare_channel_fir(channel, adaptive=adaptive)
    return capture_finalized_channel(channel, result)


def capture_finalized_channel(channel: DSPChannelExportInput,
                               result: FinalOutputTapResult) -> DSPChannelExportInput:
    """Commit validated coefficients and origin once, without any DSP work."""
    if result.validation is None:
        raise ValueError("a final FIR requires a successful validation report")
    metadata = result.adaptive.to_dict() if result.adaptive else {
        "mode": "fixed", "original_taps": result.input_taps,
        "final_taps": result.final_taps, "crop_delay_samples": result.crop_delay_samples,
        "timing_mode": "external_delay" if result.crop_delay_samples else "none",
    }
    metadata["configured_taps"] = result.configured_taps
    metadata["final_window_mode"] = result.window_mode
    metadata["final_validation"] = asdict(result.validation)
    metadata["final_crop_range"] = asdict(result.crop_range) if result.crop_range else None
    if result.frame_plan is not None:
        metadata["fixed_frame"] = asdict(result.frame_plan)
    return replace(channel, tap_count=result.final_taps, pre_alignment_tap_count=None,
                   final_fir_override=result.coefficients, final_window_applied=True,
                   cosine_taper_protected_center_taps=result.taper_reference_taps,
                   adaptive_crop_metadata=metadata,
                   dsp_additional_delay_samples=channel.dsp_additional_delay_samples + result.crop_delay_samples)


def prepare_adaptive_channel_fir(
    channel: DSPChannelExportInput,
) -> FinalOutputTapResult:
    """Compatibility entry point for common Adaptive finalization."""
    return prepare_channel_fir(channel, adaptive=True)


def fit_centered_fir_to_complex_response(response: np.ndarray, tap_count: int) -> np.ndarray:
    """Uniform-grid least-squares projection onto a centered real FIR support."""
    return project_centered_fir(response, tap_count)


def build_multichannel_export_zip(result: MultichannelCompositeResult) -> bytes:
    """Prepare analysis files and compress only on download."""
    exported = build_multichannel_export(result)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        from phase_fir_designer.output_terms import write_output_terms
        write_output_terms(archive)
        for path, data in exported.files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def build_dsp_resume_zip(
    channels: tuple[DSPChannelExportInput, ...],
    *,
    workspace: dict[str, object],
    composite: MultichannelCompositeResult | None = None,
    final_fir_artifacts: dict[str, FinalFIRArtifact] | None = None,
) -> bytes:
    """Save workspace state; only Pro includes the finalized DSP outputs."""
    from phase_fir_designer.edition import pro_feature_available
    if pro_feature_available():
        from ._dsp_resume_output import build_dsp_resume_zip as build
        return build(
            channels, workspace=workspace, composite=composite,
            final_fir_artifacts=final_fir_artifacts,
        )
    return build_workspace_resume_zip(
        workspace=workspace, sample_rate_hz=channels[0].sample_rate_hz if channels else 0,
    )


def build_workspace_resume_zip(*, workspace: dict[str, object], sample_rate_hz: int) -> bytes:
    """Save exactly the workspace read by the existing resume loader."""
    if sample_rate_hz <= 0:
        raise ValueError("invalid DSP package sample rate")
    return _write_resume_zip(workspace, int(sample_rate_hz), {})


def _write_resume_zip(
    workspace: dict[str, object], sample_rate_hz: int, files: dict[str, bytes], **manifest_extra,
) -> bytes:
    workspace_payload = dict(workspace)
    workspace_payload["format_version"] = DSP_RESUME_FORMAT_VERSION
    files["workspace.json"] = json.dumps(
        workspace_payload, ensure_ascii=False, indent=2,
        default=_workspace_json_default,
    ).encode()
    files["manifest.json"] = json.dumps({
        "format": DSP_RESUME_FORMAT, "format_version": DSP_RESUME_FORMAT_VERSION,
        "sample_rate_hz": sample_rate_hz,
        **manifest_extra,
    }, ensure_ascii=False, indent=2).encode()
    from phase_fir_designer.output_terms import OUTPUT_TERMS_FILENAME, OUTPUT_TERMS_BYTES
    files[OUTPUT_TERMS_FILENAME] = OUTPUT_TERMS_BYTES
    checksum_lines = [
        f"{hashlib.sha256(data).hexdigest()}  {path}"
        for path, data in sorted(files.items())
    ]
    files["checksums.sha256"] = ("\n".join(checksum_lines) + "\n").encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path, data in sorted(files.items()):
            output.writestr(path, data)
    return archive.getvalue()


def load_dsp_resume_zip(data: bytes) -> tuple[dict[str, object], dict[str, object]]:
    """Validate and read workspace metadata from resumable DSP packages."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if any(
            not name or name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/")
            for name in names
        ):
            raise ValueError("unsafe DSP package path")
        required = {"manifest.json", "checksums.sha256"}
        if not required.issubset(names):
            raise ValueError("DSP package is missing resume metadata")
        checksums = archive.read("checksums.sha256").decode("utf-8").splitlines()
        for line in checksums:
            digest, separator, path = line.partition("  ")
            if not separator or path not in names:
                raise ValueError("invalid DSP package checksum index")
            if hashlib.sha256(archive.read(path)).hexdigest() != digest:
                raise ValueError(f"DSP package checksum mismatch: {path}")
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            raise ValueError("invalid DSP package manifest")
        package_format = manifest.get("format")
        if package_format == DSP_RESUME_FORMAT:
            workspace_path = "workspace.json"
        elif package_format == DSP_DELIVERY_FORMAT:
            workspace_path = "configuration/workspace.json"
        else:
            raise ValueError("unsupported DSP package format")
        if workspace_path not in names:
            raise ValueError("DSP package is missing resume metadata")
        workspace = json.loads(archive.read(workspace_path))
    if not isinstance(workspace, dict):
        raise ValueError("invalid DSP package workspace")
    version = _validated_format_version(manifest, label="package")
    workspace_version = _validated_format_version(workspace, label="workspace")
    if package_format == DSP_RESUME_FORMAT:
        if not DSP_RESUME_MIN_SUPPORTED_VERSION <= version <= DSP_RESUME_FORMAT_VERSION:
            raise ValueError(f"unsupported DSP package format version: {version}")
        if workspace_version > DSP_RESUME_FORMAT_VERSION:
            raise ValueError(f"unsupported DSP workspace format version: {workspace_version}")
        if version >= 2 and workspace_version != version:
            raise ValueError("DSP package manifest/workspace version mismatch")
    else:
        if version != DSP_DELIVERY_FORMAT_VERSION:
            raise ValueError(f"unsupported DSP export format version: {version}")
        if workspace_version > DSP_RESUME_FORMAT_VERSION:
            raise ValueError(f"unsupported DSP workspace format version: {workspace_version}")
    try:
        sample_rate_hz = int(manifest.get("sample_rate_hz", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid DSP package sample rate") from exc
    if sample_rate_hz <= 0:
        raise ValueError("invalid DSP package sample rate")
    return manifest, workspace


def _validated_format_version(payload: dict[str, object], *, label: str) -> int:
    try:
        version = int(payload.get("format_version", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid DSP {label} format version") from exc
    if version < 1:
        raise ValueError(f"invalid DSP {label} format version")
    return version


def build_export(result: CompositeResult, *, stem: str = "composite") -> CompositeExport:
    wav_buffer = io.BytesIO()
    wavfile.write(wav_buffer, result.sample_rate_hz, np.asarray(result.impulse_response, dtype=np.float32))
    frd = "\n".join(f"{f:.16g} {m:.16g} {p:.16g}" for f, m, p in zip(result.frequency_hz, result.magnitude_db, result.phase_deg, strict=True)) + "\n"
    csv = "frequency_hz,magnitude_db,phase_deg,group_delay_ms\n" + "\n".join(
        f"{f:.16g},{m:.16g},{p:.16g},{g:.16g}" for f, m, p, g in zip(result.frequency_hz, result.magnitude_db, result.phase_deg, result.group_delay_ms, strict=True)
    ) + "\n"
    report = json.dumps({
        "engine": "Multiway FIR Composite Engine", "group": result.group,
        "sample_rate_hz": result.sample_rate_hz, "fft_size": result.fft_size,
        "channels": list(result.channel_responses), "normalization": "none",
    }, ensure_ascii=False, indent=2)
    return CompositeExport({f"{stem}.wav": wav_buffer.getvalue(), f"{stem}.frd": frd.encode(), f"{stem}.csv": csv.encode(), f"{stem}_report.json": report.encode()})


def build_multichannel_export(
    result: MultichannelCompositeResult,
    *, root: str = "composite",
) -> CompositeExport:
    """Export one complete artifact set per independent Composite Group."""
    files: dict[str, bytes] = {}
    group_reports: list[dict[str, object]] = []
    used_stems: set[str] = set()
    for index, (group, channel_result) in enumerate(result.groups.items(), start=1):
        base_stem = _safe_stem(group) or f"group_{index}"
        stem = base_stem
        suffix = 2
        while stem.casefold() in used_stems:
            stem = f"{base_stem}_{suffix}"
            suffix += 1
        used_stems.add(stem.casefold())
        exported = build_export(channel_result, stem=stem)
        files.update({f"{root}/{stem}/{name}": data for name, data in exported.files.items()})
        group_reports.append({
            "group": group,
            "directory": f"{root}/{stem}",
            "channels": list(channel_result.channel_responses),
            "fft_size": channel_result.fft_size,
        })
    files[f"{root}/multichannel_report.json"] = json.dumps({
        "engine": "Multiway FIR Composite Engine",
        "sample_rate_hz": result.sample_rate_hz,
        "composite_groups": group_reports,
        "output_channel_count": len(result.groups),
        "normalization": "none",
    }, ensure_ascii=False, indent=2).encode()
    return CompositeExport(files)


def _safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
