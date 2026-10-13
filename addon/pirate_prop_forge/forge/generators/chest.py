"""Cofre pirata de dos piezas: base de tablas horizontales con plinto, esquinas y flejes de hierro, cerradura,
asas, monedas; tapa abovedada de tablas con flejes en arco. La tapa se separa luego con el pivote en la bisagra."""
from math import cos, pi, sin, sqrt

from mathutils import Matrix, Vector

from . import register
from .. import kit


@register
class Chest:
    archetype = "chest"
    parts = ("base", "tapa")
    defaults = dict(
        width=0.72, depth=0.48, body_h=0.30, skirt=0.04, wood="wood", metal="iron", lock="iron_light",
        coins="iron_light", coin_count=150, lining="wood_dark", open_deg=0.0, straps=2, seed=1,
    )
    variants = {
        "comun": dict(),
        "raro": dict(wood="wood_dark", metal="iron_light", lock="gold", coins="gold", lining="cloth_red_d", coin_count=190),
        "epico": dict(wood="wood_deep", metal="gold", lock="gold", coins="gold", lining="cloth_red", coin_count=230),
        "gotico": dict(wood="wood_deep", metal="iron", lock="iron_light", coins="gold", lining="cloth_blue", coin_count=170),
    }

    @staticmethod
    def part_origins(p):
        """Origen de cada pieza: la tapa gira en la bisagra (borde trasero, base de la tapa)."""
        return {"base": (0.0, 0.0, 0.0), "tapa": (0.0, p["depth"] / 2 + 0.004 - 0.02, p["body_h"])}

    def build(self, p):
        W, D, Hb = p["width"], p["depth"], p["body_h"]
        t = 0.022
        b = kit.Builder("Chest", p["seed"])
        rng = b.rng
        wood = p["wood"]
        plinth = 0.035
        b.part = 0
        # --- plinto y suelo ------------------------------------------------------------------------------
        b.box((0, 0, plinth / 2), (W + 0.026, D + 0.026, plinth), "wood_dark", bevel=0.004, pid=0.2)
        b.box((0, 0, plinth + 0.01), (W - 2 * t, D - 2 * t, 0.02), "wood_dark", bevel=0.002, pid=0.3)
        # --- tablas de las paredes ---------------------------------------------------------------------
        n = 3
        hp = (Hb - plinth) / n
        for k in range(n):
            z = plinth + hp * (k + 0.5)
            for y in (-(D / 2 - t / 2), D / 2 - t / 2):
                b.box((0, y, z), (W, t, hp - 0.003), wood, bevel=0.0028, pid=rng.random())
            for x in (-(W / 2 - t / 2), W / 2 - t / 2):
                b.box((x, 0, z), (t, D - 2 * t - 0.002, hp - 0.003), wood, bevel=0.0028, pid=rng.random())
        # --- monedas -----------------------------------------------------------------------------------
        for _ in range(int(p["coin_count"])):
            r = abs(rng.gauss(0, 0.085))
            a = rng.uniform(0, 2 * pi)
            x = max(-W / 2 + t + 0.02, min(W / 2 - t - 0.02, cos(a) * r * 1.5))
            y = max(-D / 2 + t + 0.02, min(D / 2 - t - 0.02, sin(a) * r * 1.0))
            h = plinth + 0.025 + 0.085 * (2.718 ** (-((r / 0.11) ** 2))) + rng.uniform(0, 0.014)
            tilt = Matrix.Rotation(rng.uniform(-0.7, 0.7), 4, "X") @ Matrix.Rotation(rng.uniform(-0.7, 0.7), 4, "Y")
            b.cylinder((x, y, h), 0.0178, 0.0038, p["coins"], 9, rot=tilt, smooth=False)
        # --- hierro: esquinas, flejes, cerradura, asas ---------------------------------------------------
        metal = p["metal"]
        zc = plinth + (Hb - plinth) / 2
        hcorner = Hb - plinth + 0.012
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = sx * (W / 2), sy * (D / 2)
                b.box((cx - sx * 0.026, cy + sy * 0.003, zc + 0.006), (0.06, 0.007, hcorner), metal, bevel=0.0018)
                b.box((cx + sx * 0.003, cy - sy * 0.026, zc + 0.006), (0.007, 0.06, hcorner), metal, bevel=0.0018)
                for k in range(3):
                    zz = plinth + 0.05 + k * 0.08
                    b.sphere((cx - sx * 0.04, cy + sy * 0.0075, zz), 0.0052, "iron_light", scale=(1, 0.55, 1))
                    b.sphere((cx + sx * 0.0075, cy - sy * 0.04, zz), 0.0052, "iron_light", scale=(0.55, 1, 1))
        xs = (-0.26, 0.0, 0.26) if int(p["straps"]) == 3 else (-0.2, 0.2)
        for x in xs:
            for y in (-(D / 2 + 0.0035), D / 2 + 0.0035):
                b.box((x, y, zc + 0.006), (0.058, 0.007, Hb - plinth + 0.002), metal, bevel=0.0018)
                for k in range(4):
                    b.sphere((x, y + (0.004 if y > 0 else -0.004), plinth + 0.04 + k * 0.07), 0.0055, "iron_light",
                             scale=(1, 0.55, 1))
        # cerradura
        lock = p["lock"]
        b.box((0, -(D / 2 + 0.006), Hb - 0.072), (0.075, 0.012, 0.095), lock, bevel=0.003)
        b.box((0, -(D / 2 + 0.0125), Hb - 0.078), (0.014, 0.004, 0.03), "iron", bevel=0.001)
        for dx in (-0.027, 0.027):
            for dz in (-0.03, 0.03):
                b.sphere((dx, -(D / 2 + 0.0125), Hb - 0.072 + dz), 0.0046, "iron_light", scale=(1, 0.55, 1))
        # asas laterales (anilla de hierro)
        for sx in (-1, 1):
            b.box((sx * (W / 2 + 0.0035), 0, zc + 0.045), (0.007, 0.05, 0.05), metal, bevel=0.0018)
            ring = [(sx * (W / 2 + 0.014), 0.034 * cos(2 * pi * k / 16), zc + 0.015 + 0.034 * sin(2 * pi * k / 16))
                    for k in range(17)]
            b.tube(ring, 0.0062, 6, metal, cap_start=False, cap_end=False)
        # --- tapa ----------------------------------------------------------------------------------------
        b.part = 1
        self._lid(b, p, plinth, rng)
        return b

    def _lid(self, b, p, plinth, rng):
        W, D, Hb, sk = p["width"], p["depth"], p["body_h"], p["skirt"]
        Wl, Rl, t = W - 0.014, D / 2 + 0.004, 0.02
        z0 = Hb                       # base de la tapa cerrada
        zc = z0 + sk                  # centro del arco
        wood, metal = p["wood"], p["metal"]
        n = 7
        a_lo, a_hi = -pi / 2, pi / 2
        gap = 0.0035 / Rl
        for k in range(n):
            a0 = a_lo + (a_hi - a_lo) * k / n + gap / 2
            a1 = a_lo + (a_hi - a_lo) * (k + 1) / n - gap / 2
            pid = rng.random()
            arc = (a1 - a0) * Rl

            def pt(u, v, r, a0=a0, a1=a1):
                a = a0 + (a1 - a0) * u
                return Vector((-Wl / 2 + Wl * v, r * sin(a), zc + r * cos(a)))

            b.surface(lambda u, v: pt(u, v, Rl), 4, 2, wood, (arc, Wl), pid)
            b.surface(lambda u, v: pt(u, v, Rl - t), 4, 2, p["lining"], (arc, Wl), pid, flip=True)
            for v_edge, flipf in ((0.0, True), (1.0, False)):
                b.surface(lambda u, s, v_edge=v_edge: pt(u, v_edge, Rl) + (pt(u, v_edge, Rl - t) - pt(u, v_edge, Rl)) * s,
                          4, 1, wood, (arc, t), pid, flip=flipf, smooth=False)
            for u_edge, flipf in ((0.0, True), (1.0, False)):
                b.surface(lambda s, v, u_edge=u_edge: pt(u_edge, v, Rl) + (pt(u_edge, v, Rl - t) - pt(u_edge, v, Rl)) * s,
                          1, 2, wood, (t, Wl), pid, flip=flipf, smooth=False)
        # faldones rectos delante y detras + tapas laterales semicirculares
        for sy in (-1, 1):
            b.box((0, sy * (Rl - t / 2), z0 + sk / 2), (Wl, t, sk), wood, bevel=0.0025, pid=rng.random())
        for x in (-Wl / 2 + 0.006, Wl / 2 - 0.006):
            ring = [b.vert((x, (Rl - t) * sin(a_lo + (a_hi - a_lo) * k / 20), zc + (Rl - t) * cos(a_lo + (a_hi - a_lo) * k / 20)))
                    for k in range(21)]
            ring += [b.vert((x, (Rl - t), z0)), b.vert((x, -(Rl - t), z0))]
            isl = b.island(2 * (Rl - t), Rl - t + sk)
            uvs = [((v.co.y + Rl) , v.co.z - z0) for v in ring]
            b.face(ring if x > 0 else ring[::-1], uvs, "wood_dark", isl, 0.4, smooth=False)
        # flejes en arco + faldon
        for x in ((-0.2, 0.2) if int(p["straps"]) != 3 else (-0.26, 0.0, 0.26)):
            b.band_arc((0.0, zc), Rl, x, (a_lo, a_hi), 0.006, 0.058, metal, segments=28)
            for sy in (-1, 1):
                b.box((x, sy * (Rl + 0.0035), z0 + sk / 2 - 0.0), (0.058, 0.007, sk + 0.004), metal, bevel=0.0018)
            for k in range(5):
                a = a_lo + (a_hi - a_lo) * (k + 0.5) / 5
                b.sphere((x, (Rl + 0.0085) * sin(a), zc + (Rl + 0.0085) * cos(a)), 0.0052, "iron_light",
                         scale=(1, 1, 0.6))
        # hembrilla del cierre
        b.box((0, -(Rl + 0.004), z0 + sk - 0.005), (0.05, 0.008, 0.06), p["lock"], bevel=0.0025)
