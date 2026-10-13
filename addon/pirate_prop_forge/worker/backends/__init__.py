"""Backends de generacion imagen -> malla. Cada uno expone `Backend` (ver base.py)."""
import importlib
import importlib.util
from pathlib import Path


def _licenses():
    spec = importlib.util.spec_from_file_location("pf_shared_licenses", Path(__file__).resolve().parents[2] / "shared" / "licenses.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LIC = _licenses()
REGISTRY = {name: meta["module"] for name, meta in _LIC.MODELS.items()}


def info():
    return {k: {"license": v["license"], "commercial_ok": v["commercial_ok"], "about": v["about"]}
            for k, v in _LIC.MODELS.items()}


def load(name):
    if name not in REGISTRY:
        raise KeyError("backend desconocido: %s" % name)
    module = importlib.import_module("%s.%s" % (__name__, REGISTRY[name]))
    return module.Backend()
