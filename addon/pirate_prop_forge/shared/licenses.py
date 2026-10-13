"""Registro de modelos de IA: licencia y si se pueden usar para vender lo generado.

`commercial_ok` resume la licencia; no es asesoria legal: revisa el texto original antes de vender.
"""

MODELS = {
    "fake": {"license": "prueba", "commercial_ok": False, "module": "fake",
             "about": "Malla de prueba (sin IA); solo para comprobar el plugin", "url": ""},
    "sf3d": {"license": "Stability AI Community License", "commercial_ok": True, "module": "sf3d",
             "about": "Stable Fast 3D: malla con UV y texturas PBR (~6 GB VRAM). Uso comercial gratis con ingresos "
                      "anuales por debajo de 1 M USD; por encima hay que pedir licencia a Stability AI",
             "url": "https://huggingface.co/stabilityai/stable-fast-3d"},
    "triposr": {"license": "MIT", "commercial_ok": True, "module": "triposr",
                "about": "TripoSR: malla con color por vertice (~6 GB VRAM). Licencia MIT, sin restricciones",
                "url": "https://github.com/VAST-AI-Research/TripoSR"},
}


def get(name):
    return MODELS.get(name)


def commercial_ok(name):
    m = MODELS.get(name)
    return bool(m and m["commercial_ok"])
