"""Caja de madera: tablas con bisel, marco y travesanos diagonales, refuerzos de hierro (variante reforzada) y
cuerdas (variante carga). Cuatro variantes."""
from math import atan2, cos, pi, sin, sqrt

from mathutils import Matrix, Vector

from . import register
from .. import kit


@register
class Crate:
    archetype = "crate"
    defaults = dict(size=(0.62, 0.62, 0.60), planks=4, wood="wood", metal="iron", frame=True, braces=True,
                    straps=False, rope=False, lid=True, seed=1)
    variants = {
        "simple": dict(metal="iron"),
        "reforzada": dict(straps=True, size=(0.70, 0.70, 0.68), wood="wood_dark"),
        "carga": dict(size=(1.0, 0.7, 0.55), rope=True, planks=5, wood="wood_light", lid=False),
    }

    def build(self, p):
        X, Y, Z = p["size"]
        b = kit.Builder("Crate", p["seed"])
        rng = b.rng
        wood, metal = p["wood"], p["metal"]
        t = 0.02
        n = int(p["planks"])
        # paredes de tablas verticales (4 lados)
        hp = Z / n
        for side, (sx, sy) in enumerate(((0, -1), (0, 1), (-1, 0), (1, 0))):
            span = X if sx == 0 else Y - 2 * t
            for k in range(n):
                z = hp * (k + 0.5)
                size = (span, t, hp - 0.003) if sx == 0 else (t, span, hp - 0.003)
                pos = (0, sy * (Y / 2 - t / 2), z) if sx == 0 else (sx * (X / 2 - t / 2), 0, z)
                b.box(pos, size, wood, bevel=0.0026, pid=rng.random())
        b.box((0, 0, 0.012), (X - 2 * t, Y - 2 * t, 0.024), "wood_dark", bevel=0.002, pid=0.3)
        # marco: 4 postes de esquina + travesanos superior e inferior
        if p["frame"]:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    b.box((sx * (X / 2 - 0.024), sy * (Y / 2 - 0.024), Z / 2), (0.05, 0.05, Z + 0.012), "wood_dark",
                          bevel=0.004, pid=rng.random())
            for z in (0.012, Z - 0.012):
                for sy in (-1, 1):
                    b.box((0, sy * (Y / 2 + 0.002), z), (X + 0.01, 0.026, 0.04), "wood_dark", bevel=0.003, pid=rng.random())
                for sx in (-1, 1):
                    b.box((sx * (X / 2 + 0.002), 0, z), (0.026, Y + 0.01, 0.04), "wood_dark", bevel=0.003, pid=rng.random())
        # diagonal en las caras frontal y trasera
        if p["braces"]:
            ang = atan2(Z - 0.1, X - 0.1)
            ln = sqrt((X - 0.1) ** 2 + (Z - 0.1) ** 2)
            for sy in (-1, 1):
                b.box((0, sy * (Y / 2 + 0.014), Z / 2), (ln, 0.014, 0.05), "wood_dark", bevel=0.003, pid=rng.random(),
                      rot=Matrix.Rotation(-ang, 4, "Y"))
        # tapa de tablas (cajas cerradas)
        if p["lid"]:
            for k in range(n):
                y = -Y / 2 + (k + 0.5) * Y / n
                b.box((0, y, Z + 0.011), (X + 0.012, Y / n - 0.004, 0.022), wood, bevel=0.003, pid=rng.random())
        # refuerzos de hierro en las esquinas (variante reforzada)
        if p["straps"]:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for z in (0.07, Z - 0.07):
                        b.box((sx * (X / 2 + 0.004), sy * (Y / 2 - 0.05), z), (0.008, 0.11, 0.07), metal, bevel=0.002)
                        b.box((sx * (X / 2 - 0.05), sy * (Y / 2 + 0.004), z), (0.11, 0.008, 0.07), metal, bevel=0.002)
                        b.sphere((sx * (X / 2 + 0.0085), sy * (Y / 2 - 0.03), z), 0.0055, "iron_light", scale=(0.55, 1, 1))
            b.box((0, -(Y / 2 + 0.006), Z * 0.62), (0.08, 0.012, 0.1), "iron_light", bevel=0.003)
        # cuerda (variante carga): dos vueltas alrededor
        if p["rope"]:
            for x in (-X * 0.28, X * 0.28):
                pts = []
                hx, hy = X / 2 + 0.013, Y / 2 + 0.013
                for (px, py) in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy)):
                    pass
                path = []
                corners = [(x, -hy, 0.03), (x, -hy, Z + 0.02), (x, hy, Z + 0.02), (x, hy, 0.03), (x, -hy, 0.03)]
                for a, c in zip(corners[:-1], corners[1:]):
                    for k in range(6):
                        s = k / 6
                        path.append(tuple(a[i] + (c[i] - a[i]) * s for i in range(3)))
                path.append(corners[-1])
                b.tube(path, 0.0085, 6, "rope", cap_start=False, cap_end=False)
        return b
