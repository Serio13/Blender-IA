"""Barril de tablas: tablas curvadas con grosor, aros de hierro biselados con placa y remaches,
fondo, tapa opcional con travesano, banda de tela y mecha (variante polvora)."""
from math import atan2, cos, pi, sin, sqrt

from mathutils import Vector

from . import register
from .. import kit


@register
class Barrel:
    archetype = "barrel"
    defaults = dict(
        height=0.80, radius=0.30, bulge=0.13, staves=16, thickness=0.024, hoops=4,
        lid=False, wood="wood", metal="iron", band=None, fuse=False, seed=1,
    )
    variants = {
        "simple": dict(lid=False, hoops=4),
        "duelas": dict(lid=True, hoops=4, staves=18),
        "polvora": dict(lid=True, hoops=3, radius=0.25, height=0.74, band="cloth_red", fuse=True, wood="wood_dark"),
        "ron": dict(lid=True, hoops=3, wood="wood_light", metal="copper", radius=0.27, height=0.70),
    }

    def build(self, p):
        H, R, bulge, n = p["height"], p["radius"], p["bulge"], int(p["staves"])
        t = p["thickness"]
        b = kit.Builder("Barrel", p["seed"])
        rng = b.rng
        wood_roles = {"wood_light": "wood_light", "wood": "wood", "wood_dark": "wood_dark", "wood_deep": "wood_deep"}
        wood = wood_roles.get(p["wood"], "wood")

        def r_out(z):
            s = (z / H) * 2 - 1
            return R * (1 - bulge * s * s)

        gap = 0.004
        da = 2 * pi / n
        # --- tablas -------------------------------------------------------------------------------------
        for i in range(n):
            a0 = da * i + gap / (2 * R)
            a1 = da * (i + 1) - gap / (2 * R)
            z0, z1 = rng.uniform(0.0, 0.006), H - rng.uniform(0.0, 0.01)
            pid = rng.random()
            crown = rng.uniform(0.0006, 0.0022)
            jit = rng.uniform(0.0, 0.0016)           # cada tabla sobresale un poco distinto

            def outer(u, v, a0=a0, a1=a1, z0=z0, z1=z1, crown=crown, jit=jit, inner=False):
                z = z0 + (z1 - z0) * v
                r = r_out(z) - (t if inner else 0.0) + jit
                pa, pb = Vector((r * cos(a0), r * sin(a0), z)), Vector((r * cos(a1), r * sin(a1), z))
                p3 = pa + (pb - pa) * u
                mid = (pa + pb) * 0.5
                out = Vector((mid.x, mid.y, 0)).normalized()
                return p3 + out * (crown * (1 - (2 * u - 1) ** 2) * (-1 if inner else 1))

            chord = (outer(1, 0.5) - outer(0, 0.5)).length
            length = z1 - z0
            b.surface(lambda u, v: outer(u, v), 2, 14, wood, (chord, length), pid)
            b.surface(lambda u, v: outer(u, v, inner=True), 2, 14, wood, (chord, length), pid, flip=True)
            for u_edge, flipf in ((0.0, True), (1.0, False)):
                b.surface(lambda s, v, u_edge=u_edge: outer(u_edge, v, inner=False) +
                          (outer(u_edge, v, inner=True) - outer(u_edge, v, inner=False)) * s, 1, 6, wood,
                          (t, length), pid, flip=flipf, smooth=False)
            for v_end, flipf in ((0.0, False), (1.0, True)):
                b.surface(lambda u, s, v_end=v_end: outer(u, v_end, inner=False) +
                          (outer(u, v_end, inner=True) - outer(u, v_end, inner=False)) * s, 2, 1, wood,
                          (chord, t), pid, flip=flipf, smooth=False)
        # --- fondo --------------------------------------------------------------------------------------
        zb = 0.03
        rb = r_out(zb) - t
        ring = [b.vert((rb * cos(2 * pi * k / 32), rb * sin(2 * pi * k / 32), zb)) for k in range(32)]
        b.face(ring, [((cos(2 * pi * k / 32) + 1) * rb, (sin(2 * pi * k / 32) + 1) * rb) for k in range(32)],
               "wood_dark", b.island(2 * rb, 2 * rb), 0.5, smooth=False)
        # --- tapa ---------------------------------------------------------------------------------------
        if p["lid"]:
            self._lid(b, p, r_out, t)
        # --- aros ---------------------------------------------------------------------------------------
        metal = p["metal"]
        hoops = int(p["hoops"])
        zs = {2: [0.18, 0.82], 3: [0.14, 0.5, 0.86], 4: [0.10, 0.31, 0.69, 0.90], 5: [0.08, 0.26, 0.5, 0.74, 0.92]}[
            max(2, min(5, hoops))]
        for k, zf in enumerate(zs):
            self._hoop(b, p, r_out, zf * H, 0.046 if 0.2 < zf < 0.8 else 0.038, metal, rng, t)
        # --- banda de tela y mecha (polvora) ----------------------------------------------------------
        if p["band"]:
            zc = H * 0.5
            hh = H * 0.12
            r0 = max(r_out(zc - hh), r_out(zc + hh), r_out(zc)) + 0.0006
            prof = [(r0, zc - hh), (r0 + 0.010, zc - hh + 0.006), (r0 + 0.013, zc), (r0 + 0.010, zc + hh - 0.006),
                    (r0, zc + hh)]
            b.revolve(prof, 72, p["band"], smooth=True, closed=False, flip=True)
            for zz in (zc - hh, zc + hh):
                b.revolve([(r0, zz), (r0 + 0.0, zz)], 4, p["band"])
        if p["fuse"]:
            zt = H - 0.05
            path = []
            for k in range(14):
                s = k / 13
                path.append((0.045 + 0.05 * s * s, 0.0, zt + 0.05 + 0.15 * s - 0.04 * s * s))
            b.tube(path, lambda s: 0.0075 * (1 - 0.35 * s), 6, "rope", cap_end=True)
            b.cylinder((0.045, 0.0, zt + 0.045), 0.016, 0.03, "iron", 10, bevel=0.002)
        return b

    # ------------------------------------------------------------------------------------------------------
    def _hoop(self, b, p, r_out, z, width, metal, rng, t):
        w, th, c = width, 0.0105, 0.0028
        r0 = max(r_out(z - w / 2), r_out(z + w / 2), r_out(z)) + 0.0004
        prof = [(r0, z - w / 2), (r0 + th - c, z - w / 2), (r0 + th, z - w / 2 + c), (r0 + th, z + w / 2 - c),
                (r0 + th - c, z + w / 2), (r0, z + w / 2)]
        b.revolve(prof, 96, metal, flip=False, smooth=True)
        # placa con remaches en un angulo al azar
        ang = rng.uniform(0, 2 * pi)
        rr = r0 + th
        for dx in (-1, 1):
            pass
        center = Vector((rr * cos(ang), rr * sin(ang), z))
        b.box(center + Vector((cos(ang), sin(ang), 0)) * 0.0028, (0.0055, 0.075, w * 0.92), "iron_light",
              rot_z=ang, bevel=0.0016, segments=2)
        tang = Vector((-sin(ang), cos(ang), 0))
        for dx in (-0.024, 0.024):
            pos = center + tang * dx + Vector((cos(ang), sin(ang), 0)) * 0.0062
            b.sphere(pos, 0.0045, "iron_light", u=8, v=5, scale=(0.6, 0.6, 0.6))

    def _lid(self, b, p, r_out, t):
        H = p["height"]
        zl = H - 0.055
        rl = r_out(zl) - t - 0.0008
        boards = 4
        xs = [-rl + 2 * rl * k / boards for k in range(boards + 1)]
        for k in range(boards):
            x0, x1 = xs[k] + 0.0012, xs[k + 1] - 0.0012
            pid = b.rng.random()

            def ylim(x):
                return sqrt(max(rl * rl - x * x, 1e-8))

            def top(u, v, x0=x0, x1=x1, dz=0.0):
                x = x0 + (x1 - x0) * u
                return Vector((x, ylim(x) * (2 * v - 1), zl + dz))

            ymax = ylim((x0 + x1) / 2)
            b.surface(lambda u, v: top(u, v), 2, 6, "wood", ((x1 - x0), 2 * ymax), pid)
            b.surface(lambda u, v: top(u, v, dz=-0.02), 2, 6, "wood_dark", ((x1 - x0), 2 * ymax), pid, flip=True)
            for u_edge, flipf in ((0.0, True), (1.0, False)):
                b.surface(lambda s, v, u_edge=u_edge: top(u_edge, v) + Vector((0, 0, -0.02 * s)), 1, 4, "wood",
                          (0.02, 2 * ymax), pid, flip=flipf, smooth=False)
        # travesano con remaches
        b.box((0, 0, zl + 0.011), (0.075, rl * 1.9, 0.016), "wood_dark", bevel=0.003)
        for y in (-rl * 0.62, 0.0, rl * 0.62):
            b.sphere((0, y, zl + 0.022), 0.006, "iron_light", u=8, v=5, scale=(1, 1, 0.55))
