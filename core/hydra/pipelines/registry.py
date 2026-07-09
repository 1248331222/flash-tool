# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/registry.py
"""
Pipeline registry v2 -- FeatureVector key -> Pipeline class mapping.
Exact match only. No fallback, no degradation.
Unmatched feature vectors raise UnsupportedScriptError.
"""

from typing import Optional, Dict

from ..script_class import FeatureVector


class UnsupportedScriptError(Exception):
    """No pipeline matches the exact feature set."""
    def __init__(self, feature_vector: FeatureVector):
        feats = sorted(feature_vector.features)
        msg = "Unsupported {} script. Features ({}): {}".format(
            feature_vector.script_type, len(feats), feats
        )
        super().__init__(msg)
        self.feature_vector = feature_vector


# -- BAT pipeline registry: feature_key -> Pipeline class --
_BAT_REGISTRY: Dict[str, type] = {}

# -- SH pipeline registry: feature_key -> Pipeline class --
_SH_REGISTRY: Dict[str, type] = {}


def register_bat(feature_key: str, pipeline_cls: type) -> None:
    """Register a BAT pipeline for an exact feature set."""
    _BAT_REGISTRY[feature_key] = pipeline_cls


def register_sh(feature_key: str, pipeline_cls: type) -> None:
    """Register an SH pipeline for an exact feature set."""
    _SH_REGISTRY[feature_key] = pipeline_cls


def _auto_register_builtins() -> None:
    """Auto-import and register built-in pipeline modules under bat/ and sh/."""
    if _BAT_REGISTRY and _SH_REGISTRY:
        return
    import pkgutil
    import importlib
    import os

    base = os.path.dirname(__file__)

    for stype, register_fn in [
        ("bat", register_bat),
        ("sh", register_sh),
    ]:
        pkg_path = os.path.join(base, stype)
        if not os.path.isdir(pkg_path):
            continue
        for _, name, is_pkg in pkgutil.iter_modules([pkg_path]):
            if is_pkg and name.startswith(f"{stype}_"):
                try:
                    mod = importlib.import_module(
                        f".{stype}.{name}.pipeline", package="core.hydra.pipelines"
                    )
                    cls = getattr(mod, "Pipeline", None)
                    covers = getattr(mod, "COVERS", None)
                    if cls and covers:
                        fv = FeatureVector.from_set(frozenset(covers), stype)
                        register_fn(fv.to_key(), cls)
                except Exception:
                    import traceback
                    traceback.print_exc()


def get_pipeline(classify_result) -> Optional[object]:
    """
    Get pipeline class by exact FeatureVector match.
    
    Args:
        classify_result: ClassifyResult from ScriptClassifier.classify()
    
    Returns:
        Pipeline class (uninstantiated)
    
    Raises:
        UnsupportedScriptError: if no pipeline registered for this exact feature set
        ValueError: if classify_result has no feature_vector
    """
    fv = classify_result.feature_vector
    if fv is None:
        raise ValueError("classify_result has no feature_vector")

    _auto_register_builtins()

    key = fv.to_key()
    registry = _BAT_REGISTRY if fv.script_type == "bat" else _SH_REGISTRY

    cls = registry.get(key)
    if cls is None:
        raise UnsupportedScriptError(fv)
    return cls


def list_registered(script_type: str = None) -> Dict[str, type]:
    """Return all registered pipelines, optionally filtered by script_type."""
    _auto_register_builtins()
    result = {}
    if script_type in (None, "bat"):
        result.update(_BAT_REGISTRY)
    if script_type in (None, "sh"):
        result.update(_SH_REGISTRY)
    return result


__all__ = [
    "get_pipeline",
    "register_bat",
    "register_sh",
    "list_registered",
    "UnsupportedScriptError",
]