"""Llave de cofre: anillo/cabeza decorativa, vastago con anillas, paletón con dientes y gema opcional."""
from math import cos, pi, sin

from mathutils import Matrix, Vector

from . import register
from .. import kit


@register
class Key:
    archetype = "key"
    defaults = dict(length=0.14, head="trebol", metal="gold", gem=None, shaft="iron_light", seed=1)
    variants = {
        "comun": dict(head="aro", metal="iron_light", shaft="iron"),
        "raro": dict(head="trebol", metal="gold", shaft="iron_light", gem="cloth_blue"),
        "epico": dict(head="sol", metal="gold", shaft="gold", gem="cloth_red"),
        "gotico": dict(head="trebol", metal="iron", shaft="iron_light", gem="cloth_blue"),
    }

    def build(self, p):
        L = p["length"]
        b = kit.Builder("Key", p["seed"])
        rng = b.rng
        metal, shaft = p["metal"], p["shaft"]
        # vastago a lo largo de X
        shaft_r = L * 0.035
        x0, x1 = L * 0.12, L * 0.86
        b.cylinder(((x0 + x1) / 2, 0, 0), shaft_r, x1 - x0, shaft, 12, rot=Matrix.Rotation(pi / 2, 4, "Y"), bevel=0.0006)
        # anillas del vastago
        for xr in (L * 0.2, L * 0.25):
            b.cylinder((xr, 0, 0), shaft_r * 1.7, L * 0.022, metal, 14, rot=Matrix.Rotation(pi / 2, 4, "Y"), bevel=0.0008)
        # cabeza (en el extremo x < 0)
        head = p["head"]
        hr = L * 0.17
        if head == "aro":
            self._torus(b, (-hr * 0.4, 0, 0), hr, hr * 0.22, metal)
        elif head == "sol":
            self._torus(b, (-hr * 0.4, 0, 0), hr * 0.85, hr * 0.28, metal)
            for k in range(8):
                a = 2 * pi * k / 8
                b.cylinder((-hr * 0.4 + cos(a) * hr * 1.25, sin(a) * hr * 1.25, 0), hr * 0.12, hr * 0.5, metal, 6,
                           rot=Matrix.Rotation(a + pi / 2, 4, "Z") @ Matrix.Rotation(pi / 2, 4, "Y") @ Matrix.Rotation(0, 4, "Z"),
                           bevel=0.0004)
        else:   # trebol de tres aros
            for k in range(3):
                a = pi / 2 + 2 * pi * k / 3 + pi / 6
                self._torus(b, (-hr * 0.4 + cos(a) * hr * 0.75, sin(a) * hr * 0.75, 0), hr * 0.62, hr * 0.17, metal)
        if p["gem"]:
            b.sphere((-hr * 0.4, 0, 0.0), hr * 0.38, p["gem"], u=8, v=6, scale=(1, 1, 0.7))
        # paleton con dientes
        pw, ph = L * 0.16, L * 0.2
        px = x1 - pw
        b.box((px + pw / 2, 0, -shaft_r - ph * 0.15), (pw, shaft_r * 1.4, ph * 0.5), metal, bevel=0.0008)
        n = 3
        for k in range(n):
            xx = px + pw * (k + 0.5) / n
            hh = ph * (0.45 + 0.35 * rng.random())
            b.box((xx, 0, -shaft_r - ph * 0.4 - hh / 2 + ph * 0.25), (pw / n * 0.72, shaft_r * 1.4, hh), metal, bevel=0.0007)
        return b

    @staticmethod
    def _torus(b, center, major, minor, role):
        cx, cy, cz = center
        path = [(cx + major * cos(2 * pi * k / 20), cy + major * sin(2 * pi * k / 20), cz) for k in range(21)]
        b.tube(path, minor, 6, role, cap_start=False, cap_end=False)
