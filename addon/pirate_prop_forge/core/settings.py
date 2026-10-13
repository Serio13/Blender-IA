from dataclasses import dataclass

from .errors import PFError

# Ratios de triangulos para LOD1, LOD2, ... respecto a LOD0 (que no se toca).
PRESETS = {
    "estandar": (0.35, 0.10),
    "agresivo": (0.25, 0.06),
    "ligero": (0.60, 0.30),
    "completo": (0.50, 0.25, 0.08),
}

COLLIDERS = ("none", "hint", "mesh")
PIVOTS = ("base", "center", "keep")
LAYOUTS = ("grouped", "flat")


@dataclass
class LodSettings:
    ratios: tuple = PRESETS["estandar"]
    tris: tuple = ()              # objetivos absolutos por LOD; si existen, anulan ratios
    min_tris: int = 24            # no se crea un LOD con menos triangulos totales
    skip_below: int = 300         # assets con menos triangulos no necesitan LODs
    dissolve_deg: float = 3.0     # disolucion planar previa (0 = desactivada)
    smooth_deg: float = 35.0      # angulo de sombreado suave en los LODs
    spread: bool = False          # separar los LODs en X para revisarlos en Blender
    keep_uv2: bool = True         # conservar capas UV adicionales
    strict: bool = True           # sube o descarta los LODs que deformen la forma o la textura


def lod_settings(preset="estandar", ratios=None, tris=None, **kw):
    if ratios is None:
        if preset not in PRESETS:
            raise PFError("preset desconocido '%s' (opciones: %s)" % (preset, ", ".join(PRESETS)))
        ratios = PRESETS[preset]
    ratios = tuple(float(r) for r in ratios)
    for r in ratios:
        if not 0.0 < r < 1.0:
            raise PFError("cada ratio debe estar entre 0 y 1 (sin incluir LOD0): %r" % (ratios,))
    return LodSettings(ratios=ratios, tris=tuple(int(t) for t in (tris or ())), **kw)
