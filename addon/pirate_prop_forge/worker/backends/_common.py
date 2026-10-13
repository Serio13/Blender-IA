"""Utilidades comunes de los backends reales (se importan solo dentro del worker)."""
import gc
import importlib.util


def has(module):
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def pick_device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def supports_bf16():
    """bf16 rapido solo desde Ampere (sm_80). En Pascal (GTX 1080 Ti, sm_61) se usa FP32."""
    import torch
    if not torch.cuda.is_available():
        return False
    return torch.cuda.get_device_capability(0)[0] >= 8


def free_gpu():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def remove_background(image, session_holder):
    """Quita el fondo con rembg en CPU (deja la GPU libre para el modelo 3D)."""
    import rembg
    if image.mode == "RGBA" and image.getextrema()[3][0] < 255:
        return image                      # ya trae transparencia
    if session_holder.get("s") is None:
        session_holder["s"] = rembg.new_session("u2net", providers=["CPUExecutionProvider"])
    return rembg.remove(image, session=session_holder["s"])
