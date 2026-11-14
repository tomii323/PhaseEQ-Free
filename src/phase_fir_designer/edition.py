"""Process-wide capability for the fixed FIR Auto EQ implementation."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib import import_module
from importlib.util import find_spec
import json
from pathlib import Path
from types import ModuleType

from runtime.app_update import PRO_FILES, PRO_MANIFEST, PRO_MODULE, _inventory, is_pro_installation


@dataclass(frozen=True)
class Edition:
    distribution: str
    status: str
    module: ModuleType | None = None

    @property
    def label(self) -> str:
        return {"free": "PhaseEQ Free", "pro": "PhaseEQ Pro"}[self.distribution]

    @property
    def auto_eq_available(self) -> bool:
        return self.module is not None


MESSAGES = {
    "absent": ("FIR Gain／Phase自動EQはProで利用できます。",
               "FIR Gain and Phase Auto EQ are available in Pro."),
    "missing": ("ProのFIR自動EQファイルがありません。Pro完成版ZIPを別フォルダーへ展開し直してください。",
                "The Pro FIR Auto EQ file is missing. Extract the complete Pro ZIP into a new folder."),
    "incompatible": ("本体とProの版またはビルドが一致しません。対応するPro完成版ZIPを使用してください。",
                     "The application and Pro build do not match. Use the matching complete Pro ZIP."),
    "invalid": ("Pro配布ファイルの整合性を確認できません。Pro完成版ZIPを別フォルダーへ展開し直してください。",
                "The Pro package failed its integrity check. Extract the complete Pro ZIP into a new folder."),
    "dependency": ("Proの読み込みに必要な依存関係を確認できません。Pro完成版の起動手順を確認してください。",
                   "A dependency failed to load for Pro. Follow the startup instructions for the complete Pro package."),
}


class ProAutoEQUnavailable(ValueError):
    """An active FIR Auto EQ request could not be honored."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(MESSAGES[status][0])


def _load_edition(root: Path) -> Edition:
    if not is_pro_installation(root):
        return Edition("free", "absent")
    module_path = root / PRO_MODULE
    manifest_path = root / PRO_MANIFEST
    if any(not (root / name).is_file() for name in PRO_FILES):
        return Edition("pro", "missing")
    # An unpackaged development checkout can run regression tests on the
    # private source. Installed packages always need their build manifest.
    development = (
        not manifest_path.exists()
        and not (root / "PUBLIC_FILES.sha256").exists()
        and ((root / ".git").exists() or (root / "AGENTS.md").is_file())
    )
    if not development:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("edition") != "pro":
                return Edition("pro", "invalid")
            version = (root / "VERSION").read_text(encoding="utf-8").strip()
            inventory = (root / "PUBLIC_FILES.sha256").read_bytes()
            if manifest.get("version") != version or manifest.get("build_id") != hashlib.sha256(inventory).hexdigest():
                return Edition("pro", "incompatible")
            hashes = _inventory(inventory)
            runtime_paths = ("src/", "runtime/", "ui/", "utils/", "constraints/")
            for name, digest in hashes.items():
                if name.startswith(runtime_paths) or name in {
                    "phaseeq.py", "composite_streamlit_app.py", "requirements.txt",
                }:
                    if digest != hashlib.sha256((root / name).read_bytes()).hexdigest():
                        return Edition("pro", "incompatible")
            if manifest.get("files") != {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in PRO_FILES
            }:
                return Edition("pro", "invalid")
        except (OSError, ValueError):
            return Edition("pro", "invalid")
    try:
        name = f"{__package__}._pro_auto_eq"
        spec = find_spec(name)
        if spec is None or spec.origin is None or Path(spec.origin).resolve() != module_path.absolute():
            return Edition("pro", "invalid")
        module = import_module(name)
        if not all(
            callable(getattr(module, name, None))
            for name in ("_auto_gain_section_plans", "_auto_phase_section_plans")
        ):
            return Edition("pro", "invalid")
    except ImportError:
        return Edition("pro", "dependency")
    except Exception:
        return Edition("pro", "invalid")
    return Edition("pro", "ready", module)


@lru_cache(maxsize=1)
def current_edition() -> Edition:
    return _load_edition(Path(__file__).resolve().parents[2])


def require_pro_auto_eq() -> ModuleType:
    edition = current_edition()
    if edition.module is None:
        raise ProAutoEQUnavailable(edition.status)
    return edition.module


def fir_auto_eq_requested(config) -> bool:
    from .acoustic_target import correction_config
    from .auto_eq import auto_gain_eq_sections, auto_phase_eq_sections

    auto_eq = correction_config(config).auto_eq
    return bool(auto_gain_eq_sections(auto_eq) or auto_phase_eq_sections(auto_eq))


def require_fir_auto_eq_for(config) -> None:
    if fir_auto_eq_requested(config):
        require_pro_auto_eq()


FREE_MULTIWAY_MODES = frozenset({"Fullrange", "Fullrange+SUB", "2Way"})


def multiway_mode_available(mode: str) -> bool:
    # Empty mode is used by old Exchange assignments without a topology ID.
    return not mode or mode in FREE_MULTIWAY_MODES or current_edition().auto_eq_available


def pro_feature_available() -> bool:
    """Optional features share the verification of the complete Pro payload."""
    return current_edition().status == "ready"


def require_pro_feature(feature: str) -> None:
    if not pro_feature_available():
        raise ValueError(f"{feature}: PhaseEQ Pro required")
